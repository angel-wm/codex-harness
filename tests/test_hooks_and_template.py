"""Hook wire-contract and distributable template tests."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from tests.support import REPOSITORY_ROOT
from tests.support import TEMPLATE_ROOT
from tests.support import LocalTemporaryDirectory
from tests.support import TemporaryProject
from tests.support import approve_fixture
from tests.support import implement_fixture
from tests.support import read_json
from tests.support import write_json


class TestStaticTemplate(unittest.TestCase):
    """Parse Codex configuration and prohibit legacy/provider coupling."""

    def test_hooks_json_has_cross_platform_handlers(self) -> None:
        hooks = read_json(TEMPLATE_ROOT / ".codex" / "hooks.json")["hooks"]
        self.assertIn("PostToolUse", hooks)
        self.assertIn("Stop", hooks)
        for event in hooks.values():
            for group in event:
                for handler in group["hooks"]:
                    self.assertEqual(handler["type"], "command")
                    self.assertIn("command", handler)
                    self.assertIn("commandWindows", handler)

    def test_project_and_agent_toml_parse(self) -> None:
        config = tomllib.loads((TEMPLATE_ROOT / ".codex" / "config.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["agents"]["max_concurrent_threads_per_session"], 3)
        for path in (TEMPLATE_ROOT / ".codex" / "agents").glob("*.toml"):
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(data["name"])
            self.assertTrue(data["description"])
            self.assertTrue(data["developer_instructions"])
            self.assertNotIn("model", data)
            self.assertNotIn("model_reasoning_effort", data)
        reviewer = tomllib.loads(
            (TEMPLATE_ROOT / ".codex" / "agents" / "sdd-reviewer.toml").read_text(encoding="utf-8")
        )
        self.assertEqual(reviewer["sandbox_mode"], "read-only")

    def test_skill_front_matter_and_trigger_scope(self) -> None:
        text = (TEMPLATE_ROOT / ".agents" / "skills" / "sdd-workflow" / "SKILL.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?s)^---\nname: sdd-workflow\ndescription: .+?\n---")
        self.assertIn("Do not use for pure questions", text)

    def test_template_has_no_legacy_or_provider_specific_artifacts(self) -> None:
        files = [path for path in TEMPLATE_ROOT.rglob("*") if path.is_file() and "__pycache__" not in path.parts]
        relative = [path.relative_to(TEMPLATE_ROOT).as_posix().lower() for path in files]
        self.assertFalse(any(path.startswith(".claude/") for path in relative))
        combined = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in files)
        for forbidden in ("OPENAI_API_KEY", "from openai import", "import openai", "git add .", "git add --all", "/tmp/"):
            self.assertNotIn(forbidden, combined)
        self.assertNotRegex(combined, r"(?m)^model\s*=")
        self.assertNotIn("notes-cli", combined.lower())

    def test_no_duplicate_control_plane_copy_exists(self) -> None:
        matches = [
            path
            for path in REPOSITORY_ROOT.rglob("harnessctl.py")
            if "__pycache__" not in path.parts and "private" not in path.parts
        ]
        self.assertEqual(matches, [TEMPLATE_ROOT / "harness" / "scripts" / "harnessctl.py"])

    def test_ci_matrix_runs_windows_and_native_posix(self) -> None:
        workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        self.assertIn("ubuntu-latest", workflow)
        self.assertIn("windows-latest", workflow)
        self.assertIn('"3.11"', workflow)
        self.assertIn("python -m unittest discover -s tests -v", workflow)

    @unittest.skipUnless(shutil.which("codex"), "installed Codex client is required")
    def test_installed_codex_strictly_parses_template_config(self) -> None:
        temporary = LocalTemporaryDirectory()
        try:
            codex_home = Path(temporary.name) / "codex-home"
            shutil.copytree(TEMPLATE_ROOT / ".codex", codex_home)
            environment = os.environ.copy()
            environment["CODEX_HOME"] = str(codex_home)
            executable = shutil.which("codex")
            self.assertIsNotNone(executable)

            def run_strict_config() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [
                        executable,
                        "exec",
                        "--strict-config",
                        "--disable",
                        "plugins",
                        "--ephemeral",
                        "resume",
                        "00000000-0000-0000-0000-000000000000",
                        "configuration smoke test",
                    ],
                    cwd=TEMPLATE_ROOT,
                    env=environment,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    shell=False,
                    check=False,
                )

            valid = run_strict_config()
            self.assertNotEqual(valid.returncode, 0)
            valid_output = (valid.stdout + valid.stderr).lower()
            self.assertNotIn("unknown_harness_test_key", valid_output)
            self.assertRegex(valid_output, r"thread|session|rollout|not found")

            config_path = codex_home / "config.toml"
            original_config = config_path.read_text(encoding="utf-8")
            config_path.write_text("unknown_harness_test_key = true\n" + original_config, encoding="utf-8")
            invalid_config = run_strict_config()
            self.assertNotEqual(invalid_config.returncode, 0)
            self.assertIn("unknown_harness_test_key", (invalid_config.stdout + invalid_config.stderr).lower())
        finally:
            temporary.cleanup()


class TestHookContracts(unittest.TestCase):
    """Drive the actual stdin/stdout hooks in temporary Git repositories."""

    def run_hook(self, project: TemporaryProject, event: dict[str, object]) -> tuple[int, dict[str, object], str]:
        script = project.root / "harness" / "scripts" / "codex_hook.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=project.root,
            input=json.dumps(event),
            text=True,
            encoding="utf-8",
            capture_output=True,
            shell=False,
            check=False,
        )
        return result.returncode, json.loads(result.stdout), result.stderr

    def test_post_tool_use_returns_empty_json_when_valid(self) -> None:
        with TemporaryProject() as project:
            code, output, stderr = self.run_hook(project, {"hook_event_name": "PostToolUse"})
            self.assertEqual(code, 0, stderr)
            self.assertEqual(output, {})
            self.assertFalse((project.root / "harness" / "scripts" / "__pycache__").exists())

    def test_post_tool_use_blocks_invalid_state(self) -> None:
        with TemporaryProject() as project:
            features = read_json(project.root / "harness" / "features.json")
            features["features"][0]["status"] = "invalid"
            write_json(project.root / "harness" / "features.json", features)
            _, output, _ = self.run_hook(project, {"hook_event_name": "PostToolUse"})
            self.assertEqual(output["decision"], "block")
            self.assertIn("structural validation", output["reason"])

    def test_stop_skips_full_verification_without_active_feature(self) -> None:
        with TemporaryProject() as project:
            marker = project.root / "verification-ran"
            config = read_json(project.root / "harness" / "config.json")
            config["commands"]["verify"] = [{
                "name": "marker",
                "argv": [sys.executable, "-c", f"open({str(marker)!r},'w').write('x')"],
                "cwd": ".",
                "env": {},
                "timeout_seconds": 10,
            }]
            write_json(project.root / "harness" / "config.json", config)
            _, output, _ = self.run_hook(project, {"hook_event_name": "Stop", "stop_hook_active": False})
            self.assertEqual(output, {})
            self.assertFalse(marker.exists())

    def test_stop_verifies_changed_implementation(self) -> None:
        with TemporaryProject() as project:
            approve_fixture(project)
            implement_fixture(project)
            _, output, stderr = self.run_hook(project, {"hook_event_name": "Stop", "stop_hook_active": False})
            self.assertIn("verification passed", output["systemMessage"].lower(), stderr)
            evidence = read_json(project.root / "harness" / "progress" / "verification.json")
            self.assertTrue(evidence["success"])

    def test_stop_requests_one_continuation_then_stops_recursing(self) -> None:
        with TemporaryProject() as project:
            approve_fixture(project)
            implement_fixture(project, passing=False)
            _, first, _ = self.run_hook(project, {"hook_event_name": "Stop", "stop_hook_active": False})
            self.assertEqual(first["decision"], "block")
            _, second, _ = self.run_hook(project, {"hook_event_name": "Stop", "stop_hook_active": True})
            self.assertNotIn("decision", second)
            self.assertIn("already used", second["systemMessage"])


if __name__ == "__main__":
    unittest.main()
