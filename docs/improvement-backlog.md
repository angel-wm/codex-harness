# Harness improvement backlog

This document tracks proposed improvements to `codex-harness`, their explicit decisions, and implementation evidence. It is separate from the [approved harness design](codex-native-sdd-harness-adaptation.md) and from the feature queue installed into target projects at `template/harness/features.json`.

An agreed design direction is **not** approval to change executable code. No item below is implemented merely because it was discussed.

## EVAL-001: Model compatibility and code-quality evaluations

**Status:** Design under discussion. Scope and principles agreed; implementation not started or verified.

### Purpose

Evaluate whether a newly selected Codex model respects harness rules and generates acceptable code. Diagnose failures and recommend specific, evidence-backed changes so the harness can be adapted to the **latest** model. Preserving compatibility with an older model is not a requirement.

### Agreed direction

| Area | Decision |
| --- | --- |
| Triggers | Run on demand when a new model becomes available or the harness changes; do not assume automatic discovery of new model releases |
| Branch coverage | Separate evaluations of `master`, `legacy/monolithic`, and `experimental`; implement on one branch first, then extend |
| Comparisons | Allow direct branch/model comparisons and preserve prior results; evaluation of a new model must not always require rerunning an older one |
| Evaluation targets | Measure both harness rule compliance and generated-code quality, separately |
| Critical invariants | Require 100% pass on human approval, state transitions, scope boundaries, safety constraints, and established SDD gates |
| Reviewer competence | Include deliberately defective implementations and test whether the **actual model reviewer** identifies the seeded defects |
| Existing tests | Retain deterministic unit, integration, regression, and hook tests; add real-model evaluations instead of duplicating those tests |
| Hook coverage | Test deterministic hook handler behavior separately from whether Codex Desktop actually triggers trusted project hooks |
| Test levels | Individual/component cases for focused, lower-consumption evaluations and optional full end-to-end SDD cases |
| Languages | Start with a small Python fixture; broader language coverage only if evidence justifies it |
| Environments | Use isolated temporary test repositories/worktrees, retaining the ability to inspect results before cleanup |
| Failure handling | Stop the affected scenario on a critical failure but continue unrelated scenarios |
| Execution | Prefer manual/on-demand launch at first; do not introduce a paid OpenAI API dependency |
| Consumption | Measure real usage before selecting limits; offer quick and full suites, with selective reruns of uncertain cases |
| Reporting | Produce readable Markdown explanations and structured machine-readable evidence for future Codex handoffs |
| Diagnoses | Report violated criteria, supporting evidence, suspected components, and recommended changes; **never automatically apply repairs** |
| Acceptance | Require 100% passing critical checks; set separate numerical quality thresholds after calibration |
| Change control | Explicit human approval is required before implementing fixes; track the resulting decision and independent verification |

### Existing coverage and gap

Current tests exercise SDD transitions, invalid or contradictory review payloads, failed verification, reviewer-verdict recording, and the hooks' Python handlers. Some tests deliberately inject invalid states and predetermined `APPROVED`/`CHANGES_REQUESTED` payloads. **They do not demonstrate that a live model reviewer detects seeded bugs**. Current GitHub Actions runs Python tests and does not invoke a model.

Relevant references:

- [Integration acceptance test](../tests/test_integration_acceptance.py)
- [Review and state tests](../tests/test_workflow.py)
- [Hook and template tests](../tests/test_hooks_and_template.py)
- [Hook regression tests](../tests/test_regressions.py)
- [Current GitHub Actions workflow](../.github/workflows/tests.yml)

### Open decisions and risks

- **Codex Desktop launch:** confirm the exact in-app launch workflow, whether ordinary prompts, reusable skills, or desktop automations best serve on-demand execution; do not rely on an undocumented custom slash command.
- **Codex CLI:** optional only; assess security/account-session concerns before proposing a separate sign-in. User prefers Desktop and wishes to avoid extra sign-ins.
- **CI boundary:** GitHub Actions can validate evaluators and uploaded/committed results, but it cannot directly drive a logged-in Desktop session on the user's computer.
- **Costs:** benchmark usage and runtime before setting budgets; avoid presenting token estimates as measured.
- **Scoring:** specify deterministic expected results, seeded bugs, code-quality rubric, minimal acceptable baselines, and failure-attribution logic.
- **Comparisons:** decide exactly how baseline results, branch-specific fixtures, model versions, and execution settings are recorded.
- **Storage and cleanup:** choose the retention location and policy for disposable repositories, logs, traces, and reports.
- **Coverage rollout:** select first branch, minimal useful case set, and subsequent acceptance gates.

### Implementation and evidence

**Implementation:** Not started. No evaluation code, workflows, fixtures, or model-backed runs have been added by this backlog entry.

**Decision on implementation:** Pending completion of the design interview and separate authorization.

**Evidence:** No model-evaluation results yet. Once implemented, record test commands, revision, model, configuration, outcome, resource use, and links to reproducible artifacts.

## Adding another proposal

Add a distinct section with a stable ID, purpose, alternatives, agreed decisions, unresolved questions, acceptance criteria, expected cost when applicable, implementation status, and verification evidence. Distinguish proposal, approval, implementation, and verification; never infer one from another.
