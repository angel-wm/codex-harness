#!/usr/bin/env python3
"""Codex hook adapter for fast validation and bounded stop-time verification."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

import harnessctl


def hook_event_name(event: dict[str, Any]) -> str:
    """Read the event name across documented snake/camel-case transports."""
    value = event.get("hook_event_name", event.get("hookEventName", ""))
    return value if isinstance(value, str) else ""


def emit(payload: dict[str, Any]) -> int:
    """Emit one valid compact hook JSON object."""
    print(json.dumps(payload, separators=(",", ":")))
    return 0


def post_tool_use(root: Path) -> int:
    """Run structural validation after a completed write."""
    try:
        harnessctl.validate_repository(root)
    except harnessctl.HarnessError as exc:
        return emit(
            {
                "decision": "block",
                "reason": f"Harness structural validation failed after the edit: {exc}",
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": "Repair the invalid harness state or record a blocker before continuing.",
                },
            }
        )
    return emit({})


def stop(root: Path, event: dict[str, Any]) -> int:
    """Validate and verify a changed active implementation at most once."""
    try:
        harnessctl.validate_repository(root)
        payload = harnessctl.status_payload(root)
    except harnessctl.HarnessError as exc:
        if event.get("stop_hook_active") is True:
            return emit({"systemMessage": f"Harness validation still fails: {exc}"})
        return emit({"decision": "block", "reason": f"Repair or block the invalid harness state: {exc}"})
    active = payload["active_feature"]
    if not active:
        return emit({})
    verification = payload.get("verification")
    current = payload.get("implementation_fingerprint")
    is_current = (
        isinstance(verification, dict)
        and verification.get("success") is True
        and verification.get("feature") == active["name"]
        and verification.get("implementation_fingerprint") == current
    )
    if is_current:
        return emit({})
    try:
        _, exit_code = harnessctl.run_command_group(root, "verify")
    except harnessctl.HarnessError as exc:
        exit_code = 2
        failure = str(exc)
    else:
        failure = "Configured verification failed."
    if exit_code == 0:
        return emit({"systemMessage": "Configured verification passed for the current implementation fingerprint."})
    if event.get("stop_hook_active") is True:
        return emit(
            {
                "systemMessage": (
                    f"{failure} Stop-hook continuation was already used; preserve in_progress and "
                    "record a blocker if it cannot be repaired in scope."
                )
            }
        )
    return emit(
        {
            "decision": "block",
            "reason": (
                f"{failure} Fix the failure, rerun verification, or record the feature as blocked. "
                "This is the single automatic continuation."
            ),
        }
    )


def main() -> int:
    """Read one hook event from stdin and dispatch it."""
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return emit({"systemMessage": f"Invalid hook input: {exc}"})
    if not isinstance(event, dict):
        return emit({"systemMessage": "Invalid hook input: expected a JSON object"})
    try:
        root = harnessctl.discover_root()
    except harnessctl.HarnessError as exc:
        return emit({"systemMessage": str(exc)})
    name = hook_event_name(event)
    if name == "PostToolUse":
        return post_tool_use(root)
    if name == "Stop":
        return stop(root, event)
    return emit({})


if __name__ == "__main__":
    raise SystemExit(main())
