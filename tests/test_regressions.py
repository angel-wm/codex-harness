"""Regressions for repository-local hooks and mandatory review checkpoints."""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from tests.support import TemporaryProject, approve_fixture, implement_fixture
from tests.support import git, harnessctl, read_json, reviewer_payload, write_json


class TestRegressions(unittest.TestCase):
    def run_configured_hook(self, project, event, cwd, shell):
        handler = read_json(project.root / ".codex" / "hooks.json")["hooks"][event["hook_event_name"]][0]["hooks"][0]
        command = handler["commandWindows" if os.name == "nt" else "command"]
        # cmd.exe parses a command string; list2cmdline's escaped inner quotes
        # follow the C runtime convention and would change the Python -c code.
        arguments = f'cmd /d /s /c "{command}"' if shell[0] == "cmd" else [*shell, command]
        result = subprocess.run(
            arguments, cwd=cwd, input=json.dumps(event),
            text=True, encoding="utf-8", capture_output=True, check=False, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def check_configured_hooks(self, shells):
        with TemporaryProject() as project:
            spaced_root = project.root.with_name("project with spaces")
            project.root.rename(spaced_root)
            project.root = spaced_root
            for shell in shells:
                for cwd in (project.root, project.root / "harness" / "docs"):
                    for name in ("PostToolUse", "Stop"):
                        with self.subTest(shell=shell[0], cwd=cwd, event=name):
                            self.assertEqual(self.run_configured_hook(
                                project, {"hook_event_name": name}, cwd, shell,
                            ), {})
            features = read_json(project.root / "harness" / "features.json")
            features["features"][0]["status"] = "invalid"
            write_json(project.root / "harness" / "features.json", features)
            for shell in shells:
                for name in ("PostToolUse", "Stop"):
                    output = self.run_configured_hook(
                        project, {"hook_event_name": name}, project.root / "harness" / "docs", shell,
                    )
                    self.assertEqual(output["decision"], "block")
                output = self.run_configured_hook(
                    project, {"hook_event_name": "Stop", "stop_hook_active": True},
                    project.root / "harness" / "docs", shell,
                )
                self.assertNotIn("decision", output)
                self.assertIn("systemMessage", output)

    @unittest.skipUnless(os.name == "nt", "Windows hook command requires Windows")
    def test_configured_windows_hooks_from_root_and_subdirectory_with_spaces(self):
        self.check_configured_hooks([
            ["cmd", "/d", "/s", "/c"],
            ["powershell", "-NoProfile", "-Command"],
        ])

    @unittest.skipUnless(os.name != "nt" and shutil.which("sh"), "POSIX hook command requires native POSIX")
    def test_configured_posix_hooks_from_root_and_subdirectory_with_spaces(self):
        self.check_configured_hooks([["sh", "-c"]])

    def test_review_rejects_omitted_mandatory_checkpoint(self):
        with TemporaryProject() as project:
            approve_fixture(project)
            fingerprint = implement_fixture(project)
            payload = reviewer_payload(fingerprint)
            payload["checkpoints"] = payload["checkpoints"][:1]
            path = Path(project._temporary.name) / "review.json"
            write_json(path, payload)
            with self.assertRaisesRegex(harnessctl.HarnessError, "every checkpoint exactly once"):
                harnessctl.record_review(project.root, "example_feature", path)

    def test_review_rejects_invalid_checkpoint_payloads_without_recording(self):
        with TemporaryProject() as project:
            approve_fixture(project)
            fingerprint = implement_fixture(project)
            path = Path(project._temporary.name) / "review.json"
            for verdict in ("APPROVED", "CHANGES_REQUESTED"):
                base = reviewer_payload(fingerprint, verdict)
                cases = {
                    "omitted": base["checkpoints"][:-1],
                    "duplicate": base["checkpoints"] + [base["checkpoints"][0]],
                    "unknown": base["checkpoints"] + [{"name": "scope", "passed": True}],
                    "non-object": [None],
                    "non-string name": [{"name": [], "passed": True}],
                    "empty name": [{"name": " ", "passed": True}],
                    "missing passed": [{"name": base["checkpoints"][0]["name"]}],
                    "non-boolean passed": [{"name": base["checkpoints"][0]["name"], "passed": 1}],
                    "non-array": {},
                    "empty array": [],
                }
                for label, checkpoints in cases.items():
                    with self.subTest(verdict=verdict, case=label):
                        payload = copy.deepcopy(base)
                        payload["checkpoints"] = checkpoints
                        write_json(path, payload)
                        with self.assertRaises(harnessctl.HarnessError):
                            harnessctl.record_review(project.root, "example_feature", path)
                self.assertFalse((project.root / "harness" / "progress" / "reviews" / "example_feature.json").exists())
                self.assertEqual(read_json(project.root / "harness" / "features.json")["features"][0]["review_cycles"], 0)

    def test_review_uses_custom_repository_checkpoints(self):
        with TemporaryProject() as project:
            approve_fixture(project)
            (project.root / "harness" / "checkpoints.md").write_text(
                "# Project controls\n\n- [ ] Custom project check.\n- [x] Another check with `markup`.\n",
                encoding="utf-8",
            )
            fingerprint = implement_fixture(project)
            payload = reviewer_payload(fingerprint, root=project.root)
            payload["checkpoints"].reverse()
            path = Path(project._temporary.name) / "review.json"
            write_json(path, payload)
            review = harnessctl.record_review(project.root, "example_feature", path)
            self.assertEqual(review["verdict"], "APPROVED")
            self.assertEqual({entry["name"] for entry in review["checkpoints"]}, {
                "Custom project check.", "Another check with `markup`.",
            })

    def test_review_rejects_missing_empty_duplicate_or_malformed_catalog(self):
        with TemporaryProject() as project:
            approve_fixture(project)
            catalog = project.root / "harness" / "checkpoints.md"
            path = Path(project._temporary.name) / "review.json"
            payload = reviewer_payload(implement_fixture(project))
            cases = (None, "# No controls\n", "- [ ] Same\n- [ ] Same\n", "- [ ] \n", "- [yes] Bad\n", "- Missing checkbox\n")
            for text in cases:
                with self.subTest(catalog=text):
                    if text is None:
                        catalog.unlink()
                    else:
                        catalog.write_text(text, encoding="utf-8")
                    baseline = read_json(project.root / "harness" / "features.json")["features"][0]["approval"]["baseline"]
                    payload["implementation_fingerprint"] = harnessctl.implementation_fingerprint(project.root, baseline)
                    write_json(path, payload)
                    with self.assertRaisesRegex(harnessctl.HarnessError, "checkpoints.md"):
                        harnessctl.record_review(project.root, "example_feature", path)

    def test_completion_rechecks_stored_checkpoint_coverage(self):
        with TemporaryProject() as project:
            approve_fixture(project)
            fingerprint = implement_fixture(project)
            _, code = harnessctl.run_command_group(project.root, "verify")
            self.assertEqual(code, 0)
            path = Path(project._temporary.name) / "review.json"
            write_json(path, reviewer_payload(fingerprint))
            harnessctl.record_review(project.root, "example_feature", path)
            stored = project.root / "harness" / "progress" / "reviews" / "example_feature.json"
            payload = read_json(stored)
            payload["checkpoints"].pop()
            write_json(stored, payload)
            with self.assertRaisesRegex(harnessctl.HarnessError, "every checkpoint exactly once"):
                harnessctl.complete_feature(project.root, "example_feature")
            self.assertEqual(read_json(project.root / "harness" / "features.json")["features"][0]["status"], "in_progress")

    def stop(self, project):
        result = subprocess.run(
            [sys.executable, str(project.root / "harness" / "scripts" / "codex_hook.py")],
            cwd=project.root, input=json.dumps({"hook_event_name": "Stop"}),
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def configure_counting_verification(self, project, *, exit_code=0):
        config = read_json(project.root / "harness" / "config.json")
        marker = project.root / "harness" / "progress" / "reviews" / "verify-count"
        marker.parent.mkdir(exist_ok=True)
        config["commands"]["verify"] = [{
            "name": "count-runs",
            "argv": [sys.executable, "-c", f"from pathlib import Path; p=Path({str(marker)!r}); p.write_text((p.read_text() if p.exists() else '')+'x'); raise SystemExit({exit_code})"],
            "cwd": ".", "env": {}, "timeout_seconds": 10,
        }]
        write_json(project.root / "harness" / "config.json", config)
        return marker

    def test_stop_verifies_untracked_staged_committed_deleted_and_config_changes(self):
        for kind in ("untracked", "staged", "committed", "deleted", "config"):
            with self.subTest(change=kind), TemporaryProject() as project:
                marker = self.configure_counting_verification(project)
                approve_fixture(project)
                if kind == "deleted":
                    (project.root / "AGENTS.md").unlink()
                elif kind == "config":
                    config = read_json(project.root / "harness" / "config.json")
                    config["git"]["commit_message"] = "updated({feature_name}): {feature_title}"
                    write_json(project.root / "harness" / "config.json", config)
                else:
                    (project.root / "implementation.txt").write_text("changed", encoding="utf-8")
                    if kind == "staged":
                        git(project.root, "add", "--", "implementation.txt")
                    elif kind == "committed":
                        project.commit_all("fixture implementation")
                output = self.stop(project)
                self.assertIn("verification passed", output.get("systemMessage", ""), output)
                self.assertEqual(marker.read_text(), "x")
                self.assertEqual(self.stop(project), {})
                self.assertEqual(marker.read_text(), "x")

    def test_stop_preserves_failed_verification_without_implementation_changes(self):
        with TemporaryProject() as project:
            marker = self.configure_counting_verification(project, exit_code=1)
            approve_fixture(project)
            _, code = harnessctl.run_command_group(project.root, "verify")
            self.assertEqual(code, 1)
            self.assertEqual(self.stop(project)["decision"], "block")
            self.assertEqual(marker.read_text(), "xx")

    def test_stop_still_validates_state_before_skipping_verification(self):
        with TemporaryProject() as project:
            marker = self.configure_counting_verification(project)
            approve_fixture(project)
            features = read_json(project.root / "harness" / "features.json")
            features["features"][0]["status"] = "invalid"
            write_json(project.root / "harness" / "features.json", features)
            self.assertEqual(self.stop(project)["decision"], "block")
            self.assertFalse(marker.exists())

    def test_stop_skips_verification_immediately_after_approval(self):
        with TemporaryProject() as project:
            approve_fixture(project)
            self.assertFalse((project.root / "harness" / "progress" / "verification.json").exists())
            self.assertEqual(self.stop(project), {})
            self.assertFalse((project.root / "harness" / "progress" / "verification.json").exists())
            with self.assertRaises(harnessctl.HarnessError):
                harnessctl.complete_feature(project.root, "example_feature")


if __name__ == "__main__":
    unittest.main()
