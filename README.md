# Codex Harness

Reusable development harness designed for Codex.

Goals:

- Use Codex through ChatGPT authentication, without requiring the OpenAI API.
- Provide persistent project state.
- Support specification-driven development.
- Separate implementation and review responsibilities.
- Provide validation gates and resumable workflows.
- Remain reusable across programming languages and repositories.

The initial architectural reference is `BettaTech/harness-sdd`. This repository
is an independent Codex-oriented implementation and is not coupled to a specific
application. The sibling reference checkout is never part of the distributable
template.

## What the template provides

Copying `template/` into a target Git repository adds four cooperating layers:

1. `AGENTS.md` supplies durable repository policy and routes implementation
   requests to the local `sdd-workflow` skill.
2. `.agents/skills/sdd-workflow/SKILL.md` coordinates the human-gated state
   machine.
3. `.codex/agents/` defines a spec author, sequential implementer, and independent
   read-only reviewer. No model or reasoning effort is pinned.
4. `harness/scripts/harnessctl.py` is the authoritative standard-library control
   plane. Hooks improve feedback speed, but cannot bypass its transition gates.

The persistent project data lives under `harness/` to reduce collisions with an
existing application's files:

```text
harness/
├── config.json               # structured bootstrap/verification and Git policy
├── features.json             # deterministic feature queue and state
├── checkpoints.md            # objective review checklist
├── docs/                     # target architecture, conventions, SDD, verification
├── specs/<feature>/          # requirements.md, design.md, tasks.md
├── progress/                 # current state, history, reports, reviews, evidence
└── scripts/                  # dependency-free control plane and hook adapter
```

## Prerequisites

- A Git repository with at least one commit.
- Python 3.11 or newer for the harness control plane.
- Codex desktop or Codex CLI, signed in with ChatGPT.
- A project/application verification command. The application itself may use any
  language or build system.

The harness does not install the OpenAI SDK, read an API key, pin a provider, or
call the Responses API. Model and reasoning choices remain controlled by the
active Codex session.

## Install into a target repository

Review the template before copying it. From this repository, copy all entries,
including hidden `.agents` and `.codex` directories.

Windows PowerShell:

```powershell
$target = 'C:\path\to\target-repository'
Get-ChildItem -Force -LiteralPath '.\template' |
    Copy-Item -Destination $target -Recurse -Force
Set-Location -LiteralPath $target
```

POSIX:

```bash
cp -a template/. /path/to/target-repository/
cd /path/to/target-repository
```

Then:

1. Replace `REPLACE_ME` with the same project name in `harness/config.json` and
   `harness/features.json`.
2. Replace the template architecture and conventions with target-specific policy.
3. Configure at least one `commands.verify` step. Bootstrap may remain empty.
4. Replace or remove the example feature.
5. Commit the installed and customized harness.
6. Open the repository in Codex and explicitly trust the project.
7. Use `/hooks` to inspect the exact hook commands before trusting them. If hook
   definitions change, review and trust the new definitions again.

Project instructions, agents, configuration, and hooks are Codex-local features.
Codex can skip them in an untrusted project, so trust is part of onboarding—not a
silent assumption.

## Configure commands

Command groups are ordered arrays. Each step is executed directly, never through
a shell:

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

The platform-specific vector wins when present; otherwise `argv` is used. `cwd`
must remain inside the Git root. Steps run sequentially and stop at the first
failure or timeout. Only metadata and fingerprints are persisted; failing output
is printed to the active turn. Never put secrets in checked-in configuration or
command arguments.

Run the initial checks on Windows:

```powershell
py -3 harness/scripts/harnessctl.py doctor
py -3 harness/scripts/harnessctl.py status --json
```

On POSIX:

```bash
python3 harness/scripts/harnessctl.py doctor
python3 harness/scripts/harnessctl.py status --json
```

`doctor` intentionally fails until placeholders are replaced and a verification
command is configured. `validate` performs fast structural checks without running
the application test suite.

## Add a feature

Add a positive, unique ID and stable snake-case name to
`harness/features.json`:

```json
{
  "id": 2,
  "name": "export_report",
  "title": "Export a report",
  "description": "Export the current data as a report.",
  "acceptance": [
    "The requested output is written to the selected path."
  ],
  "sdd": true,
  "status": "pending",
  "approval": null,
  "block": null,
  "review_cycles": 0
}
```

IDs make “next feature” deterministic. At most one feature may be
`in_progress`; normal commands never reopen `done`.

