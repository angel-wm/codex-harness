"""Configuration, feature schema validation, and validated state loading."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .repository import HarnessError, json_load, paths, run_git
from .specs import validate_spec


SCHEMA_VERSION = 1
VALID_STATES = {"pending", "spec_ready", "in_progress", "done", "blocked"}
BLOCKABLE_STATES = {"pending", "spec_ready", "in_progress"}


def validate_step(step: Any, root: Path, label: str) -> list[str]:
    """Validate one structured command configuration."""
    errors: list[str] = []
    if not isinstance(step, dict):
        return [f"{label} must be an object"]
    if not isinstance(step.get("name"), str) or not step["name"].strip():
        errors.append(f"{label}.name must be a non-empty string")
    variants = ("argv", "windows_argv", "posix_argv")
    available = 0
    for field in variants:
        if field not in step:
            continue
        argv = step[field]
        if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
            errors.append(f"{label}.{field} must be a non-empty string array")
        else:
            available += 1
    if not available:
        errors.append(f"{label} must define argv or a platform-specific argv")
    cwd = step.get("cwd", ".")
    if not isinstance(cwd, str) or not cwd:
        errors.append(f"{label}.cwd must be a non-empty string")
    else:
        try:
            (root / cwd).resolve().relative_to(root.resolve())
        except ValueError:
            errors.append(f"{label}.cwd escapes the Git root")
    environment = step.get("env", {})
    if not isinstance(environment, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in environment.items()
    ):
        errors.append(f"{label}.env must map strings to strings")
    else:
        sensitive = ("SECRET", "TOKEN", "PASSWORD", "API_KEY", "PRIVATE_KEY")
        for key in environment:
            if any(marker in key.upper() for marker in sensitive):
                errors.append(f"{label}.env must not contain secret-like key {key!r}")
    timeout = step.get("timeout_seconds", 600)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 86400:
        errors.append(f"{label}.timeout_seconds must be an integer from 1 to 86400")
    return errors


def validate_config(config: dict[str, Any], root: Path) -> list[str]:
    """Validate the versioned, language-neutral harness configuration."""
    errors: list[str] = []
    if config.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"config.schema_version must equal {SCHEMA_VERSION}")
    project = config.get("project")
    if not isinstance(project, dict) or not isinstance(project.get("name"), str) or not project["name"].strip():
        errors.append("config.project.name must be a non-empty string")
    workflow = config.get("workflow")
    if not isinstance(workflow, dict):
        errors.append("config.workflow must be an object")
    else:
        cycles = workflow.get("max_review_cycles")
        if isinstance(cycles, bool) or not isinstance(cycles, int) or cycles < 1:
            errors.append("config.workflow.max_review_cycles must be a positive integer")
        if not isinstance(workflow.get("require_clean_worktree"), bool):
            errors.append("config.workflow.require_clean_worktree must be a boolean")
    commands = config.get("commands")
    if not isinstance(commands, dict):
        errors.append("config.commands must be an object")
    else:
        for group in ("bootstrap", "verify"):
            steps = commands.get(group)
            if not isinstance(steps, list):
                errors.append(f"config.commands.{group} must be an array")
                continue
            for index, step in enumerate(steps, start=1):
                errors.extend(validate_step(step, root, f"config.commands.{group}[{index}]") )
    git = config.get("git")
    if not isinstance(git, dict):
        errors.append("config.git must be an object")
    else:
        if not isinstance(git.get("auto_commit_on_done"), bool):
            errors.append("config.git.auto_commit_on_done must be a boolean")
        message = git.get("commit_message")
        if not isinstance(message, str) or "{feature_name}" not in message or "{feature_title}" not in message:
            errors.append("config.git.commit_message must contain {feature_name} and {feature_title}")
    return errors


def validate_features(features_data: dict[str, Any], root: Path) -> list[str]:
    """Validate feature schema, state invariants, and required specs."""
    errors: list[str] = []
    if features_data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"features.schema_version must equal {SCHEMA_VERSION}")
    if not isinstance(features_data.get("project"), str) or not features_data["project"].strip():
        errors.append("features.project must be a non-empty string")
    features = features_data.get("features")
    if not isinstance(features, list):
        return errors + ["features.features must be an array"]
    ids: set[int] = set()
    names: set[str] = set()
    active = 0
    for index, feature in enumerate(features, start=1):
        label = f"features[{index}]"
        if not isinstance(feature, dict):
            errors.append(f"{label} must be an object")
            continue
        identifier = feature.get("id")
        if isinstance(identifier, bool) or not isinstance(identifier, int) or identifier <= 0:
            errors.append(f"{label}.id must be a positive integer")
        elif identifier in ids:
            errors.append(f"Duplicate feature id: {identifier}")
        else:
            ids.add(identifier)
        name = feature.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", name):
            errors.append(f"{label}.name must be a filesystem-safe snake_case slug")
        elif name in names:
            errors.append(f"Duplicate feature name: {name}")
        else:
            names.add(name)
        for field in ("title", "description"):
            if not isinstance(feature.get(field), str) or not feature[field].strip():
                errors.append(f"{label}.{field} must be a non-empty string")
        if not isinstance(feature.get("acceptance"), list) or not all(
            isinstance(item, str) and item.strip() for item in feature.get("acceptance", [])
        ):
            errors.append(f"{label}.acceptance must be an array of non-empty strings")
        if not isinstance(feature.get("sdd"), bool):
            errors.append(f"{label}.sdd must be a boolean")
        state = feature.get("status")
        if state not in VALID_STATES:
            errors.append(f"{label}.status must be one of {sorted(VALID_STATES)}")
        if state == "in_progress":
            active += 1
        cycles = feature.get("review_cycles", 0)
        if isinstance(cycles, bool) or not isinstance(cycles, int) or cycles < 0:
            errors.append(f"{label}.review_cycles must be a non-negative integer")
        approval = feature.get("approval")
        if state in {"in_progress", "done"} and feature.get("sdd"):
            if not isinstance(approval, dict):
                errors.append(f"{label}.approval is required in state {state}")
            elif not all(isinstance(approval.get(key), str) and approval[key] for key in ("digest", "approved_at", "baseline")):
                errors.append(f"{label}.approval must contain digest, approved_at, and baseline strings")
        if state in {"pending", "spec_ready"} and approval is not None:
            errors.append(f"{label}.approval must be null in state {state}")
        if isinstance(approval, dict) and isinstance(approval.get("baseline"), str):
            baseline_check = run_git(root, ["cat-file", "-e", f"{approval['baseline']}^{{commit}}"], check=False)
            if baseline_check.returncode != 0:
                errors.append(f"{label}.approval.baseline must identify an existing commit")
        block = feature.get("block")
        if state == "blocked":
            if not isinstance(block, dict):
                errors.append(f"{label}.block is required while blocked")
            elif block.get("prior_status") not in BLOCKABLE_STATES or not all(
                isinstance(block.get(key), str) and block[key] for key in ("reason", "blocked_at")
            ):
                errors.append(f"{label}.block must contain a valid prior_status, reason, and blocked_at")
        elif block is not None:
            errors.append(f"{label}.block must be null unless status is blocked")
        if feature.get("sdd") and state in {"spec_ready", "in_progress", "done"}:
            _, spec_errors = validate_spec(root, feature)
            errors.extend(f"{name}: {error}" for error in spec_errors)
    if active > 1:
        errors.append("At most one feature may be in_progress")
    return errors


def load_state(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load and structurally validate configuration and feature state."""
    location = paths(root)
    config = json_load(location["config"])
    features = json_load(location["features"])
    errors = validate_config(config, root) + validate_features(features, root)
    if errors:
        raise HarnessError("Harness validation failed:\n- " + "\n- ".join(errors))
    return config, features


def find_feature(features_data: dict[str, Any], selector: str) -> dict[str, Any]:
    """Find a feature by name or decimal ID."""
    for feature in features_data["features"]:
        if feature["name"] == selector or str(feature["id"]) == selector:
            return feature
    raise HarnessError(f"Unknown feature: {selector}")
