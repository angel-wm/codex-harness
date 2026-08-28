#!/usr/bin/env python3
"""Deterministic control plane for the repository-owned SDD harness."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


SCHEMA_VERSION = 1
VALID_STATES = {"pending", "spec_ready", "in_progress", "done", "blocked"}
BLOCKABLE_STATES = {"pending", "spec_ready", "in_progress"}
VOLATILE_PATHS = {
    "harness/features.json",
    "harness/progress/current.md",
    "harness/progress/history.md",
    "harness/progress/verification.json",
}
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


class HarnessError(Exception):
    """A user-correctable harness invariant or command failure."""


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp without fractional seconds."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def json_load(path: Path) -> dict[str, Any]:
    """Load one JSON object with a useful error on malformed input."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HarnessError(f"Required file is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise HarnessError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HarnessError(f"Expected a JSON object in {path}")
    return value


def atomic_write(path: Path, text: str) -> None:
    """Replace a UTF-8 text file atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def json_write(path: Path, value: Any) -> None:
    """Write stable, human-readable JSON atomically."""
    atomic_write(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def run_git(root: Path, args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run Git without a shell and capture UTF-8 text."""
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        shell=False,
        check=False,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
        raise HarnessError(f"git {' '.join(args)} failed: {detail}")
    return result


def discover_root(start: Path | None = None) -> Path:
    """Find the enclosing Git root."""
    location = (start or Path.cwd()).resolve()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=location,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        shell=False,
        check=False,
    )
    if result.returncode != 0:
        raise HarnessError("The harness must run inside a Git repository.")
    return Path(result.stdout.strip()).resolve()


def paths(root: Path) -> dict[str, Path]:
    """Return canonical harness paths for a repository root."""
    harness = root / "harness"
    progress = harness / "progress"
    return {
        "root": root,
        "harness": harness,
        "config": harness / "config.json",
        "features": harness / "features.json",
        "specs": harness / "specs",
        "progress": progress,
        "current": progress / "current.md",
        "history": progress / "history.md",
        "reviews": progress / "reviews",
        "verification": progress / "verification.json",
    }


def normalized_relative(root: Path, candidate: Path) -> str:
    """Return a slash-normalized repository-relative path."""
    return candidate.resolve().relative_to(root.resolve()).as_posix()


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


def spec_paths(root: Path, feature: dict[str, Any]) -> tuple[Path, Path, Path]:
    """Return requirements, design, and tasks paths for a feature."""
    base = root / "harness" / "specs" / feature["name"]
    return base / "requirements.md", base / "design.md", base / "tasks.md"


