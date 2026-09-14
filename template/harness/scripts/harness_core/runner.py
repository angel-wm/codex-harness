"""Structured, sequential command execution and verification evidence."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Sequence

from .repository import HarnessError, implementation_fingerprint, json_write, paths, utc_now
from .state import SCHEMA_VERSION, load_state


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