## Run the two-turn SDD workflow

Invoke the skill explicitly with `$sdd-workflow`, or ask Codex to “implement the
next pending feature.” Pure questions and read-only inspection do not activate the
multi-agent workflow.

### Turn one: specification

The coordinator runs `doctor`, selects the lowest-ID actionable feature, and
spawns exactly one spec author. The author creates:

```text
harness/specs/<feature>/requirements.md
harness/specs/<feature>/design.md
harness/specs/<feature>/tasks.md
```

Requirements use strict English EARS with stable `R1`, `R2`, … identifiers and
one uppercase `MUST` obligation each. Each requirement includes an explicit
acceptance mapping such as `Acceptance: A1, A2`. Tasks use ordered `T1`, `T2`, …
checkboxes and requirement references.

After `spec-ready`, the workflow stops. Review the three files and feature-state
change. Commit those reviewed phase-one artifacts so approval can begin from a
clean, stable Git baseline.

### Turn two: explicit approval and implementation

Send an explicit approval message naming the current feature. Silence, a previous
session, or a general request to continue is not approval. The coordinator then:

1. Revalidates the spec and clean worktree.
2. Records the normalized spec digest and current `HEAD` baseline.
3. Spawns one sequential implementer.
4. Runs configured full verification.
5. Spawns the independent read-only reviewer.
6. Records its structured verdict for the current implementation fingerprint.
7. Returns concrete change requests to the implementer, if any, and repeats up to
   `max_review_cycles`.
8. Completes only after current approval, checked tasks, explicit requirement
   traceability, successful current verification, and an `APPROVED` current
   review all agree.

Reviewer JSON is validated as a strict contract. Requirement entries must be
unique and complete, checkpoint entries must be unique and well-formed, evidence
and findings must be non-empty, `APPROVED` requires all requirements and
checkpoints to pass, and `CHANGES_REQUESTED` requires at least one actionable
finding.

Checking task boxes does not invalidate approval. Changing requirement text,
design, or task text does. A blocked feature preserves its prior state, timestamp,
and reason; `resume` requires explicit human direction.

## Command reference

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

Run `--help` on a command for syntax. State-changing commands independently
recheck their gates; hooks are never the sole enforcement boundary.

## Git guarantees

`git.auto_commit_on_done` is `false` by default. With that default, the harness
never stages or commits.

When explicitly enabled, completion derives the exact changed paths from the
recorded approval baseline, stages each path separately, and creates one commit
from the configured message template. It never uses repository-wide staging.
Commit failure is non-destructive: no reset, checkout, or discarded change occurs.

In every mode, the harness never pushes, publishes, creates or changes branches,
opens a pull request, adds a remote, or mutates an existing remote.

## Hooks

The trusted `PostToolUse` hook runs fast `validate` checks after writes. The
trusted `Stop` hook always validates and runs full verification only when an
`in_progress` implementation differs from its last successful verification. A
failure requests one continuation; `stop_hook_active` prevents an infinite loop.

If hooks are disabled or untrusted, invalid work still cannot pass the
authoritative `approve`, `record-review`, or `complete` commands.

## Develop and verify this repository

The canonical scripts live only under `template/`; tests import or execute that
copy directly. Run on Windows:

```powershell
py -3 -m unittest discover -s tests -v
```

Run on POSIX:

```bash
python3 -m unittest discover -s tests -v
```

The suite uses Python standard library and disposable Git repositories. It covers
configuration, safe command execution, schemas, strict EARS parsing, transitions,
approval normalization, Git baselines, verification/review freshness, completion,
optional exact-path commits, hook contracts, Codex configuration parsing, and a
complete integration acceptance flow.

The suite has been exercised directly on Windows and Ubuntu under WSL. The
checked-in CI matrix repeats it on native `windows-latest` and `ubuntu-latest`
runners with Python 3.11 and 3.13. When an installed Codex CLI is available, an
additional smoke test copies the template configuration into an isolated Codex
home, parses it with `--strict-config`, and uses an unknown-field negative control
to prove strict parsing is active without starting a model turn.

## Design and documentation

The approved implementation design is in
[`docs/codex-native-sdd-harness-adaptation.md`](docs/codex-native-sdd-harness-adaptation.md).
Codex configuration follows the official documentation for
[AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md),
[subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents),
[skills](https://learn.chatgpt.com/docs/build-skills), and
[hooks](https://learn.chatgpt.com/docs/hooks).
