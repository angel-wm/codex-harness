#!/usr/bin/env python3
"""Deterministic control plane for the repository-owned SDD harness."""
from __future__ import annotations

import argparse
from importlib import import_module as _import_module
from importlib.util import module_from_spec as _module_from_spec
from importlib.util import spec_from_file_location as _spec_from_file_location
import json
import sys
from pathlib import Path
from typing import Sequence
from uuid import uuid4 as _uuid4


# Give each facade load its own package identity. Relative imports resolve only
# within this tree, even when other copies or versions are already in sys.modules.
_internal_package_path = Path(__file__).resolve().parent / "harness_core"
_internal_package_name = f"_harness_core_{_uuid4().hex}"
_internal_spec = _spec_from_file_location(
    _internal_package_name,
    _internal_package_path / "__init__.py",
    submodule_search_locations=[str(_internal_package_path)],
)
if _internal_spec is None or _internal_spec.loader is None:
    raise ImportError(f"Cannot load harness internals from {_internal_package_path}")

_previous_dont_write_bytecode = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    _internal_package = _module_from_spec(_internal_spec)
    sys.modules[_internal_package_name] = _internal_package
    _internal_spec.loader.exec_module(_internal_package)
    _repository = _import_module(f"{_internal_package_name}.repository")
    HarnessError = _repository.HarnessError
    atomic_write = _repository.atomic_write
    changed_paths = _repository.changed_paths
    discover_root = _repository.discover_root
    git_is_clean = _repository.git_is_clean
    implementation_fingerprint = _repository.implementation_fingerprint
    is_volatile = _repository.is_volatile
    json_load = _repository.json_load
    json_write = _repository.json_write
    normalized_relative = _repository.normalized_relative
    paths = _repository.paths
    run_git = _repository.run_git
    utc_now = _repository.utc_now
    VOLATILE_PATHS = _repository.VOLATILE_PATHS
    _specs = _import_module(f"{_internal_package_name}.specs")
    approval_is_current = _specs.approval_is_current
    canonical_spec_digest = _specs.canonical_spec_digest
    parse_requirements = _specs.parse_requirements
    parse_tasks = _specs.parse_tasks
    spec_paths = _specs.spec_paths
    traceability_ids = _specs.traceability_ids
    validate_spec = _specs.validate_spec
    _state = _import_module(f"{_internal_package_name}.state")
    BLOCKABLE_STATES = _state.BLOCKABLE_STATES
    SCHEMA_VERSION = _state.SCHEMA_VERSION
    VALID_STATES = _state.VALID_STATES
    find_feature = _state.find_feature
    load_state = _state.load_state
    validate_config = _state.validate_config
    validate_features = _state.validate_features
    validate_step = _state.validate_step
    _runner = _import_module(f"{_internal_package_name}.runner")
    command_fingerprint = _runner.command_fingerprint
    run_command_group = _runner.run_command_group
    select_argv = _runner.select_argv
    _inspection = _import_module(f"{_internal_package_name}.inspection")
    REQUIRED_TEMPLATE_PATHS = _inspection.REQUIRED_TEMPLATE_PATHS
    doctor = _inspection.doctor
    print_status = _inspection.print_status
    status_payload = _inspection.status_payload
    validate_repository = _inspection.validate_repository
    _workflow = _import_module(f"{_internal_package_name}.workflow")
    approve_feature = _workflow.approve_feature
    block_feature = _workflow.block_feature
    complete_feature = _workflow.complete_feature
    read_review = _workflow.read_review
    record_review = _workflow.record_review
    resume_feature = _workflow.resume_feature
    transition_spec_ready = _workflow.transition_spec_ready
    update_current = _workflow.update_current
finally:
    sys.dont_write_bytecode = _previous_dont_write_bytecode


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
