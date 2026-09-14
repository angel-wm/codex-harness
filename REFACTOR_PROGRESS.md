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

## Pending

1. Extract inspection and workflow operations.
2. Reduce the facade to stable reexports plus CLI parsing/dispatch, update template inventory, and perform final validation.

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

## Last stable checkpoint

- `b04e70b` (`refactor: extract repository and spec primitives`). State/runner extraction passes locally; checkpoint commit pending.
