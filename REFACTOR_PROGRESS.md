# Harness control-plane refactor progress

## Completed

- Inspected repository policy, Git state, adaptation design, test loader, hook consumers, CLI, and all top-level `harnessctl.py` definitions.
- Established the clean `master` baseline: 64 tests passed in 60.666 seconds.
- Created branch `refactor/modularize-harnessctl`.
- Defined a conservative six-module boundary under `template/harness/scripts/harness_core/` while retaining `harnessctl.py` as the stable facade and CLI.
- Added contract coverage for direct-file facade loading, subprocess CLI execution from root and nested directories without `PYTHONPATH`, argument/domain error codes, the imported Python surface, and recursive cache absence.

## Pending

1. Extract repository and specification primitives.
2. Extract state validation and command execution.
3. Extract inspection and workflow operations.
4. Reduce the facade to stable reexports plus CLI parsing/dispatch, update template inventory, and perform final validation.

## Decisions

- Preserve the identity of a single `HarnessError` across the facade and every internal module.
- Preserve every existing top-level Python name through explicit facade reexports.
- Internal modules follow one-way dependencies and never import `harnessctl.py`.
- Direct `spec_from_file_location` loading and real CLI execution must work without caller-provided `PYTHONPATH`.
- Internal imports must not leave `__pycache__` below `harness/scripts/`.

## Tests executed

- `python -B -m unittest discover -s tests -v` — 64 passed (baseline).
- `python -B -m unittest tests.test_hooks_and_template -v` — 15 passed after contract additions.

## Last stable checkpoint

- Contract-test substage passes locally; checkpoint commit pending.