def parse_requirements(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse strict English EARS requirements and their acceptance mappings."""
    errors: list[str] = []
    matches = list(re.finditer(r"(?m)^## (R(\d+))\s*$", text))
    if not matches:
        return [], ["requirements.md must contain headings beginning with ## R1"]
    requirements: list[dict[str, Any]] = []
    expected = 1
    ears = re.compile(
        r"^(?:The system MUST .+|WHEN .+, the system MUST .+|"
        r"WHILE .+, the system MUST .+|WHERE .+, the system MUST .+|"
        r"IF .+ THEN the system MUST .+)$"
    )
    for index, match in enumerate(matches):
        identifier = match.group(1)
        number = int(match.group(2))
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():end].strip()
        statement_lines: list[str] = []
        acceptance: list[int] = []
        for line in body.splitlines():
            stripped = line.strip()
            mapping = re.fullmatch(r"Acceptance:\s*(A\d+(?:\s*,\s*A\d+)*)", stripped)
            if mapping:
                acceptance.extend(int(item[1:]) for item in re.findall(r"A\d+", mapping.group(1)))
            elif stripped and not stripped.startswith("<!--"):
                statement_lines.append(stripped)
        statement = " ".join(statement_lines)
        if number != expected:
            errors.append(f"Requirement IDs must be sequential; expected R{expected}, found {identifier}")
            expected = number
        expected += 1
        if statement.count("MUST") != 1:
            errors.append(f"{identifier} must contain exactly one uppercase MUST obligation")
        if re.search(r"\b(?:MAY|SHOULD|COULD)\b", statement):
            errors.append(f"{identifier} contains a soft obligation")
        if not ears.fullmatch(statement):
            errors.append(f"{identifier} does not match a strict English EARS form")
        requirements.append({"id": identifier, "statement": statement, "acceptance": acceptance})
    return requirements, errors


def parse_tasks(text: str, requirement_ids: set[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse ordered executable tasks with requirement references."""
    errors: list[str] = []
    tasks: list[dict[str, Any]] = []
    pattern = re.compile(r"(?m)^- \[([ xX])\] T(\d+)\s+.+?(?:Covers|Requirements):\s*([^\n.]+)\.?")
    for match in pattern.finditer(text):
        references = re.findall(r"R\d+", match.group(3))
        tasks.append(
            {
                "id": f"T{match.group(2)}",
                "number": int(match.group(2)),
                "complete": match.group(1).lower() == "x",
                "requirements": references,
            }
        )
    if not tasks:
        return [], ["tasks.md must contain tasks like '- [ ] T1 — ... Covers: R1.'"]
    for expected, task in enumerate(tasks, start=1):
        if task["number"] != expected:
            errors.append(f"Task IDs must be sequential; expected T{expected}, found {task['id']}")
        if not task["requirements"]:
            errors.append(f"{task['id']} must reference at least one requirement")
        unknown = sorted(set(task["requirements"]) - requirement_ids)
        if unknown:
            errors.append(f"{task['id']} references unknown requirements: {', '.join(unknown)}")
    return tasks, errors


def validate_spec(root: Path, feature: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Validate all three spec files for one feature."""
    requirements_path, design_path, tasks_path = spec_paths(root, feature)
    missing = [str(path.relative_to(root)) for path in (requirements_path, design_path, tasks_path) if not path.is_file()]
    if missing:
        return {}, [f"Missing spec file: {item}" for item in missing]
    requirements, errors = parse_requirements(requirements_path.read_text(encoding="utf-8"))
    acceptance_count = len(feature.get("acceptance", []))
    if acceptance_count:
        covered = {number for requirement in requirements for number in requirement["acceptance"]}
        expected = set(range(1, acceptance_count + 1))
        missing_acceptance = sorted(expected - covered)
        unknown_acceptance = sorted(covered - expected)
        if missing_acceptance:
            errors.append("Unmapped acceptance criteria: " + ", ".join(f"A{item}" for item in missing_acceptance))
        if unknown_acceptance:
            errors.append("Unknown acceptance mappings: " + ", ".join(f"A{item}" for item in unknown_acceptance))
    design = design_path.read_text(encoding="utf-8").strip()
    if len(design) < 100:
        errors.append("design.md must contain substantive design decisions")
    if "alternative" not in design.lower():
        errors.append("design.md must document at least one rejected alternative")
    requirement_ids = {item["id"] for item in requirements}
    tasks, task_errors = parse_tasks(tasks_path.read_text(encoding="utf-8"), requirement_ids)
    errors.extend(task_errors)
    referenced = {identifier for task in tasks for identifier in task["requirements"]}
    unreferenced = sorted(requirement_ids - referenced, key=lambda item: int(item[1:]))
    if unreferenced:
        errors.append("Requirements not referenced by any task: " + ", ".join(unreferenced))
    return {"requirements": requirements, "tasks": tasks}, errors


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


def canonical_spec_digest(root: Path, feature: dict[str, Any]) -> str:
    """Hash normalized spec content while ignoring task checkbox state."""
    digest = hashlib.sha256()
    for path in spec_paths(root, feature):
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
        if path.name == "tasks.md":
            text = re.sub(r"(?m)^- \[[xX]\]", "- [ ]", text)
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(text.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def git_is_clean(root: Path) -> bool:
    """Return whether tracked, staged, and untracked state is clean."""
    return not run_git(root, ["status", "--porcelain"]).stdout


def changed_paths(root: Path, baseline: str) -> list[str]:
    """Return all tracked changes from baseline plus current untracked files."""
    tracked = run_git(root, ["diff", "--name-only", "--diff-filter=ACDMRTUXB", baseline, "--"]).stdout.splitlines()
    untracked = run_git(root, ["ls-files", "--others", "--exclude-standard"]).stdout.splitlines()
    return sorted({item.replace("\\", "/") for item in [*tracked, *untracked] if item})


def is_volatile(path: str) -> bool:
    """Identify coordinator-owned evidence excluded from implementation identity."""
    return path in VOLATILE_PATHS or path.startswith("harness/progress/reviews/")


def implementation_fingerprint(root: Path, baseline: str) -> str:
    """Hash repository content changed since approval, excluding volatile evidence."""
    digest = hashlib.sha256()
    for relative in changed_paths(root, baseline):
        if is_volatile(relative):
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        path = root / relative
        if path.is_file():
            digest.update(path.read_bytes())
        else:
            digest.update(b"<deleted>")
        digest.update(b"\0")
    return digest.hexdigest()


def approval_is_current(root: Path, feature: dict[str, Any]) -> bool:
    """Return whether the stored approval matches the normalized current spec."""
    approval = feature.get("approval")
    return isinstance(approval, dict) and approval.get("digest") == canonical_spec_digest(root, feature)


def select_argv(step: dict[str, Any], platform_name: str | None = None) -> list[str]:
    """Select the configured argument vector for a platform."""
    platform = platform_name or ("windows" if os.name == "nt" else "posix")
    field = "windows_argv" if platform == "windows" else "posix_argv"
    value = step.get(field, step.get("argv"))
    if not isinstance(value, list) or not value:
        raise HarnessError(f"Command {step.get('name', '<unnamed>')} has no argv for {platform}")
    return list(value)


def command_fingerprint(argv: Sequence[str], cwd: str, environment: dict[str, str]) -> str:
    """Hash non-secret command metadata for durable evidence."""
    payload = json.dumps({"argv": list(argv), "cwd": cwd, "env_keys": sorted(environment)}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_command_group(root: Path, group: str) -> tuple[dict[str, Any], int]:
    """Execute one configured command group sequentially and persist verification evidence."""
    config, features_data = load_state(root)
    steps = config["commands"][group]
    if not steps:
        raise HarnessError(f"No commands are configured for {group}")
    active = next((item for item in features_data["features"] if item["status"] == "in_progress"), None)
    baseline = active.get("approval", {}).get("baseline") if active else None
    fingerprint = implementation_fingerprint(root, baseline) if baseline else None
    evidence: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "group": group,
        "started_at": utc_now(),
        "feature": active["name"] if active else None,
        "implementation_fingerprint": fingerprint,
        "steps": [],
        "success": True,
    }
    final_code = 0
    for step in steps:
        argv = select_argv(step)
        cwd_value = step.get("cwd", ".")
        working_directory = (root / cwd_value).resolve()
        environment = os.environ.copy()
        environment.update(step.get("env", {}))
        started = time.monotonic()
        timed_out = False
        try:
            result = subprocess.run(
                argv,
                cwd=working_directory,
                env=environment,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                shell=False,
                timeout=step.get("timeout_seconds", 600),
                check=False,
            )
            exit_code = result.returncode
            stdout = result.stdout
            stderr = result.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = 124
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
        duration = round(time.monotonic() - started, 6)
        record = {
            "name": step["name"],
            "exit_code": exit_code,
            "duration_seconds": duration,
            "finished_at": utc_now(),
            "timed_out": timed_out,
            "command_fingerprint": command_fingerprint(argv, cwd_value, step.get("env", {})),
        }
        evidence["steps"].append(record)
        if exit_code != 0:
            evidence["success"] = False
            final_code = exit_code
            print(f"Command step failed: {step['name']} (exit {exit_code})", file=sys.stderr)
            if stdout:
                print(stdout, file=sys.stderr, end="" if stdout.endswith("\n") else "\n")
            if stderr:
                print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")
            print("Command output is not persisted. Do not put secrets in configured arguments.", file=sys.stderr)
            break
    evidence["finished_at"] = utc_now()
    if group == "verify":
        json_write(paths(root)["verification"], evidence)
    return evidence, final_code


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


def update_current(root: Path, feature: dict[str, Any], next_step: str) -> None:
    """Write a concise durable current-session record."""
    text = (
        "# Current SDD session\n\n"
        f"- **Feature:** `{feature['name']}`\n"
        f"- **State:** `{feature['status']}`\n"
        f"- **Updated (UTC):** {utc_now()}\n\n"
        "## Next step\n\n"
        f"{next_step}\n"
    )
    atomic_write(paths(root)["current"], text)


def transition_spec_ready(root: Path, selector: str) -> dict[str, Any]:
    """Move one valid SDD feature from pending to spec_ready."""
    config, features_data = load_state(root)
    feature = find_feature(features_data, selector)
    if feature["status"] != "pending":
        raise HarnessError("spec-ready requires a pending feature")
    if not feature["sdd"]:
        raise HarnessError("spec-ready applies only to SDD features")
    if any(item["status"] == "in_progress" for item in features_data["features"]):
        raise HarnessError("Another feature is already in_progress")
    if not config["commands"]["verify"]:
        raise HarnessError("Configure at least one verify command before spec-ready")
    _, errors = validate_spec(root, feature)
    if errors:
        raise HarnessError("Spec validation failed:\n- " + "\n- ".join(errors))
    feature["status"] = "spec_ready"
    feature["approval"] = None
    feature["block"] = None
    feature["review_cycles"] = 0
    json_write(paths(root)["features"], features_data)
    update_current(root, feature, "Human reviews and commits the three spec files and feature state, then explicitly approves them.")
    return feature


def approve_feature(root: Path, selector: str) -> dict[str, Any]:
    """Record exact spec approval and move spec_ready to in_progress."""
    config, features_data = load_state(root)
    feature = find_feature(features_data, selector)
    if feature["status"] != "spec_ready":
        raise HarnessError("approve requires a spec_ready feature")
    if any(item is not feature and item["status"] == "in_progress" for item in features_data["features"]):
        raise HarnessError("Another feature is already in_progress")
    if not config["commands"]["verify"]:
        raise HarnessError("Configure at least one verify command before approval")
    _, errors = validate_spec(root, feature)
    if errors:
        raise HarnessError("Spec validation failed:\n- " + "\n- ".join(errors))
    if config["workflow"]["require_clean_worktree"] and not git_is_clean(root):
        raise HarnessError("Approval requires a clean worktree; commit or stash reviewed spec/state changes first")
    baseline = run_git(root, ["rev-parse", "HEAD"]).stdout.strip()
    feature["approval"] = {
        "digest": canonical_spec_digest(root, feature),
        "approved_at": utc_now(),
        "baseline": baseline,
    }
    feature["status"] = "in_progress"
    feature["block"] = None
    feature["review_cycles"] = 0
    json_write(paths(root)["features"], features_data)
    update_current(root, feature, "Run the sequential implementer, configured verification, and independent reviewer.")
    return feature


def read_review(path: Path, feature: dict[str, Any], expected_fingerprint: str, requirement_ids: set[str]) -> dict[str, Any]:
    """Validate a strict reviewer JSON verdict."""
    review = json_load(path)
    errors: list[str] = []
    if review.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must equal {SCHEMA_VERSION}")
    if review.get("feature") != feature["name"]:
        errors.append("feature does not match")
    if review.get("implementation_fingerprint") != expected_fingerprint:
        errors.append("implementation_fingerprint is stale or incorrect")
    if review.get("verdict") not in {"APPROVED", "CHANGES_REQUESTED"}:
        errors.append("verdict must be APPROVED or CHANGES_REQUESTED")
    coverage = review.get("requirements")
    if not isinstance(coverage, list):
        errors.append("requirements must be an array")
    else:
        seen: set[str] = set()
        for entry in coverage:
            if not isinstance(entry, dict) or entry.get("id") not in requirement_ids:
                errors.append("requirements contains an invalid id")
                continue
            seen.add(entry["id"])
            if not isinstance(entry.get("covered"), bool) or not isinstance(entry.get("evidence"), str):
                errors.append(f"requirements entry {entry['id']} needs covered boolean and evidence string")
        if seen != requirement_ids:
            errors.append("requirements coverage must include every requirement exactly once")
    if not isinstance(review.get("tasks_complete"), bool):
        errors.append("tasks_complete must be a boolean")
    if not isinstance(review.get("checkpoints"), list):
        errors.append("checkpoints must be an array")
    findings = review.get("findings")
    if not isinstance(findings, list) or not all(
        isinstance(item, dict)
        and isinstance(item.get("path"), str)
        and isinstance(item.get("remediation"), str)
        for item in findings
    ):
        errors.append("findings must be an array of path/remediation objects")
    if review.get("verdict") == "APPROVED":
        if review.get("tasks_complete") is not True or findings:
            errors.append("APPROVED requires tasks_complete true and no findings")
        if isinstance(coverage, list) and any(entry.get("covered") is not True for entry in coverage if isinstance(entry, dict)):
            errors.append("APPROVED requires all requirements covered")
    if errors:
        raise HarnessError("Invalid review JSON:\n- " + "\n- ".join(errors))
    review["recorded_at"] = utc_now()
    return review


def record_review(root: Path, selector: str, input_path: Path) -> dict[str, Any]:
    """Persist a current structured reviewer verdict and enforce cycle limits."""
    config, features_data = load_state(root)
    feature = find_feature(features_data, selector)
    if feature["status"] != "in_progress":
        raise HarnessError("record-review requires an in_progress feature")
    if not approval_is_current(root, feature):
        raise HarnessError("The approved spec digest is stale")
    spec, errors = validate_spec(root, feature)
    if errors:
        raise HarnessError("Spec validation failed:\n- " + "\n- ".join(errors))
    fingerprint = implementation_fingerprint(root, feature["approval"]["baseline"])
    review = read_review(input_path, feature, fingerprint, {item["id"] for item in spec["requirements"]})
    paths(root)["reviews"].mkdir(parents=True, exist_ok=True)
    json_write(paths(root)["reviews"] / f"{feature['name']}.json", review)
    findings_lines = "\n".join(
        f"- `{item['path']}` — {item['remediation']}" for item in review["findings"]
    ) or "- None."
    markdown = (
        f"# Review: {feature['name']}\n\n"
        f"- Verdict: **{review['verdict']}**\n"
        f"- Fingerprint: `{fingerprint}`\n"
        f"- Recorded: {review['recorded_at']}\n\n"
        f"## Findings\n\n{findings_lines}\n"
    )
    atomic_write(paths(root)["reviews"] / f"{feature['name']}.md", markdown)
    feature["review_cycles"] = feature.get("review_cycles", 0) + 1
    if review["verdict"] == "CHANGES_REQUESTED" and feature["review_cycles"] >= config["workflow"]["max_review_cycles"]:
        prior = feature["status"]
        feature["status"] = "blocked"
        feature["block"] = {
            "prior_status": prior,
            "reason": f"Review cycle limit reached ({feature['review_cycles']})",
            "blocked_at": utc_now(),
        }
    json_write(paths(root)["features"], features_data)
    next_step = "Complete the feature." if review["verdict"] == "APPROVED" else "Address only the recorded findings, then verify and review again."
    update_current(root, feature, next_step)
    return review


def traceability_ids(report_path: Path) -> set[str]:
    """Extract requirements with explicit arrow-based evidence entries."""
    if not report_path.is_file():
        return set()
    return set(re.findall(r"(?m)^- (R\d+)\s*(?:→|->)\s*\S.+$", report_path.read_text(encoding="utf-8")))


def complete_feature(root: Path, selector: str) -> dict[str, Any]:
    """Complete one feature after independently rechecking every final gate."""
    config, features_data = load_state(root)
    feature = find_feature(features_data, selector)
    if feature["status"] != "in_progress":
        raise HarnessError("complete requires an in_progress feature")
    if not approval_is_current(root, feature):
        raise HarnessError("Completion rejected: approved spec digest is stale")
    spec, errors = validate_spec(root, feature)
    if errors:
        raise HarnessError("Completion rejected by spec validation:\n- " + "\n- ".join(errors))
    incomplete = [item["id"] for item in spec["tasks"] if not item["complete"]]
    if incomplete:
        raise HarnessError("Completion rejected: incomplete tasks: " + ", ".join(incomplete))
    requirement_ids = {item["id"] for item in spec["requirements"]}
    report = paths(root)["progress"] / f"impl_{feature['name']}.md"
    missing_traceability = sorted(requirement_ids - traceability_ids(report), key=lambda item: int(item[1:]))
    if missing_traceability:
        raise HarnessError("Completion rejected: missing traceability for " + ", ".join(missing_traceability))
    fingerprint = implementation_fingerprint(root, feature["approval"]["baseline"])
    verification_path = paths(root)["verification"]
    if not verification_path.is_file():
        raise HarnessError("Completion rejected: no verification artifact")
    verification = json_load(verification_path)
    if not verification.get("success") or verification.get("group") != "verify":
        raise HarnessError("Completion rejected: latest verification did not succeed")
    if verification.get("feature") != feature["name"] or verification.get("implementation_fingerprint") != fingerprint:
        raise HarnessError("Completion rejected: verification is stale")
    review_path = paths(root)["reviews"] / f"{feature['name']}.json"
    if not review_path.is_file():
        raise HarnessError("Completion rejected: no recorded review")
    review = json_load(review_path)
    if review.get("verdict") != "APPROVED" or review.get("implementation_fingerprint") != fingerprint:
        raise HarnessError("Completion rejected: review is absent, non-approved, or stale")
    feature["status"] = "done"
    feature["block"] = None
    completed_at = utc_now()
    json_write(paths(root)["features"], features_data)
    history_path = paths(root)["history"]
    existing = history_path.read_text(encoding="utf-8") if history_path.is_file() else "# SDD history\n"
    entry = (
        f"\n## {completed_at} — {feature['title']} (`{feature['name']}`)\n\n"
        f"- Feature ID: {feature['id']}\n"
        f"- Approved spec: `{feature['approval']['digest']}`\n"
        f"- Implementation: `{fingerprint}`\n"
        f"- Verification: successful\n"
        f"- Review cycles: {feature['review_cycles']}\n"
    )
    atomic_write(history_path, existing.rstrip() + "\n" + entry)
    atomic_write(
        paths(root)["current"],
        "# Current SDD session\n\n- **Feature:** _none_\n- **Started (UTC):** _—_\n- **Coordinator:** _—_\n\n## Plan\n\n_—_\n\n## Log\n\n_—_\n\n## Next step\n\n_—_\n",
    )
    if config["git"]["auto_commit_on_done"]:
        exact_paths = changed_paths(root, feature["approval"]["baseline"])
        if not exact_paths:
            raise HarnessError("Feature completed, but auto-commit found no changed paths")
        for relative in exact_paths:
            run_git(root, ["add", "--", relative])
        message = config["git"]["commit_message"].format(
            feature_name=feature["name"], feature_title=feature["title"]
        )
        commit = run_git(root, ["commit", "-m", message], check=False)
        if commit.returncode != 0:
            detail = commit.stderr.strip() or commit.stdout.strip()
            raise HarnessError(f"Feature completed, but auto-commit failed non-destructively: {detail}")
    return {"feature": feature["name"], "status": "done", "implementation_fingerprint": fingerprint}


def block_feature(root: Path, selector: str, reason: str) -> dict[str, Any]:
    """Record a durable blocker while preserving the resumable prior state."""
    _, features_data = load_state(root)
    feature = find_feature(features_data, selector)
    if feature["status"] not in BLOCKABLE_STATES:
        raise HarnessError("Only pending, spec_ready, or in_progress features can be blocked")
    prior = feature["status"]
    feature["status"] = "blocked"
    feature["block"] = {"prior_status": prior, "reason": reason.strip(), "blocked_at": utc_now()}
    if not feature["block"]["reason"]:
        raise HarnessError("A non-empty block reason is required")
    json_write(paths(root)["features"], features_data)
    update_current(root, feature, f"Blocked: {reason.strip()} Explicit human direction is required to resume.")
    return feature


def resume_feature(root: Path, selector: str) -> dict[str, Any]:
    """Restore a blocked feature to its recorded valid prior state."""
    _, features_data = load_state(root)
    feature = find_feature(features_data, selector)
    if feature["status"] != "blocked" or not isinstance(feature.get("block"), dict):
        raise HarnessError("resume requires a blocked feature")
    prior = feature["block"].get("prior_status")
    if prior not in BLOCKABLE_STATES:
        raise HarnessError("Blocked feature has no valid prior state")
    if prior == "in_progress" and any(
        item is not feature and item["status"] == "in_progress" for item in features_data["features"]
    ):
        raise HarnessError("Cannot resume: another feature is in_progress")
    feature["status"] = prior
    feature["block"] = None
    json_write(paths(root)["features"], features_data)
    update_current(root, feature, f"Resumed to {prior}; continue only within the existing approved scope.")
    return feature


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


def build_parser() -> argparse.ArgumentParser:
    """Create the stable command-line interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor")
    status = subparsers.add_parser("status")
    status.add_argument("--json", action="store_true", dest="as_json")
    subparsers.add_parser("validate")
    run = subparsers.add_parser("run")
    run.add_argument("group", choices=("bootstrap", "verify"))
    for name in ("spec-ready", "approve", "complete", "resume"):
        command = subparsers.add_parser(name)
        command.add_argument("feature")
    review = subparsers.add_parser("record-review")
    review.add_argument("feature")
    review.add_argument("--input", required=True, type=Path)
    block = subparsers.add_parser("block")
    block.add_argument("feature")
    block.add_argument("--reason", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and convert harness errors into stable exit code 2."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = discover_root()
        if args.command == "doctor":
            result = doctor(root)
            print(json.dumps(result, indent=2))
            return 0 if result["ok"] else 1
        if args.command == "status":
            result = status_payload(root)
            if args.as_json:
                print(json.dumps(result, indent=2))
            else:
                print_status(result)
            return 0
        if args.command == "validate":
            print(json.dumps(validate_repository(root), indent=2))
            return 0
        if args.command == "run":
            evidence, code = run_command_group(root, args.group)
            print(json.dumps(evidence, indent=2))
            return code
        if args.command == "spec-ready":
            result = transition_spec_ready(root, args.feature)
        elif args.command == "approve":
            result = approve_feature(root, args.feature)
        elif args.command == "record-review":
            result = record_review(root, args.feature, args.input.resolve())
        elif args.command == "complete":
            result = complete_feature(root, args.feature)
        elif args.command == "block":
            result = block_feature(root, args.feature, args.reason)
        elif args.command == "resume":
            result = resume_feature(root, args.feature)
        else:
            parser.error(f"Unhandled command: {args.command}")
            return 2
        print(json.dumps(result, indent=2))
        return 0
    except HarnessError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
