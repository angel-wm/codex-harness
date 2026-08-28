"""Configuration and structured command execution tests."""
from __future__ import annotations

import json
import os
import sys
import unittest

from tests.support import TemporaryProject
from tests.support import harnessctl
from tests.support import read_json
from tests.support import write_json


class TestConfiguration(unittest.TestCase):
    """Validate language-neutral configuration boundaries."""

    def test_template_configuration_is_structurally_valid(self) -> None:
        with TemporaryProject() as project:
            result = harnessctl.validate_repository(project.root)
            self.assertTrue(result["valid"])

    def test_platform_specific_argv_takes_precedence(self) -> None:
        step = {
            "name": "x",
            "argv": ["common"],
            "windows_argv": ["windows"],
            "posix_argv": ["posix"],
        }
        self.assertEqual(harnessctl.select_argv(step, "windows"), ["windows"])
        self.assertEqual(harnessctl.select_argv(step, "posix"), ["posix"])

    def test_common_argv_is_fallback(self) -> None:
        self.assertEqual(harnessctl.select_argv({"name": "x", "argv": ["common"]}, "posix"), ["common"])

    def test_rejects_shell_string(self) -> None:
        with TemporaryProject() as project:
            config = read_json(project.root / "harness" / "config.json")
            config["commands"]["verify"][0]["argv"] = "python -m unittest"
            errors = harnessctl.validate_config(config, project.root)
            self.assertTrue(any("argv must be a non-empty string array" in item for item in errors))

    def test_rejects_empty_executable(self) -> None:
        with TemporaryProject() as project:
            config = read_json(project.root / "harness" / "config.json")
            config["commands"]["verify"][0]["argv"] = [""]
            errors = harnessctl.validate_config(config, project.root)
            self.assertTrue(any("argv must be" in item for item in errors))

    def test_rejects_out_of_repository_cwd(self) -> None:
        with TemporaryProject() as project:
            config = read_json(project.root / "harness" / "config.json")
            config["commands"]["verify"][0]["cwd"] = "../outside"
            errors = harnessctl.validate_config(config, project.root)
            self.assertTrue(any("escapes the Git root" in item for item in errors))

    def test_rejects_invalid_timeout(self) -> None:
        with TemporaryProject() as project:
            config = read_json(project.root / "harness" / "config.json")
            config["commands"]["verify"][0]["timeout_seconds"] = 0
            errors = harnessctl.validate_config(config, project.root)
            self.assertTrue(any("timeout_seconds" in item for item in errors))

    def test_rejects_secret_like_environment_key(self) -> None:
        with TemporaryProject() as project:
            config = read_json(project.root / "harness" / "config.json")
            config["commands"]["verify"][0]["env"] = {"API_TOKEN": "bad"}
            errors = harnessctl.validate_config(config, project.root)
            self.assertTrue(any("secret-like" in item for item in errors))

    def test_doctor_rejects_missing_verification_commands(self) -> None:
        with TemporaryProject() as project:
            config = read_json(project.root / "harness" / "config.json")
            config["commands"]["verify"] = []
            write_json(project.root / "harness" / "config.json", config)
            result = harnessctl.doctor(project.root)
            check = next(item for item in result["checks"] if item["name"] == "verification_commands")
            self.assertFalse(check["ok"])


class TestCommandExecution(unittest.TestCase):
    """Execute real structured subprocesses without shell semantics."""

    def test_environment_and_relative_cwd_are_applied(self) -> None:
        with TemporaryProject() as project:
            subdir = project.root / "subdir"
            subdir.mkdir()
            script = subdir / "check.py"
            script.write_text(
                "import os,pathlib,sys\n"
                "ok=os.environ.get('HARNESS_FIXTURE')=='yes' and pathlib.Path.cwd().name=='subdir'\n"
                "raise SystemExit(0 if ok else 7)\n",
                encoding="utf-8",
            )
            config = read_json(project.root / "harness" / "config.json")
            config["commands"]["bootstrap"] = [{
                "name": "environment",
                "argv": [sys.executable, "check.py"],
                "cwd": "subdir",
                "env": {"HARNESS_FIXTURE": "yes"},
                "timeout_seconds": 10,
            }]
            write_json(project.root / "harness" / "config.json", config)
            evidence, code = harnessctl.run_command_group(project.root, "bootstrap")
            self.assertEqual(code, 0)
            self.assertTrue(evidence["success"])

    def test_steps_run_sequentially_and_fail_fast(self) -> None:
        with TemporaryProject() as project:
            marker = project.root / "third-ran"
            config = read_json(project.root / "harness" / "config.json")
            config["commands"]["bootstrap"] = [
                {"name": "first", "argv": [sys.executable, "-c", "pass"], "cwd": ".", "env": {}, "timeout_seconds": 10},
                {"name": "second", "argv": [sys.executable, "-c", "raise SystemExit(9)"], "cwd": ".", "env": {}, "timeout_seconds": 10},
                {"name": "third", "argv": [sys.executable, "-c", f"open({str(marker)!r},'w').write('x')"], "cwd": ".", "env": {}, "timeout_seconds": 10},
            ]
            write_json(project.root / "harness" / "config.json", config)
            evidence, code = harnessctl.run_command_group(project.root, "bootstrap")
            self.assertEqual(code, 9)
            self.assertEqual([item["name"] for item in evidence["steps"]], ["first", "second"])
            self.assertFalse(marker.exists())

    def test_timeout_is_recorded(self) -> None:
        with TemporaryProject() as project:
            config = read_json(project.root / "harness" / "config.json")
            config["commands"]["bootstrap"] = [{
                "name": "timeout",
                "argv": [sys.executable, "-c", "import time; time.sleep(5)"],
                "cwd": ".",
                "env": {},
                "timeout_seconds": 1,
            }]
            write_json(project.root / "harness" / "config.json", config)
            evidence, code = harnessctl.run_command_group(project.root, "bootstrap")
            self.assertEqual(code, 124)
            self.assertTrue(evidence["steps"][0]["timed_out"])

    def test_verification_evidence_omits_full_output(self) -> None:
        with TemporaryProject() as project:
            config = read_json(project.root / "harness" / "config.json")
            config["commands"]["verify"] = [{
                "name": "quiet-metadata",
                "argv": [sys.executable, "-c", "print('SENSITIVE_OUTPUT')"],
                "cwd": ".",
                "env": {},
                "timeout_seconds": 10,
            }]
            write_json(project.root / "harness" / "config.json", config)
            evidence, code = harnessctl.run_command_group(project.root, "verify")
            self.assertEqual(code, 0)
            serialized = json.dumps(evidence)
            self.assertNotIn("SENSITIVE_OUTPUT", serialized)
            self.assertNotIn("stdout", serialized)


if __name__ == "__main__":
    unittest.main()
