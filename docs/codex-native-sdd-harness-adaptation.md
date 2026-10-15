# Codex-Native SDD Harness Adaptation

This document records the approved design and its implementation closeout.
The correction record identifies subsequent changes. Use the [README](../README.md)
for installation and operation, and the canonical files under `template/` for
current executable behavior and agent contracts. Future-tense passages below
record the original design intent, not unfinished functionality.

## Summary

Build `codex-harness` as the source repository for a reusable, English-language template under `template/`. The reference repository remains untouched. The template will support the Codex desktop app and Codex CLI, use ChatGPT authentication without API keys, and work with target applications written in any language; only the harness control plane will require Python 3.11+ standard library.

Preserve the reference’s core invariants:

- One active feature at a time.
- Strict EARS requirements with stable requirement IDs.
- `requirements → design → tasks → human approval → implementation → independent review → done`.
- Persistent, repository-owned state and progress artifacts.
- Executable validation and requirement-to-test traceability.
- No automatic push or publication.

Replace the Claude-specific layer as follows:

| Reference mechanism | Codex-native replacement |
|---|---|
| `CLAUDE.md` forces the leader role | Root `AGENTS.md` supplies the durable policy and routes SDD work to a repository skill. Codex reads repository `AGENTS.md` automatically. [Official AGENTS.md documentation](https://learn.chatgpt.com/docs/agent-configuration/agents-md) |
| `.claude/agents/leader.md` | The primary Codex session is the coordinator; there is no redundant leader subagent. Detailed orchestration lives in `.agents/skills/sdd-workflow/SKILL.md`. Repository skills can be invoked explicitly or implicitly, while custom prompts are deprecated. [Official skills documentation](https://learn.chatgpt.com/docs/build-skills), [custom-prompts deprecation](https://learn.chatgpt.com/docs/custom-prompts) |
| Claude `spec_author`, `implementer`, and `reviewer` Markdown agents | Project-scoped `.codex/agents/*.toml` custom agents. They inherit the parent model and reasoning level because the template will not pin a model. [Official subagents documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents) |
| `.claude/settings.json` hooks | Trusted project hooks in `.codex/hooks.json`, backed by cross-platform Python handlers and separate Windows/POSIX commands. [Official hooks documentation](https://learn.chatgpt.com/docs/hooks) |
| Claude `permissions.allow` entries | No direct allow-list port. Verification commands run through the normal Codex sandbox as structured, non-shell subprocesses. Project execution rules are unnecessary unless a target later needs commands outside the sandbox. |
| Root `feature_list.json`, `specs/`, `progress/`, and generic `docs/` | A visible `harness/` namespace that avoids collisions in existing repositories while keeping specs and progress easy to inspect. |
| Notes CLI and Unix-specific commands | A language-neutral command configuration, Windows/POSIX command variants, and a small disposable test fixture rather than a bundled Notes application. |

At the original design baseline, the installed Codex client was authenticated through ChatGPT and exposed hooks and multi-agent support. The implementation therefore does not add the OpenAI SDK, an API key, model credentials, or direct Responses API calls. ChatGPT account sign-in is a supported Codex setup path. [Official quickstart](https://learn.chatgpt.com/docs/quickstart)

## Template and Control-Plane Design

### Repository layout

Keep development and distribution separate:

```text
codex-harness/
├── README.md
├── AGENTS.md
├── template/
│   ├── AGENTS.md
│   ├── .agents/
│   │   └── skills/
│   │       └── sdd-workflow/
│   │           └── SKILL.md
│   ├── .codex/
│   │   ├── config.toml
│   │   ├── hooks.json
│   │   └── agents/
│   │       ├── sdd-spec-author.toml
│   │       ├── sdd-implementer.toml
│   │       └── sdd-reviewer.toml
│   └── harness/
│       ├── config.json
│       ├── features.json
│       ├── checkpoints.md
│       ├── docs/
│       │   ├── architecture.md
│       │   ├── conventions.md
│       │   ├── sdd.md
│       │   └── verification.md
│       ├── specs/
│       ├── progress/
│       │   ├── current.md
│       │   ├── history.md
│       │   └── reviews/
│       └── scripts/
│           ├── harnessctl.py
│           ├── codex_hook.py
│           └── harness_core/
│               ├── __init__.py
│               ├── repository.py
│               ├── specs.py
│               ├── state.py
│               ├── runner.py
│               ├── inspection.py
│               └── workflow.py
└── tests/
    └── fixtures/
```

The root `AGENTS.md` governs development of `codex-harness` itself. The template’s `AGENTS.md` is the file copied into target projects. Template tests import or invoke the canonical `harnessctl.py` facade directly from `template/`; its internal package separates repository access, specification parsing, state validation, command execution, inspection, and workflow gates. Internal dependencies point toward those lower-level responsibilities and never back to the facade. There is no duplicate generated copy of the control-plane implementation.

### Codex configuration

- `.codex/config.toml` will enable/configure project subagents and set a conservative concurrency cap, but it will not set a model, reasoning effort, API provider, API key, global sandbox mode, or network access.
- The spec author and implementer inherit the parent session’s permissions. They require a workspace-writable parent turn.
- The reviewer is configured read-only. It reviews the implementation, specs, tests, task completion, and a fresh verification artifact, but does not edit code or create its own report.
- The primary coordinator converts the reviewer’s structured result into repository artifacts and performs the final verification gate.
- Do not depend on beta permission profiles for correctness. They can be overridden by live runtime choices and do not compose with older sandbox settings. [Official permissions documentation](https://learn.chatgpt.com/docs/permissions)
- Project configuration and hooks only load for a trusted project. Onboarding will explicitly tell users to trust the project and review the exact hooks through `/hooks`; changed hook definitions require renewed trust. [Config trust behavior](https://learn.chatgpt.com/docs/config-file/config-basic), [hook trust behavior](https://learn.chatgpt.com/docs/hooks)

### `harness/config.json`

Define a versioned, language-neutral configuration:

```json
{
  "schema_version": 1,
  "project": {
    "name": "REPLACE_ME"
  },
  "workflow": {
    "max_review_cycles": 3,
    "require_clean_worktree": true
  },
  "commands": {
    "bootstrap": [],
    "verify": []
  },
  "git": {
    "auto_commit_on_done": false,
    "commit_message": "feat({feature_name}): {feature_title}"
  }
}
```

Each command group is an ordered list of structured steps:

```json
{
  "name": "unit-tests",
  "argv": ["python", "-m", "unittest", "discover"],
  "windows_argv": ["py", "-3", "-m", "unittest", "discover"],
  "posix_argv": ["python3", "-m", "unittest", "discover"],
  "cwd": ".",
  "env": {},
  "timeout_seconds": 600
}
```

Command behavior is fixed:

- Select the platform-specific `argv` when present; otherwise use the common `argv`.
- Execute directly without a shell.
- Resolve `cwd` relative to the Git root and reject traversal outside it.
- Merge non-secret configured environment values into the inherited environment.
- Run steps sequentially and stop at the first failure or timeout.
- Require at least one `verify` step before an SDD feature can enter implementation.
- Persist only step names, exit codes, durations, timestamps, and content fingerprints. Do not persist full stdout/stderr automatically.
- Print failing command output to the active Codex turn while warning users not to place secrets in command arguments or the checked-in configuration.

### `harness/features.json`

Use a versioned schema with positive integer IDs so “next feature” is deterministic:

```json
{
  "schema_version": 1,
  "project": "REPLACE_ME",
  "features": [
    {
      "id": 1,
      "name": "example_feature",
      "title": "Example feature",
      "description": "Replace or remove this example.",
      "acceptance": [],
      "sdd": true,
      "status": "pending",
      "approval": null,
      "block": null
    }
  ]
}
```

Supported states remain:

```text
pending → spec_ready → in_progress → done
                     ↘ blocked ↗
```

Control-plane invariants:

- IDs and names are unique.
- Names are stable filesystem-safe slugs.
- At most one feature is `in_progress`.
- A non-legacy SDD feature in `spec_ready`, `in_progress`, or `done` has all three spec files.
- A feature cannot move directly from `pending` to `in_progress`.
- `done` is immutable through normal control-plane commands.
- A blocked feature records its prior state, UTC timestamp, and reason. Resuming requires explicit user direction and restores only a valid prior state.
- A feature may remain `in_progress` across reviewer change requests.
- After three unsuccessful review cycles by default, the coordinator records the feature as blocked and returns control to the human.

### Control-plane CLI

`harness/scripts/harnessctl.py` will expose these stable commands:

```text
doctor
status [--json]
validate
run bootstrap
run verify
spec-ready FEATURE
approve FEATURE
record-review FEATURE --input REVIEW_JSON
complete FEATURE
block FEATURE --reason TEXT
resume FEATURE
```

Behavior:

- `doctor` checks Python version, Git availability, required template files, configuration completeness, JSON schemas, spec structure, and configured command executables.
- `status` reports the active feature, next pending feature, gate state, approval freshness, latest verification, and latest review.
- `validate` performs fast structural checks without running the target project’s full test suite.
- `run bootstrap` and `run verify` execute their configured command groups and return machine-readable results. Only `run verify` persists completion evidence in `harness/progress/verification.json`.
- `spec-ready` is allowed only from `pending`, after the three spec files pass structural and EARS checks.
- `approve` is allowed only from `spec_ready` and only when invoked by the coordinator in response to an explicit human approval message. It verifies a clean Git worktree, calculates the approved-spec digest, records the current Git `HEAD` as the implementation baseline, and moves the feature to `in_progress`.
- Because the spec-author phase creates tracked artifacts, users must commit those reviewed spec/state changes before approval. Unrelated existing work must likewise be committed or stashed.
- `record-review` validates and stores the reviewer result against the implementation fingerprint. Expected checkpoint names come only from `harness/checkpoints.md`: every checklist item must appear exactly once, with its full text after the checkbox, preserving inline Markdown and punctuation. Missing, duplicate, unknown, or malformed review entries are rejected. The catalog must be readable, non-empty, and contain no duplicate or malformed checklist entries. `APPROVED` requires every checkpoint's `passed` value to be `true`; `complete` revalidates the stored JSON against this catalog before changing state.
- `complete` requires current approval, all tasks checked, an `APPROVED` review for the current implementation fingerprint, and a successful current verification. It then marks the feature done, appends history, and resets `current.md`.
- `block` and `resume` preserve the previous state and reason rather than silently discarding progress.

The approval digest will hash the three spec files in a fixed order using UTF-8 and normalized LF line endings. Task checkbox markers will be normalized from `[x]`/`[X]` back to `[ ]` before hashing, so checking off an approved task does not invalidate approval; changing task text, requirements, or design does invalidate it.

### Git behavior

- Git is required because approval scope, review scope, content fingerprints, and optional auto-commit depend on a stable baseline.
- `git.auto_commit_on_done` defaults to `false`.
- When disabled, the harness never stages or commits automatically.
- When enabled:
  - Approval still requires a clean worktree.
  - Completion derives the exact changed-path list from the recorded baseline.
  - The control plane stages explicit paths one by one; it never uses `git add .` or `git add --all`.
  - It creates one commit using the configured message template after status, review, history, and completion evidence have been written.
  - It never pushes, opens a pull request, creates a remote, or changes branches.
  - If staging or committing fails, the harness does not reset, discard, or rewrite user changes. It reports the failure and leaves the completed work available for manual recovery.

## SDD Workflow and Agent Contracts

### Primary coordinator and skill

The template’s `AGENTS.md` stays concise and acts as a navigation and safety map. It directs implementation requests—such as “implement the next pending feature”—to `$sdd-workflow`. Pure repository questions and read-only exploration do not invoke the multi-agent workflow.

The `sdd-workflow` skill defines the complete state machine:

1. Run `doctor`, inspect `status`, and read only the relevant project policy documents.
2. Select the lowest-ID actionable feature.
3. For `pending`, spawn exactly one `sdd_spec_author`, validate its files, transition to `spec_ready`, and stop for human review.
4. Present the three spec paths and explain that the reviewed phase-one artifacts must be committed before approval.
5. On a later explicit approval, run `approve`; never infer approval from silence, a previous session, or a general implementation request.
6. Spawn one `sdd_implementer` sequentially. Parallel write agents are prohibited.
7. Run full configured verification through the neutral control plane.
8. Spawn one read-only `sdd_reviewer`, supplying the feature, approved spec path, implementation baseline, and verification artifact.
9. Record the structured verdict.
10. If changes are requested, return the findings to the implementer, re-run verification, and repeat review up to the configured limit.
11. If approved, re-run or confirm a fingerprint-current final verification and invoke `complete`.
12. If an invariant, tool, spec, or verification gate cannot be satisfied, record a blocker instead of inventing a workaround.

Read-heavy explorers may be used for genuinely complex repository investigation, but they do not edit and do not replace the spec author, implementer, or reviewer.

### `sdd_spec_author`

- Writes exactly one feature’s `requirements.md`, `design.md`, and `tasks.md`.
- May update `harness/progress/current.md` and implementation-neutral planning artifacts.
- Does not edit application source or tests.
- Uses strict English EARS:
  - `The system MUST ...`
  - `WHEN ..., the system MUST ...`
  - `WHILE ..., the system MUST ...`
  - `WHERE ..., the system MUST ...`
  - `IF ... THEN the system MUST ...`
- Assigns stable `R1`, `R2`, … identifiers.
- Uses one `MUST` obligation per requirement.
- Maps every original acceptance criterion to at least one requirement.
- Produces ordered `T1`, `T2`, … tasks, each referencing one or more requirements.
- Stops with a blocker if acceptance criteria are insufficient rather than inventing product behavior.
- Does not transition the feature directly; the coordinator calls `spec-ready` after validation.

### `sdd_implementer`

- Requires `in_progress`, a fresh approval digest, all three spec files, and the recorded implementation baseline.
- Implements exactly one feature and preserves unrelated files.
- Follows tasks in order, adds tests alongside behavior, marks task checkboxes, and maintains `harness/progress/impl_<feature>.md`.
- Records an explicit `R<n> → test or verification evidence` map.
- Does not mark the feature done and does not approve its own work.
- Stops and records a blocker when implementing would require an unapproved spec change.
- On reviewer change requests, fixes only the documented findings before returning for another verification/review cycle.

### `sdd_reviewer`

- Runs in read-only mode.
- Independently inspects the approved spec, current diff relative to the recorded baseline, tests, implementation report, checkpoints, and fresh verification evidence.
- Rejects stale approval, stale verification, uncovered requirements, incomplete tasks, architecture violations, unintended scope, or unaddressed acceptance criteria.
- Returns a strict JSON verdict to the coordinator with:
  - schema version and feature name;
  - reviewed implementation fingerprint;
  - `APPROVED` or `CHANGES_REQUESTED`;
  - per-requirement coverage and evidence;
  - task and checkpoint results;
  - concrete findings with paths and actionable remediation.
- Does not edit source, tests, feature state, specs, or progress files.
- The coordinator writes the returned JSON to `harness/progress/reviews/<feature>.json` and creates a concise Markdown companion for human review.

## Hooks and Enforcement

Use `.codex/hooks.json` with `command` for POSIX and `commandWindows` for Windows:

Both launch commands use `git rev-parse --show-toplevel` to resolve the adapter
from the Git root rather than the current directory. The POSIX command quotes
the resulting script path; Windows passes the resolved path as a subprocess
argument. Root and nested invocation support paths with spaces. This changes
script discovery while preserving the `PostToolUse` and `Stop` JSON contracts.

- `PostToolUse`, matcher `apply_patch|Edit|Write`:
  - Run `harnessctl validate`.
  - Perform only fast structural/state checks.
  - If a completed edit leaves invalid state, return blocking feedback to Codex so it repairs or records the issue.
  - Do not run the full target test suite after every edit.

- `Stop`:
  - Read the Codex hook event JSON from stdin.
  - Always perform structural validation.
  - With an active `in_progress` feature, skip the initial full verification only if approval is current, the implementation content digest is empty relative to the approval baseline, and no verification artifact exists. Approval-only coordinator state does not count as implementation content.
  - Otherwise, run configured full verification unless the latest evidence is successful and matches both the active feature and its current implementation fingerprint. Prior failed evidence still triggers verification, even without implementation changes.
  - If verification fails and `stop_hook_active` is false, return a Codex `decision: block` result so the turn continues with the failure reason.
  - If the continuation fails again with `stop_hook_active` true, stop without an infinite loop, preserve `in_progress`, and surface the failure for the coordinator to record as blocked.
  - If no implementation is active, avoid an unnecessary full test run.
  - Emit valid JSON on successful `Stop` execution, as required by Codex’s hook contract.

Hooks are guardrails, not the sole enforcement boundary. The authoritative transitions in `harnessctl.py` independently re-check every gate, so disabling or failing to trust a hook cannot make an invalid feature complete.

## Documentation and Verification

### Documentation

Expand the existing user-authored README without discarding its goals. Document:

- Architecture and Claude-to-Codex migration rationale.
- Template installation by copying `template/` contents into a target Git repository.
- Python 3.11+, Git, Codex desktop/CLI, and ChatGPT sign-in prerequisites.
- Project and hook trust steps.
- How to customize architecture, conventions, verification commands, and checkpoints.
- How to add a pending feature.
- The two-turn human approval flow.
- Explicit `$sdd-workflow` invocation and implicit “implement the next pending feature” behavior.
- Windows commands using `py -3` and POSIX commands using `python3`.
- Opt-in auto-commit behavior and the guarantee that the harness never pushes.
- Known limitation that project instructions, agents, config, and hooks are Codex-local features and may be skipped in untrusted projects.

### Automated tests

Use only Python standard-library tests and temporary Git repositories.

Cover:

- Configuration parsing, required fields, platform command selection, relative working directories, environment merging, timeouts, sequential execution, and fail-fast behavior.
- Rejection of shell strings, empty executables, out-of-repository `cwd`, invalid timeouts, and missing verification commands.
- Feature schema validation, duplicate IDs/names, invalid states, more than one `in_progress`, missing specs, and invalid blockers.
- Every valid and invalid state transition.
- Strict EARS parsing, stable IDs, one obligation per requirement, task-to-requirement references, and completed-task checks.
- Approval digest stability across LF/CRLF and task checkbox changes.
- Approval invalidation after requirement, design, or task-text edits.
- Clean-worktree approval enforcement and stored baseline validation.
- Verification and review fingerprint freshness.
- Reviewer approval and change-request schemas.
- Review-cycle limit and blocked/resume behavior.
- Completion rejection for stale approval, stale verification, incomplete tasks, missing traceability, or non-approved review.
- Auto-commit disabled by default.
- Auto-commit enabled with exact-path staging, templated commit message, no push, and non-destructive failure behavior.
- Hook stdin/stdout contracts for `PostToolUse` and `Stop`, including one continuation and recursion prevention.
- Static parsing of `.codex/config.toml`, all custom-agent TOML files, `hooks.json`, and the skill front matter.
- Assertions that the template contains no Claude paths, Claude tool names, model pins, API keys, OpenAI SDK dependency, Notes CLI assumptions, `/tmp`-only behavior, or Unix-only command requirement.

### Integration acceptance

In a temporary Git repository copied from `template/`:

1. Replace required placeholders and configure a tiny Python fixture’s verification command.
2. Add one pending SDD feature.
3. Run `doctor`.
4. Create valid strict-EARS specs and transition to `spec_ready`.
5. Commit the phase-one spec/state artifacts to establish a clean approval baseline.
6. Approve and confirm the stored digest and baseline.
7. Apply a fixture implementation and tests.
8. Produce a failed verification and prove completion is blocked.
9. Fix the fixture and produce a successful verification artifact.
10. Record a `CHANGES_REQUESTED` review and prove completion remains blocked.
11. Record an `APPROVED` review for the current fingerprint and complete the feature.
12. Confirm history/current-state cleanup and optional exact-path commit behavior.
13. Run the full harness test suite on Windows.
14. Validate both Windows and POSIX command-selection branches in unit tests; do not claim native POSIX execution until it is exercised on a POSIX host or CI runner.
15. Parse the template through the installed Codex client in strict-config mode without starting an API-backed application or requiring an API key.

### Implementation closeout

Completed on 2026-08-27:

- The canonical suite passes on Windows and Ubuntu under WSL; the latter exercises
  native POSIX command execution rather than only mocking the platform selector.
- `.github/workflows/tests.yml` continuously exercises `windows-latest` and
  `ubuntu-latest` with Python 3.11 and 3.13.
- The installed-Codex smoke test parses an isolated copy of the template
  configuration with `--strict-config`. A deliberately unknown field is rejected,
  proving the test reaches strict configuration parsing without starting a model
  turn or requiring an API key.
- The state tests now cover every state-changing transition command against every
  valid and invalid source state, including block/resume restoration from all
  three resumable states.
- Reviewer verdict validation rejects duplicate requirement/checkpoint entries,
  empty evidence or findings, failed checkpoints under `APPROVED`, and
  `CHANGES_REQUESTED` without an actionable finding.

### Correction record: 2026-10-14

Original correction commit: `e8c41653c3579b1c105c98476c1ee195912d4f65`.
Git-root hook discovery, exact checkpoint coverage, stored-review revalidation,
and the narrow initial `Stop` optimization are implemented on this maintained
line. `tests/test_regressions.py` covers root/subdirectory invocation with spaces,
platform-specific launch commands, invalid checkpoint catalogs and verdicts,
stored-review tampering, implementation changes, prior failures, and approval-only
state. Native hook cases run only on their matching OS; platform selection tests
alone do not establish native execution on another OS. Completion retains its
independent approval, task, traceability, verification, and review gates.

### Documentation review: 2026-10-14

Presentation was reviewed against the
[Repository Documentation Readability Guide, version 0.2](https://github.com/angel-wm/repository-documentation-readability/blob/65c2f82c9e76b4340320618e42a7e3a59332ffe7/GUIDE.md).
This is guidance, not a certification or an additional SDD gate. The README provides
entry paths, installation, operation, and recovery; the existing design, template
policy, workflow skill, and agent contracts retain their own responsibilities.
Examples and detailed rules are linked to their existing sources where practical.
No RRD skill is installed. Additional diagrams, document hierarchies, and documentation
linters were unnecessary for this scope; the existing text and file trees suffice.

## Assumptions and Boundaries

- `harness-sdd-reference` is read-only reference material and will not be edited.
- The template is generic; the Notes CLI will not be copied into the distributable template.
- Target projects must use Git and Python 3.11+ for the harness control plane, but their application language and build system are unrestricted.
- Model and reasoning choices remain user/session controlled; subagents inherit them.
- The default auto-commit setting is off. Even when enabled, there is never an automatic push, branch creation, pull request, remote mutation, or publication.
- The implementation task itself will not create a Git commit or remote change unless the user separately authorizes that exact action.
- A human approval message authorizes only the exact normalized spec digest recorded at that gate.
- Structural hooks improve feedback speed, while state transitions and completion commands remain the authoritative enforcement layer.
