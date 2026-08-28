"""Shared temporary-repository helpers for harness tests."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import uuid
from pathlib import Path
from types import ModuleType
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = REPOSITORY_ROOT / "template"
HARNESSCTL_PATH = TEMPLATE_ROOT / "harness" / "scripts" / "harnessctl.py"
PRIVATE_TEST_ROOT = REPOSITORY_ROOT / "private"
PRIVATE_TEST_ROOT.mkdir(exist_ok=True)


class LocalTemporaryDirectory:
    """Workspace-local temporary directory without Windows tempfile ACL changes."""

    def __init__(self) -> None:
        self.path = PRIVATE_TEST_ROOT / f"harness-test-{uuid.uuid4().hex}"
        self.path.mkdir()
        self.name = str(self.path)

    def cleanup(self) -> None:
        """Remove the exact isolated test directory."""
        def make_writable(function: Any, path: str, error_info: object) -> None:
            del error_info
            os.chmod(path, stat.S_IWRITE)
            function(path)

        shutil.rmtree(self.path, onerror=make_writable)


def load_harnessctl() -> ModuleType:
    """Import the canonical template control plane without copying it."""
    spec = importlib.util.spec_from_file_location("canonical_harnessctl", HARNESSCTL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load canonical harnessctl.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harnessctl = load_harnessctl()


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run Git in a test repository."""
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        encoding="utf-8",
        capture_output=True,
        shell=False,
        check=check,
    )


def write_json(path: Path, value: Any) -> None:
    """Write stable test JSON."""
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object in a test."""
    return json.loads(path.read_text(encoding="utf-8"))


def valid_spec(root: Path, name: str = "example_feature", acceptance_count: int = 1) -> None:
    """Create one structurally valid strict-EARS spec."""
    spec_root = root / "harness" / "specs" / name
    spec_root.mkdir(parents=True, exist_ok=True)
    mappings = ", ".join(f"A{index}" for index in range(1, acceptance_count + 1))
    mapping_line = f"\nAcceptance: {mappings}\n" if mappings else "\n"
    (spec_root / "requirements.md").write_text(
        "# Requirements\n\n## R1\n\n"
        "WHEN the user requests the fixture value, the system MUST print `ready`.\n"
        f"{mapping_line}",
        encoding="utf-8",
    )
    (spec_root / "design.md").write_text(
        "# Design\n\nThe fixture adds a tiny application entry point and a standard-library test. "
        "The verification command invokes unittest without a shell. Errors propagate as a "
        "non-zero process exit. The rejected alternative was adding an external test framework, "
        "because the harness must remain dependency-free.\n",
        encoding="utf-8",
    )
    (spec_root / "tasks.md").write_text(
        "# Tasks\n\n- [ ] T1 — Add the fixture and its test. Covers: R1.\n",
        encoding="utf-8",
    )


class TemporaryProject:
    """Context manager for a configured copy of the distributable template."""

    def __init__(self, *, acceptance: list[str] | None = None) -> None:
        self._temporary = LocalTemporaryDirectory()
        self.root = Path(self._temporary.name) / "project"
        shutil.copytree(
            TEMPLATE_ROOT,
            self.root,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
        config = read_json(self.root / "harness" / "config.json")
        config["project"]["name"] = "fixture"
        config["commands"]["verify"] = [
            {
                "name": "fixture-tests",
                "argv": [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                "cwd": ".",
                "env": {"PYTHONDONTWRITEBYTECODE": "1"},
                "timeout_seconds": 30,
            }
        ]
        write_json(self.root / "harness" / "config.json", config)
        features = read_json(self.root / "harness" / "features.json")
        features["project"] = "fixture"
        features["features"][0]["acceptance"] = acceptance or ["The fixture prints ready."]
        write_json(self.root / "harness" / "features.json", features)
        (self.root / "tests").mkdir()
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.email", "tests@example.invalid")
        git(self.root, "config", "user.name", "Harness Tests")
        git(self.root, "add", "--", ".")
        git(self.root, "commit", "-m", "initial template")

    def commit_all(self, message: str) -> None:
        """Commit all fixture changes for an explicit test checkpoint."""
        git(self.root, "add", "--", ".")
        git(self.root, "commit", "-m", message)

    def close(self) -> None:
        """Clean up the temporary repository."""
        self._temporary.cleanup()

    def __enter__(self) -> "TemporaryProject":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


def approve_fixture(project: TemporaryProject) -> dict[str, Any]:
    """Create, validate, commit, and approve the fixture spec."""
    valid_spec(project.root)
    harnessctl.transition_spec_ready(project.root, "example_feature")
    project.commit_all("spec: approve fixture scope")
    return harnessctl.approve_feature(project.root, "example_feature")


def implement_fixture(project: TemporaryProject, *, passing: bool = True) -> str:
    """Create fixture implementation, tests, completed task, and traceability."""
    (project.root / "fixture_app.py").write_text(
        "def value():\n    return 'ready'\n" if passing else "def value():\n    return 'wrong'\n",
        encoding="utf-8",
    )
    (project.root / "tests" / "test_fixture.py").write_text(
        "import unittest\n\nfrom fixture_app import value\n\n"
        "class TestFixture(unittest.TestCase):\n"
        "    def test_value_is_ready(self):\n"
        "        self.assertEqual(value(), 'ready')\n",
        encoding="utf-8",
    )
    tasks = project.root / "harness" / "specs" / "example_feature" / "tasks.md"
    tasks.write_text(tasks.read_text(encoding="utf-8").replace("[ ]", "[x]"), encoding="utf-8")
    report = project.root / "harness" / "progress" / "impl_example_feature.md"
    report.write_text("# Implementation\n\n## Traceability\n\n- R1 → `tests/test_fixture.py::TestFixture::test_value_is_ready`\n", encoding="utf-8")
    baseline = read_json(project.root / "harness" / "features.json")["features"][0]["approval"]["baseline"]
    return harnessctl.implementation_fingerprint(project.root, baseline)


def reviewer_payload(fingerprint: str, verdict: str = "APPROVED") -> dict[str, Any]:
    """Build a valid reviewer result."""
    approved = verdict == "APPROVED"
    return {
        "schema_version": 1,
        "feature": "example_feature",
        "implementation_fingerprint": fingerprint,
        "verdict": verdict,
        "requirements": [
            {"id": "R1", "covered": approved, "evidence": "tests/test_fixture.py" if approved else "missing"}
        ],
        "tasks_complete": approved,
        "checkpoints": [{"name": "scope", "passed": approved}],
        "findings": [] if approved else [{"path": "fixture_app.py", "remediation": "Return ready."}],
    }
