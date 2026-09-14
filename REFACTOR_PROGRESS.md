# Harness control-plane refactor progress

## Completed

- Inspected repository policy, Git state, adaptation design, test loader, hook consumers, CLI, and all top-level `harnessctl.py` definitions.
- Established the clean `master` baseline: 64 tests passed in 60.666 seconds.
- Created branch `refactor/modularize-harnessctl`.
- Defined a conservative six-module boundary under `template/harness/scripts/harness_core/` while retaining `harnessctl.py` as the stable facade and CLI.
- Added contract coverage for direct-file facade loading, subprocess CLI execution from root and nested directories without `PYTHONPATH`, argument/domain error codes, the imported Python surface, and recursive cache absence.
- Extracted repository/path/persistence/Git/fingerprint primitives into `harness_core/repository.py`.
- Extracted strict EARS, task, traceability, and spec-digest primitives into `harness_core/specs.py`.
- Kept every extracted name reexported by the canonical facade with one shared `HarnessError` identity.
- Extracted configuration and feature-state validation/loading into `harness_core/state.py`.
- Extracted platform argv selection, command fingerprints, sequential subprocess execution, timeouts, fail-fast handling, and verification evidence into `harness_core/runner.py`.
- Extracted structural inspection, prerequisite checks, status payloads, and human-readable status output into `harness_core/inspection.py`.
- Extracted all state transitions, approval, reviewer validation/recording, completion gates, exact-path auto-commit, blocking, and resumption into `harness_core/workflow.py`.
- Reduced `harnessctl.py` to the stable import facade, CLI parser, and command dispatch while retaining every original function and constant on the facade.
- Added all internal modules to the distributable inventory checked by `doctor`.
- Updated the README and adaptation architecture tree, and added a static dependency-direction/distribution test.

## Pending

1. Perform final static and runtime validation, remove this progress file, and create the closeout commit.

## Decisions

- Preserve the identity of a single `HarnessError` across the facade and every internal module.
- Preserve every existing top-level Python name through explicit facade reexports.
- Internal modules follow one-way dependencies and never import `harnessctl.py`.
- Direct `spec_from_file_location` loading and real CLI execution must work without caller-provided `PYTHONPATH`.
- Internal imports must not leave `__pycache__` below `harness/scripts/`.

## Tests executed

- `python -B -m unittest discover -s tests -v` — 64 passed (baseline).
- `python -B -m unittest tests.test_hooks_and_template -v` — 15 passed after contract additions.
- `python -B -m unittest tests.test_config_and_commands -v` — 13 passed after repository/spec extraction.
- `python -B -m unittest tests.test_specs_and_state -v` — 17 passed after repository/spec extraction.
- `python -B -m unittest tests.test_hooks_and_template -v` — 15 passed after repository/spec extraction.
- `python -B -m unittest tests.test_integration_acceptance -v` — 1 passed after repository/spec extraction.
- `python -B -m unittest discover -s tests -v` — 67 passed in 54.655 seconds after repository/spec extraction.
- Static AST comparison — all 42 original top-level definitions remain structurally identical.
- `python -B -m unittest tests.test_config_and_commands -v` — 13 passed after state/runner extraction.
- `python -B -m unittest tests.test_specs_and_state -v` — 17 passed after state/runner extraction.
- `python -B -m unittest tests.test_workflow -v` — 21 passed after state/runner extraction.
- `python -B -m unittest tests.test_hooks_and_template -v` — 15 passed after state/runner extraction.
- `python -B -m unittest tests.test_integration_acceptance -v` — 1 passed after state/runner extraction.
- `python -B -m unittest discover -s tests -v` — 67 passed in 54.310 seconds after state/runner extraction.
- Repeated static AST comparison — no missing or changed original definitions.
- `python -B -m unittest tests.test_hooks_and_template -v` — 15 passed after inspection/workflow extraction.
- `python -B -m unittest tests.test_integration_acceptance -v` — 1 passed after inspection/workflow extraction.
- `python -B -m unittest discover -s tests -v` — 67 passed in 55.069 seconds after inspection/workflow extraction, including all 21 workflow tests.
- Repeated static AST comparison after inspection/workflow extraction — no missing or changed original definitions.
- `python -B -m unittest tests.test_hooks_and_template -v` — 16 passed after facade/distribution closeout.
- `python -B -m unittest tests.test_config_and_commands -v` — 13 passed after facade/distribution closeout.
- `python -B -m unittest tests.test_specs_and_state -v` — 17 passed after facade/distribution closeout.
- `python -B -m unittest tests.test_integration_acceptance -v` — 1 passed after facade/distribution closeout.
- `python -m unittest discover -s tests -v` — 68 passed in 55.703 seconds using the exact repository-required command.

## Last stable checkpoint

- `5f74b03` (`refactor: isolate inspection and workflow gates`). Facade/distribution closeout passes locally; checkpoint commit pending.
