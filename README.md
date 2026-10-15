# Codex Harness

Reusable specification-driven development (SDD) harness for developers using
Codex in Git repositories. It keeps specifications, human approval, implementation,
verification, and independent review in a resumable workflow. Target applications
may use any language; the harness requires Python 3.11+ and Git.

Start with [installation](#install-into-a-target-repository), then
[the two-turn workflow](#run-the-two-turn-sdd-workflow). For existing installations,
see [maintenance and recovery](#maintenance-and-recovery). For internals, see
[the approved design](docs/codex-native-sdd-harness-adaptation.md#template-and-control-plane-design).

## Maintained variants

This branch, `experimental`, derives from the modular `master` line and adds
only coordinator communication preferences to the template. `harnessctl.py`
remains the stable facade while the control-plane logic is distributed across
`harness_core/`. See [the experimental variant](docs/experimental.md) for its
scope, source, exact differences, and reversal instructions. `master` remains
the stable modular line.
The `legacy/monolithic` branch preserves the original monolithic line, with its
main logic concentrated in `harnessctl.py`.

`v1-monolithic` is the fixed initial snapshot of the monolithic variant, and
`v2-modular` is the fixed initial snapshot of the reviewed modular variant. The
branches may continue to evolve independently while these tags remain immutable.
The presence of `v2-modular` does not make the monolithic variant obsolete or
make the modular variant the required or recommended choice; both are retained
intentionally so they can be developed and evaluated separately.

After cloning the repository, select a maintained line or a fixed snapshot with:

```bash
git switch master
git switch legacy/monolithic
git switch experimental
git switch --detach v1-monolithic  # or v2-modular
```

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
└── scripts/
    ├── harnessctl.py         # stable CLI and import facade
    ├── codex_hook.py         # hook adapter
    └── harness_core/         # dependency-free control-plane responsibilities
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

Run the copy command from the selected source checkout into an existing target
Git repository. Review collisions in `AGENTS.md`, `.agents/`, `.codex/`, and
`harness/` first: these commands overwrite matching files. If any exist, merge the
needed entries individually while preserving target policy and state. Include
hidden `.agents` and `.codex` directories.

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
2. Customize [architecture](template/harness/docs/architecture.md),
   [conventions](template/harness/docs/conventions.md), and
   [review checkpoints](template/harness/checkpoints.md) for the target project.
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

Configure ordered command steps in `harness/config.json` using the
[verification policy and command example](template/harness/docs/verification.md).
Platform-specific argument lists override `argv`; steps run sequentially without
a shell and stop on failure or timeout. Bootstrap is optional. Full command output
is shown on failure; only `run verify` persists verification metadata and
fingerprints. Keep secrets out of checked-in configuration and arguments.

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

Use the [specification formats and traceability rules](template/harness/docs/sdd.md)
for strict English EARS requirements, acceptance mappings, and ordered tasks.

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

The [reviewer contract](template/.codex/agents/sdd-reviewer.toml) defines the
required JSON fields. The [control-plane review rules](docs/codex-native-sdd-harness-adaptation.md#control-plane-cli)
explain exact checkpoint coverage and stored-review revalidation at completion.

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

Both hooks locate `harness/scripts/codex_hook.py` from the Git root, so they
work from the root or subdirectories, including repository paths with spaces.
The configuration supplies separate Windows and POSIX launch commands.

The trusted `PostToolUse` hook runs fast `validate` checks after writes. The
trusted `Stop` hook always performs structural validation. It skips the initial
full verification only when approval is current, no implementation content has
changed from the approval baseline, and no prior verification evidence exists.
Otherwise, an active implementation requires verification unless a successful
result already matches its feature and fingerprint; failed evidence is never
ignored. A failure requests one continuation; `stop_hook_active` prevents an
infinite loop. `complete` still independently requires current approval, checked
tasks, traceability, successful current verification, and an approved current review.

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

## Maintenance and recovery

The root [development policy](AGENTS.md) governs this source repository. The
[installed policy](template/AGENTS.md) and [workflow skill](template/.agents/skills/sdd-workflow/SKILL.md)
govern target projects; target-specific rules belong in `harness/docs/`, while
`harness/specs/` and `harness/progress/` hold approved scope and execution evidence.
CLI `--help` describes accepted arguments. Keep detailed formats and changing
policy in these sources rather than copying them into the README.

Existing installations do not update automatically. Compare the selected branch's
`template/` with the installed files, merge changes while preserving target
configuration, policy, specs, and progress, then run `doctor` and the target's
configured verification. Review and trust changed hooks again. For harness
contributions, edit the canonical `template/` and run the suite above.

- If `doctor` reports placeholders, missing verification commands, or executables,
  finish configuration and check the selected platform's executable on `PATH`.
  Rerun `doctor`; a healthy installation returns `"ok": true` and exit code 0.
- If `approve` rejects a dirty worktree, inspect `git status`, preserve unrelated
  work, and commit the reviewed spec/state before retrying explicit approval.
  If the spec changed, obtain approval for the updated scope first.
- If completion rejects stale verification or review, inspect `status --json`,
  rerun `run verify`, and obtain and record an independent review for the current
  fingerprint. Retry `complete` only after all reported gates pass; do not edit
  stored evidence to bypass a rejection.

## Design and documentation

The approved implementation design is in
[`docs/codex-native-sdd-harness-adaptation.md`](docs/codex-native-sdd-harness-adaptation.md).
Codex configuration follows the official documentation for
[AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md),
[subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents),
[skills](https://learn.chatgpt.com/docs/build-skills), and
[hooks](https://learn.chatgpt.com/docs/hooks).
