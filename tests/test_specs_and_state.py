"""Strict spec parsing and feature-state invariant tests."""
from __future__ import annotations

import unittest

from tests.support import TemporaryProject
from tests.support import harnessctl
from tests.support import read_json
from tests.support import valid_spec
from tests.support import write_json


class TestStrictEars(unittest.TestCase):
    """Enforce stable IDs and one strict English EARS obligation."""

    def test_accepts_all_five_ears_forms(self) -> None:
        text = """# Requirements

## R1
The system MUST persist the value.

## R2
WHEN a request arrives, the system MUST validate it.

## R3
WHILE maintenance is active, the system MUST reject writes.

## R4
WHERE caching is enabled, the system MUST reuse the result.

## R5
IF validation fails THEN the system MUST return an error.
"""
        requirements, errors = harnessctl.parse_requirements(text)
        self.assertEqual(errors, [])
        self.assertEqual([item["id"] for item in requirements], ["R1", "R2", "R3", "R4", "R5"])

    def test_rejects_non_sequential_ids(self) -> None:
        _, errors = harnessctl.parse_requirements("## R2\n\nThe system MUST work.\n")
        self.assertTrue(any("expected R1" in item for item in errors))

    def test_rejects_multiple_obligations(self) -> None:
        _, errors = harnessctl.parse_requirements("## R1\n\nThe system MUST work and MUST persist.\n")
        self.assertTrue(any("exactly one" in item for item in errors))

    def test_rejects_soft_obligation(self) -> None:
        _, errors = harnessctl.parse_requirements("## R1\n\nThe system MUST work and SHOULD log.\n")
        self.assertTrue(any("soft obligation" in item for item in errors))

    def test_rejects_invalid_ears_sentence(self) -> None:
        _, errors = harnessctl.parse_requirements("## R1\n\nUsers MUST get a value.\n")
        self.assertTrue(any("strict English EARS" in item for item in errors))


class TestSpecValidation(unittest.TestCase):
    """Validate all three spec artifacts and mappings."""

    def test_valid_spec_maps_acceptance_and_tasks(self) -> None:
        with TemporaryProject(acceptance=["one", "two"]) as project:
            valid_spec(project.root, acceptance_count=2)
            feature = read_json(project.root / "harness" / "features.json")["features"][0]
            parsed, errors = harnessctl.validate_spec(project.root, feature)
            self.assertEqual(errors, [])
            self.assertEqual(parsed["tasks"][0]["requirements"], ["R1"])

    def test_rejects_unmapped_acceptance(self) -> None:
        with TemporaryProject(acceptance=["one", "two"]) as project:
            valid_spec(project.root, acceptance_count=1)
            feature = read_json(project.root / "harness" / "features.json")["features"][0]
            _, errors = harnessctl.validate_spec(project.root, feature)
            self.assertTrue(any("A2" in item for item in errors))

    def test_rejects_unknown_task_requirement(self) -> None:
        with TemporaryProject() as project:
            valid_spec(project.root)
            tasks = project.root / "harness" / "specs" / "example_feature" / "tasks.md"
            tasks.write_text("- [ ] T1 — Broken reference. Covers: R9.\n", encoding="utf-8")
            feature = read_json(project.root / "harness" / "features.json")["features"][0]
            _, errors = harnessctl.validate_spec(project.root, feature)
            self.assertTrue(any("unknown requirements" in item for item in errors))

    def test_rejects_missing_design_alternative(self) -> None:
        with TemporaryProject() as project:
            valid_spec(project.root)
            design = project.root / "harness" / "specs" / "example_feature" / "design.md"
            design.write_text("x" * 120, encoding="utf-8")
            feature = read_json(project.root / "harness" / "features.json")["features"][0]
            _, errors = harnessctl.validate_spec(project.root, feature)
            self.assertTrue(any("rejected alternative" in item for item in errors))


