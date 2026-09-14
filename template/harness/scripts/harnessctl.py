#!/usr/bin/env python3
"""Deterministic control plane for the repository-owned SDD harness."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


_INTERNAL_MODULE_PATH = str(Path(__file__).resolve().parent)
_path_added = _INTERNAL_MODULE_PATH not in sys.path
_previous_dont_write_bytecode = sys.dont_write_bytecode
if _path_added:
    sys.path.insert(0, _INTERNAL_MODULE_PATH)
sys.dont_write_bytecode = True
try:
    from harness_core.repository import HarnessError
    from harness_core.repository import atomic_write
    from harness_core.repository import changed_paths
    from harness_core.repository import discover_root
    from harness_core.repository import git_is_clean
    from harness_core.repository import implementation_fingerprint
    from harness_core.repository import is_volatile
    from harness_core.repository import json_load
    from harness_core.repository import json_write
    from harness_core.repository import normalized_relative
    from harness_core.repository import paths
    from harness_core.repository import run_git
    from harness_core.repository import utc_now
    from harness_core.repository import VOLATILE_PATHS
    from harness_core.specs import approval_is_current
    from harness_core.specs import canonical_spec_digest
    from harness_core.specs import parse_requirements
    from harness_core.specs import parse_tasks
    from harness_core.specs import spec_paths
    from harness_core.specs import traceability_ids
    from harness_core.specs import validate_spec
    from harness_core.state import BLOCKABLE_STATES
    from harness_core.state import SCHEMA_VERSION
    from harness_core.state import VALID_STATES
    from harness_core.state import find_feature
    from harness_core.state import load_state
    from harness_core.state import validate_config
    from harness_core.state import validate_features
    from harness_core.state import validate_step
    from harness_core.runner import command_fingerprint
    from harness_core.runner import run_command_group
    from harness_core.runner import select_argv
    from harness_core.inspection import REQUIRED_TEMPLATE_PATHS
    from harness_core.inspection import doctor
    from harness_core.inspection import print_status
    from harness_core.inspection import status_payload
    from harness_core.inspection import validate_repository
    from harness_core.workflow import approve_feature
    from harness_core.workflow import block_feature
    from harness_core.workflow import complete_feature
    from harness_core.workflow import read_review
    from harness_core.workflow import record_review
    from harness_core.workflow import resume_feature
    from harness_core.workflow import transition_spec_ready
    from harness_core.workflow import update_current
finally:
    sys.dont_write_bytecode = _previous_dont_write_bytecode
    if _path_added:
        sys.path.remove(_INTERNAL_MODULE_PATH)


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
