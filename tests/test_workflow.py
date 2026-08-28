"""Git-backed state transition, freshness, review, and completion tests."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.support import TemporaryProject
from tests.support import approve_fixture
from tests.support import git
from tests.support import harnessctl
from tests.support import implement_fixture
from tests.support import read_json
from tests.support import reviewer_payload
from tests.support import valid_spec
from tests.support import write_json


class TestTransitions(unittest.TestCase):
    """Verify every supported transition and important invalid edge."""

    def test_pending_cannot_approve_directly(self) -> None:
        with TemporaryProject() as project:
            with self.assertRaisesRegex(harnessctl.HarnessError, "spec_ready"):
                harnessctl.approve_feature(project.root, "example_feature")

    def test_spec_ready_requires_specs_and_verification(self) -> None:
        with TemporaryProject() as project:
            config = read_json(project.root / "harness" / "config.json")
            config["commands"]["verify"] = []
            write_json(project.root / "harness" / "config.json", config)
            with self.assertRaisesRegex(harnessctl.HarnessError, "verify command"):
                harnessctl.transition_spec_ready(project.root, "example_feature")

    def test_spec_ready_updates_state_but_not_approval(self) -> None:
        with TemporaryProject() as project:
            valid_spec(project.root)
            result = harnessctl.transition_spec_ready(project.root, "example_feature")
            self.assertEqual(result["status"], "spec_ready")
            self.assertIsNone(result["approval"])

    def test_approval_requires_clean_worktree(self) -> None:
        with TemporaryProject() as project:
            valid_spec(project.root)
            harnessctl.transition_spec_ready(project.root, "example_feature")
            with self.assertRaisesRegex(harnessctl.HarnessError, "clean worktree"):
                harnessctl.approve_feature(project.root, "example_feature")

    def test_approval_records_digest_and_baseline(self) -> None:
        with TemporaryProject() as project:
            result = approve_fixture(project)
            self.assertEqual(result["status"], "in_progress")
            self.assertEqual(len(result["approval"]["digest"]), 64)
            self.assertEqual(result["approval"]["baseline"], git(project.root, "rev-parse", "HEAD").stdout.strip())

    def test_done_is_immutable_through_normal_transitions(self) -> None:
        with TemporaryProject() as project:
            features = read_json(project.root / "harness" / "features.json")
            feature = features["features"][0]
            feature["sdd"] = False
            feature["status"] = "done"
            write_json(project.root / "harness" / "features.json", features)
            for operation in (
                lambda: harnessctl.transition_spec_ready(project.root, "example_feature"),
                lambda: harnessctl.approve_feature(project.root, "example_feature"),
                lambda: harnessctl.block_feature(project.root, "example_feature", "x"),
                lambda: harnessctl.resume_feature(project.root, "example_feature"),
            ):
                with self.assertRaises(harnessctl.HarnessError):
                    operation()

    def test_block_and_resume_restore_prior_state(self) -> None:
        with TemporaryProject() as project:
            approve_fixture(project)
            blocked = harnessctl.block_feature(project.root, "example_feature", "dependency unavailable")
            self.assertEqual(blocked["block"]["prior_status"], "in_progress")
            self.assertEqual(blocked["status"], "blocked")
            resumed = harnessctl.resume_feature(project.root, "example_feature")
            self.assertEqual(resumed["status"], "in_progress")
            self.assertIsNone(resumed["block"])


class TestVerificationAndReview(unittest.TestCase):
    """Keep execution evidence and independent verdicts fingerprint-current."""

    def write_review(self, project: TemporaryProject, payload: dict[str, object]) -> Path:
        temporary = Path(project._temporary.name) / "review.json"
        write_json(temporary, payload)
        return temporary

    def test_failed_verification_blocks_completion(self) -> None:
        with TemporaryProject() as project:
            approve_fixture(project)
            implement_fixture(project, passing=False)
            evidence, code = harnessctl.run_command_group(project.root, "verify")
            self.assertNotEqual(code, 0)
            self.assertFalse(evidence["success"])
            with self.assertRaisesRegex(harnessctl.HarnessError, "verification did not succeed"):
                harnessctl.complete_feature(project.root, "example_feature")

    def test_review_rejects_stale_fingerprint(self) -> None:
        with TemporaryProject() as project:
            approve_fixture(project)
            fingerprint = implement_fixture(project)
            payload = reviewer_payload("0" * 64)
            with self.assertRaisesRegex(harnessctl.HarnessError, "stale"):
                harnessctl.record_review(project.root, "example_feature", self.write_review(project, payload))
            self.assertNotEqual(fingerprint, "0" * 64)

    def test_change_request_is_recorded_and_feature_stays_in_progress(self) -> None:
        with TemporaryProject() as project:
            approve_fixture(project)
            fingerprint = implement_fixture(project)
            review = harnessctl.record_review(
                project.root,
                "example_feature",
                self.write_review(project, reviewer_payload(fingerprint, "CHANGES_REQUESTED")),
            )
            self.assertEqual(review["verdict"], "CHANGES_REQUESTED")
            feature = read_json(project.root / "harness" / "features.json")["features"][0]
            self.assertEqual(feature["status"], "in_progress")
            self.assertEqual(feature["review_cycles"], 1)

    def test_review_cycle_limit_blocks_feature(self) -> None:
        with TemporaryProject() as project:
            approve_fixture(project)
            fingerprint = implement_fixture(project)
            review_path = self.write_review(project, reviewer_payload(fingerprint, "CHANGES_REQUESTED"))
            for _ in range(3):
                harnessctl.record_review(project.root, "example_feature", review_path)
            feature = read_json(project.root / "harness" / "features.json")["features"][0]
            self.assertEqual(feature["status"], "blocked")
            self.assertIn("Review cycle limit", feature["block"]["reason"])

    def test_spec_change_invalidates_approval(self) -> None:
        with TemporaryProject() as project:
            approve_fixture(project)
            requirements = project.root / "harness" / "specs" / "example_feature" / "requirements.md"
            requirements.write_text(requirements.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
            feature = read_json(project.root / "harness" / "features.json")["features"][0]
            self.assertFalse(harnessctl.approval_is_current(project.root, feature))


class TestCompletion(unittest.TestCase):
    """Exercise the full integration acceptance path and rejection gates."""

    def prepare_approved_review(self, project: TemporaryProject) -> str:
        fingerprint = implement_fixture(project)
        evidence, code = harnessctl.run_command_group(project.root, "verify")
        self.assertEqual(code, 0)
        self.assertEqual(evidence["implementation_fingerprint"], fingerprint)
        review_path = Path(project._temporary.name) / "approved-review.json"
        write_json(review_path, reviewer_payload(fingerprint))
        harnessctl.record_review(project.root, "example_feature", review_path)
        return fingerprint

    def test_end_to_end_completion_updates_history_and_resets_current(self) -> None:
        with TemporaryProject() as project:
            approve_fixture(project)
            fingerprint = self.prepare_approved_review(project)
            result = harnessctl.complete_feature(project.root, "example_feature")
            self.assertEqual(result["status"], "done")
            self.assertEqual(result["implementation_fingerprint"], fingerprint)
            feature = read_json(project.root / "harness" / "features.json")["features"][0]
            self.assertEqual(feature["status"], "done")
            self.assertIn("example_feature", (project.root / "harness" / "progress" / "history.md").read_text())
            self.assertIn("_none_", (project.root / "harness" / "progress" / "current.md").read_text())

    def test_incomplete_tasks_reject_completion(self) -> None:
        with TemporaryProject() as project:
            approve_fixture(project)
            fingerprint = implement_fixture(project)
            tasks = project.root / "harness" / "specs" / "example_feature" / "tasks.md"
            tasks.write_text(tasks.read_text(encoding="utf-8").replace("[x]", "[ ]"), encoding="utf-8")
            with self.assertRaisesRegex(harnessctl.HarnessError, "incomplete tasks"):
                harnessctl.complete_feature(project.root, "example_feature")
            self.assertEqual(len(fingerprint), 64)

    def test_missing_traceability_rejects_completion(self) -> None:
        with TemporaryProject() as project:
            approve_fixture(project)
            implement_fixture(project)
            (project.root / "harness" / "progress" / "impl_example_feature.md").unlink()
            with self.assertRaisesRegex(harnessctl.HarnessError, "missing traceability"):
                harnessctl.complete_feature(project.root, "example_feature")

    def test_stale_verification_rejects_completion(self) -> None:
        with TemporaryProject() as project:
            approve_fixture(project)
            self.prepare_approved_review(project)
            (project.root / "fixture_app.py").write_text("def value():\n    return 'changed'\n", encoding="utf-8")
            with self.assertRaisesRegex(harnessctl.HarnessError, "verification is stale"):
                harnessctl.complete_feature(project.root, "example_feature")

    def test_change_request_rejects_completion(self) -> None:
        with TemporaryProject() as project:
            approve_fixture(project)
            fingerprint = implement_fixture(project)
            _, code = harnessctl.run_command_group(project.root, "verify")
            self.assertEqual(code, 0)
            review_path = Path(project._temporary.name) / "changes.json"
            write_json(review_path, reviewer_payload(fingerprint, "CHANGES_REQUESTED"))
            harnessctl.record_review(project.root, "example_feature", review_path)
            with self.assertRaisesRegex(harnessctl.HarnessError, "non-approved"):
                harnessctl.complete_feature(project.root, "example_feature")

    def test_auto_commit_disabled_by_default(self) -> None:
        with TemporaryProject() as project:
            approve_fixture(project)
            self.prepare_approved_review(project)
            before = git(project.root, "rev-parse", "HEAD").stdout.strip()
            harnessctl.complete_feature(project.root, "example_feature")
            after = git(project.root, "rev-parse", "HEAD").stdout.strip()
            self.assertEqual(before, after)
            self.assertNotEqual(git(project.root, "status", "--porcelain").stdout, "")

    def test_opt_in_auto_commit_uses_exact_paths_and_never_pushes(self) -> None:
        with TemporaryProject() as project:
            config = read_json(project.root / "harness" / "config.json")
            config["git"]["auto_commit_on_done"] = True
            write_json(project.root / "harness" / "config.json", config)
            project.commit_all("config: enable fixture auto commit")
            approve_fixture(project)
            self.prepare_approved_review(project)
            result = harnessctl.complete_feature(project.root, "example_feature")
            self.assertEqual(result["status"], "done")
            self.assertEqual(git(project.root, "status", "--porcelain").stdout, "")
            message = git(project.root, "log", "-1", "--pretty=%s").stdout.strip()
            self.assertEqual(message, "feat(example_feature): Example feature")
            self.assertEqual(git(project.root, "remote").stdout, "")

    def test_auto_commit_failure_preserves_completed_work(self) -> None:
        with TemporaryProject() as project:
            config = read_json(project.root / "harness" / "config.json")
            config["git"]["auto_commit_on_done"] = True
            write_json(project.root / "harness" / "config.json", config)
            project.commit_all("config: enable fixture auto commit")
            approve_fixture(project)
            self.prepare_approved_review(project)
            hook = project.root / ".git" / "hooks" / "pre-commit"
            hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            os.chmod(hook, 0o755)
            with self.assertRaisesRegex(harnessctl.HarnessError, "failed non-destructively"):
                harnessctl.complete_feature(project.root, "example_feature")
            feature = read_json(project.root / "harness" / "features.json")["features"][0]
            self.assertEqual(feature["status"], "done")
            self.assertTrue((project.root / "fixture_app.py").is_file())
            self.assertNotEqual(git(project.root, "status", "--porcelain").stdout, "")


if __name__ == "__main__":
    unittest.main()
