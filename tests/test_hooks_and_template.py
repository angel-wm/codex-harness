"""Hook wire-contract and distributable template tests."""
from __future__ import annotations

import ast
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
from tests.support import HARNESSCTL_PATH
from tests.support import TEMPLATE_ROOT
from tests.support import LocalTemporaryDirectory
from tests.support import TemporaryProject
from tests.support import approve_fixture
from tests.support import implement_fixture
from tests.support import read_json
from tests.support import write_json
from tests.support import harnessctl


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

    def test_canonical_facade_exports_existing_python_surface(self) -> None:
        expected = {
            "HarnessError",
            "utc_now",
            "json_load",
            "atomic_write",
            "json_write",
            "run_git",
            "discover_root",
            "paths",
            "normalized_relative",
            "validate_step",
            "validate_config",
            "spec_paths",
            "parse_requirements",
            "parse_tasks",
            "validate_spec",
            "validate_features",
            "load_state",
            "find_feature",
            "canonical_spec_digest",
            "git_is_clean",
            "changed_paths",
            "is_volatile",
            "implementation_fingerprint",
            "approval_is_current",
            "select_argv",
            "command_fingerprint",
            "run_command_group",
            "validate_repository",
            "doctor",
            "status_payload",
            "update_current",
            "transition_spec_ready",
            "approve_feature",
            "read_review",
            "record_review",
            "traceability_ids",
            "complete_feature",
            "block_feature",
            "resume_feature",
            "print_status",
            "build_parser",
            "main",
        }
        self.assertEqual({name for name in expected if hasattr(harnessctl, name)}, expected)
        for constant in (
            "SCHEMA_VERSION",
            "VALID_STATES",
            "BLOCKABLE_STATES",
            "VOLATILE_PATHS",
            "REQUIRED_TEMPLATE_PATHS",
        ):
            self.assertTrue(hasattr(harnessctl, constant), constant)

    def test_internal_modules_are_distributed_with_acyclic_dependencies(self) -> None:
        module_root = TEMPLATE_ROOT / "harness" / "scripts" / "harness_core"
        expected_paths = {
            f"harness/scripts/harness_core/{name}.py"
            for name in ("__init__", "repository", "specs", "state", "runner", "inspection", "workflow")
        }
        self.assertEqual(
            {path.relative_to(TEMPLATE_ROOT).as_posix() for path in module_root.glob("*.py")},
            expected_paths,
        )
        self.assertTrue(expected_paths.issubset(set(harnessctl.REQUIRED_TEMPLATE_PATHS)))

        ranks = {"repository": 0, "specs": 0, "state": 1, "runner": 2, "workflow": 2, "inspection": 3}
        for path in module_root.glob("*.py"):
            if path.stem == "__init__":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                self.assertNotEqual(node.module, "harnessctl")
                if node.level == 1 and node.module in ranks:
                    self.assertLess(ranks[node.module], ranks[path.stem])

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

    def run_control_plane(
        self, project: TemporaryProject, *arguments: str, cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        return subprocess.run(
            [sys.executable, str(project.root / HARNESSCTL_PATH.relative_to(TEMPLATE_ROOT)), *arguments],
            cwd=cwd or project.root,
            env=environment,
            text=True,
            encoding="utf-8",
            capture_output=True,
            shell=False,
            check=False,
        )

    def test_cli_runs_from_root_and_subdirectory_without_pythonpath(self) -> None:
        with TemporaryProject() as project:
            root_result = self.run_control_plane(project, "validate")
            nested_result = self.run_control_plane(project, "status", "--json", cwd=project.root / "harness" / "docs")
            self.assertEqual(root_result.returncode, 0, root_result.stderr)
            self.assertEqual(json.loads(root_result.stdout), {"valid": True, "feature_count": 1})
            self.assertEqual(nested_result.returncode, 0, nested_result.stderr)
            self.assertEqual(json.loads(nested_result.stdout)["project"], "fixture")
            self.assertFalse(any((project.root / "harness" / "scripts").rglob("__pycache__")))

    def test_cli_preserves_argument_and_domain_error_exit_codes(self) -> None:
        with TemporaryProject() as project:
            invalid = self.run_control_plane(project, "unknown-command")
            domain = self.run_control_plane(project, "run", "bootstrap")
            self.assertEqual(invalid.returncode, 2)
            self.assertIn("invalid choice", invalid.stderr)
            self.assertEqual(domain.returncode, 2)
            self.assertEqual(domain.stdout, "")
            self.assertIn("error: No commands are configured for bootstrap", domain.stderr)

    def test_post_tool_use_returns_empty_json_when_valid(self) -> None:
        with TemporaryProject() as project:
            code, output, stderr = self.run_hook(project, {"hook_event_name": "PostToolUse"})
            self.assertEqual(code, 0, stderr)
            self.assertEqual(output, {})
            self.assertFalse(any((project.root / "harness" / "scripts").rglob("__pycache__")))

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
