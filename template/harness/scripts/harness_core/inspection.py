"""Repository inspection, structural validation, and status reporting."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any, Iterable

from .repository import HarnessError, git_is_clean, implementation_fingerprint, json_load, paths, run_git
from .runner import select_argv
from .specs import approval_is_current
from .state import SCHEMA_VERSION, load_state, validate_config, validate_features


REQUIRED_TEMPLATE_PATHS = (
    "AGENTS.md",
    ".agents/skills/sdd-workflow/SKILL.md",
    ".codex/config.toml",
    ".codex/hooks.json",
    ".codex/agents/sdd-spec-author.toml",
    ".codex/agents/sdd-implementer.toml",
    ".codex/agents/sdd-reviewer.toml",
    "harness/config.json",
    "harness/features.json",
    "harness/checkpoints.md",
    "harness/docs/architecture.md",
    "harness/docs/conventions.md",
    "harness/docs/sdd.md",
    "harness/docs/verification.md",
    "harness/progress/current.md",
    "harness/progress/history.md",
    "harness/scripts/harnessctl.py",
    "harness/scripts/codex_hook.py",
)


def validate_repository(root: Path) -> dict[str, Any]:
    """Perform fast structural checks without running target verification."""
    config = json_load(paths(root)["config"])
    features = json_load(paths(root)["features"])
    errors = validate_config(config, root) + validate_features(features, root)
    if errors:
        raise HarnessError("Harness validation failed:\n- " + "\n- ".join(errors))
    return {"valid": True, "feature_count": len(features["features"])}


def doctor(root: Path) -> dict[str, Any]:
    """Check prerequisites, completeness, schemas, and configured executables."""
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    add("python", sys.version_info >= (3, 11), f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    add("git", shutil.which("git") is not None, shutil.which("git") or "not found")
    missing = [item for item in REQUIRED_TEMPLATE_PATHS if not (root / item).is_file()]
    add("required_files", not missing, "complete" if not missing else "missing: " + ", ".join(missing))
    try:
        config, features = load_state(root)
        add("schemas", True, f"{len(features['features'])} feature(s)")
        project_names = (config["project"]["name"], features["project"])
        configured = all(name != "REPLACE_ME" for name in project_names) and project_names[0] == project_names[1]
        add("project_configuration", configured, "configured" if configured else "replace placeholders with one matching project name")
        verify_steps = config["commands"]["verify"]
        add("verification_commands", bool(verify_steps), f"{len(verify_steps)} configured")
        for group in ("bootstrap", "verify"):
            for step in config["commands"][group]:
                executable = select_argv(step)[0]
                resolved = shutil.which(executable)
                add(f"executable:{group}:{step['name']}", resolved is not None, resolved or f"not found: {executable}")
    except HarnessError as exc:
        add("schemas", False, str(exc))
    head = run_git(root, ["rev-parse", "--verify", "HEAD"], check=False)
    add("git_head", head.returncode == 0, head.stdout.strip() or head.stderr.strip())
    return {"ok": all(item["ok"] for item in checks), "checks": checks}


def status_payload(root: Path) -> dict[str, Any]:
    """Report deterministic workflow status and gate freshness."""
    config, features_data = load_state(root)
    ordered = sorted(features_data["features"], key=lambda item: item["id"])
    active = next((item for item in ordered if item["status"] == "in_progress"), None)
    pending = next((item for item in ordered if item["status"] == "pending"), None)
    actionable = next((item for item in ordered if item["status"] in {"pending", "spec_ready", "in_progress", "blocked"}), None)
    verification = None
    if paths(root)["verification"].is_file():
        verification = json_load(paths(root)["verification"])
    latest_review = None
    if active:
        review_path = paths(root)["reviews"] / f"{active['name']}.json"
        if review_path.is_file():
            latest_review = json_load(review_path)
    fingerprint = None
    if active and isinstance(active.get("approval"), dict):
        fingerprint = implementation_fingerprint(root, active["approval"]["baseline"])
    return {
        "schema_version": SCHEMA_VERSION,
        "project": config["project"]["name"],
        "active_feature": active,
        "next_pending_feature": pending,
        "next_actionable_feature": actionable,
        "worktree_clean": git_is_clean(root),
        "approval_current": approval_is_current(root, active) if active else None,
        "implementation_fingerprint": fingerprint,
        "verification": verification,
        "latest_review": latest_review,
    }


def print_status(payload: dict[str, Any]) -> None:
    """Print a concise human-readable status."""
    active = payload["active_feature"]
    actionable = payload["next_actionable_feature"]
    print(f"Project: {payload['project']}")
    print(f"Active feature: {active['name'] if active else 'none'}")
    print(f"Next actionable: {actionable['name'] if actionable else 'none'}")
    print(f"Worktree clean: {str(payload['worktree_clean']).lower()}")
    if active:
        print(f"Approval current: {str(payload['approval_current']).lower()}")
        print(f"Implementation fingerprint: {payload['implementation_fingerprint']}")
