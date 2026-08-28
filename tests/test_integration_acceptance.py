"""One complete disposable-repository acceptance workflow."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.support import TemporaryProject
from tests.support import git
from tests.support import harnessctl
from tests.support import implement_fixture
from tests.support import read_json
from tests.support import reviewer_payload
from tests.support import valid_spec
from tests.support import write_json


class TestIntegrationAcceptance(unittest.TestCase):
    """Prove the intended two-turn SDD flow with real Git and subprocesses."""

    def test_failed_verify_change_request_then_approval_and_completion(self) -> None:
        with TemporaryProject() as project:
            doctor = harnessctl.doctor(project.root)
            self.assertTrue(doctor["ok"])

            valid_spec(project.root)
            harnessctl.transition_spec_ready(project.root, "example_feature")
            project.commit_all("spec: reviewed fixture feature")
            approved = harnessctl.approve_feature(project.root, "example_feature")
            self.assertEqual(approved["approval"]["baseline"], git(project.root, "rev-parse", "HEAD").stdout.strip())

            implement_fixture(project, passing=False)
            _, failed_code = harnessctl.run_command_group(project.root, "verify")
            self.assertNotEqual(failed_code, 0)
            with self.assertRaises(harnessctl.HarnessError):
                harnessctl.complete_feature(project.root, "example_feature")

            fingerprint = implement_fixture(project, passing=True)
            passed, passed_code = harnessctl.run_command_group(project.root, "verify")
            self.assertEqual(passed_code, 0)
            self.assertEqual(passed["implementation_fingerprint"], fingerprint)

            review_input = Path(project._temporary.name) / "review.json"
            write_json(review_input, reviewer_payload(fingerprint, "CHANGES_REQUESTED"))
            harnessctl.record_review(project.root, "example_feature", review_input)
            with self.assertRaises(harnessctl.HarnessError):
                harnessctl.complete_feature(project.root, "example_feature")

            write_json(review_input, reviewer_payload(fingerprint, "APPROVED"))
            harnessctl.record_review(project.root, "example_feature", review_input)
            completed = harnessctl.complete_feature(project.root, "example_feature")
            self.assertEqual(completed["status"], "done")
            final = read_json(project.root / "harness" / "features.json")["features"][0]
            self.assertEqual(final["status"], "done")


if __name__ == "__main__":
    unittest.main()
