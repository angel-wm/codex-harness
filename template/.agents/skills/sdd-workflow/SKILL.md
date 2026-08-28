---
name: sdd-workflow
description: Coordinate repository features through strict specification-driven development. Use for requests to implement, continue, approve, resume, or complete an entry in harness/features.json. Do not use for pure questions or read-only exploration.
---

# SDD workflow

Coordinate one feature through the repository-owned control plane. Run commands
from the Git root with `py -3` on Windows or `python3` on POSIX.

1. Run `harness/scripts/harnessctl.py doctor` and inspect `status --json`.
   Read only the applicable files under `harness/docs/`.
2. Select the lowest positive-ID actionable feature. Never work on two features
   concurrently.
3. If it is `pending`, spawn exactly one `sdd_spec_author`. After it returns,
   run `validate` and `spec-ready FEATURE`. Present the three spec paths, explain
   that the reviewed spec and state must be committed, and stop for the human.
4. Never infer approval. On a later explicit approval for the current feature,
   run `approve FEATURE`. If the worktree is not clean or the spec changed, stop.
5. Spawn exactly one `sdd_implementer`. Do not use parallel write agents.
6. Run `run verify`. A failed verification returns to the implementer without
   advancing state.
7. Spawn one read-only `sdd_reviewer` with the feature, approved spec path,
   implementation baseline, current implementation fingerprint, and fresh
   verification artifact.
8. Save its exact JSON response to a temporary input file and run
   `record-review FEATURE --input INPUT`. The coordinator, not the reviewer,
   owns repository review artifacts.
9. For `CHANGES_REQUESTED`, send only the recorded findings to the implementer,
   then verify and review again. Stop and run `block` after the configured cycle
   limit.
10. For `APPROVED`, confirm verification is still fingerprint-current and run
    `complete FEATURE`.
11. On any unsatisfied invariant, failed tool, stale evidence, or required spec
    change, run `block FEATURE --reason TEXT` when the state permits and return
    control to the human. Resume only on explicit human direction.

Read-only explorer agents are optional for genuinely complex investigation.
They never edit and never replace the three workflow roles.