class TestFeatureSchema(unittest.TestCase):
    """Enforce deterministic feature identities and coherent states."""

    def test_rejects_duplicate_ids_and_names(self) -> None:
        with TemporaryProject() as project:
            data = read_json(project.root / "harness" / "features.json")
            data["features"].append(dict(data["features"][0]))
            errors = harnessctl.validate_features(data, project.root)
            self.assertTrue(any("Duplicate feature id" in item for item in errors))
            self.assertTrue(any("Duplicate feature name" in item for item in errors))

    def test_rejects_more_than_one_in_progress(self) -> None:
        with TemporaryProject() as project:
            data = read_json(project.root / "harness" / "features.json")
            first = data["features"][0]
            first["status"] = "in_progress"
            first["approval"] = {"digest": "x", "approved_at": "now", "baseline": "head"}
            second = dict(first, id=2, name="second_feature")
            data["features"].append(second)
            errors = harnessctl.validate_features(data, project.root)
            self.assertTrue(any("At most one" in item for item in errors))

    def test_nonlegacy_active_feature_requires_specs(self) -> None:
        with TemporaryProject() as project:
            data = read_json(project.root / "harness" / "features.json")
            data["features"][0]["status"] = "spec_ready"
            errors = harnessctl.validate_features(data, project.root)
            self.assertTrue(any("Missing spec file" in item for item in errors))

    def test_legacy_feature_does_not_require_specs(self) -> None:
        with TemporaryProject() as project:
            data = read_json(project.root / "harness" / "features.json")
            feature = data["features"][0]
            feature["sdd"] = False
            feature["status"] = "done"
            errors = harnessctl.validate_features(data, project.root)
            self.assertEqual(errors, [])

    def test_blocked_feature_requires_valid_block_metadata(self) -> None:
        with TemporaryProject() as project:
            data = read_json(project.root / "harness" / "features.json")
            data["features"][0]["status"] = "blocked"
            errors = harnessctl.validate_features(data, project.root)
            self.assertTrue(any("block is required" in item for item in errors))

    def test_rejects_nonexistent_approval_baseline(self) -> None:
        with TemporaryProject() as project:
            valid_spec(project.root)
            data = read_json(project.root / "harness" / "features.json")
            feature = data["features"][0]
            feature["status"] = "in_progress"
            feature["approval"] = {
                "digest": "x" * 64,
                "approved_at": "2026-01-01T00:00:00Z",
                "baseline": "0" * 40,
            }
            errors = harnessctl.validate_features(data, project.root)
            self.assertTrue(any("existing commit" in item for item in errors))


class TestDigest(unittest.TestCase):
    """Approval scope remains stable only for permitted normalization."""

    def test_digest_is_stable_across_crlf_and_checkbox_changes(self) -> None:
        with TemporaryProject() as project:
            valid_spec(project.root)
            feature = read_json(project.root / "harness" / "features.json")["features"][0]
            initial = harnessctl.canonical_spec_digest(project.root, feature)
            for path in harnessctl.spec_paths(project.root, feature):
                text = path.read_text(encoding="utf-8").replace("\n", "\r\n")
                if path.name == "tasks.md":
                    text = text.replace("[ ]", "[X]")
                path.write_bytes(text.encode("utf-8"))
            self.assertEqual(initial, harnessctl.canonical_spec_digest(project.root, feature))

    def test_digest_changes_after_requirement_design_or_task_text(self) -> None:
        for filename in ("requirements.md", "design.md", "tasks.md"):
            with self.subTest(filename=filename), TemporaryProject() as project:
                valid_spec(project.root)
                feature = read_json(project.root / "harness" / "features.json")["features"][0]
                initial = harnessctl.canonical_spec_digest(project.root, feature)
                path = project.root / "harness" / "specs" / "example_feature" / filename
                path.write_text(path.read_text(encoding="utf-8") + "\nchanged text\n", encoding="utf-8")
                self.assertNotEqual(initial, harnessctl.canonical_spec_digest(project.root, feature))


if __name__ == "__main__":
    unittest.main()
