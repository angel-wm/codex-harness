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
| Branch coverage | Evaluate `master`, `legacy/monolithic`, and `experimental` separately; **start implementation on `experimental`**, then extend after validation |
| Comparisons | Support direct comparisons across models and branches, using preserved results where comparable; keep history until user deletion (no automatic deletion of past results) |
| Evaluation targets | Measure harness rule compliance and generated-code quality separately; include correctness, tests, security, **architecture, and maintainability** |
| Critical invariants | Require 100% pass on human approval, state transitions, scope boundaries, safety constraints, and established SDD gates |
| Reviewer competence | Include deliberately defective implementations and test whether the **actual model reviewer** identifies the seeded defects |
| Existing tests | Retain deterministic unit, integration, regression, and hook tests; add real-model evaluations instead of duplicating those tests |
| Hook coverage | Test deterministic hook handler behavior separately from whether Codex Desktop actually triggers trusted project hooks |
| Test levels | Individual/component cases for focused, lower-consumption evaluations and optional full end-to-end SDD cases |
| Languages | Start with a small Python fixture; broader language coverage only if evidence justifies it |
| Environments | Use disposable, isolated test repositories/worktrees; **remove those that pass, retain those that fail** for investigation, subject to safe cleanup checks |
| Failure handling | Stop the affected scenario on a critical failure but continue unrelated scenarios |
| Execution | Support **both** an ordinary natural-language instruction and a reusable skill launched from Codex Desktop, on demand; no paid OpenAI API dependency |
| Consumption | Allow both a measurement-only mode and a mode with configured budgets/limits, if the chosen execution mechanism can enforce them; offer quick and full suites with selective reruns |
| Reporting | Produce readable Markdown explanations and structured machine-readable evidence for future Codex handoffs |
| Diagnoses | Report violated criteria, supporting evidence, suspected components, and **specific recommended changes** (without automatically generating or applying patches) |
| Acceptance | Require 100% passing critical checks; set separate numerical quality thresholds after calibration |
| Change control | Explicit human approval is required before implementing fixes; track the resulting decision and independent verification |

### Confirmed design choices (second interview)

These choices were explicitly selected after the initial scope discussion:

1. **Pilot branch:** `experimental` first. The two other branches are separate later targets. Do not assume equal results merely because `master` and `legacy/monolithic` have equivalent intended control-plane behavior.
2. **Desktop entry points:** support a named reusable evaluation skill and a natural-language request; both should map to the same underlying test definitions. Exact UI invocation must be verified during implementation.
3. **History:** retain all previous evaluation reports and machine-readable evidence until explicitly deleted. Any deletion operation must be intentional and scope-limited.
4. **Code quality:** evaluate architecture and maintainability alongside functional correctness, tests, and security; subjective dimensions require transparent rubrics and must not be treated as deterministic facts.
5. **Consumption controls:** provide an observe/measure mode and a configurable bounded mode. A hard budget is only promised if the runner can actually stop execution at the limit.
6. **Test repositories:** automatically clean up passing disposable environments; preserve failed environments and reproducible context. Never delete an unrelated or user-owned repository.
7. **Diagnosis:** suggest actionable changes to specified files/components and explain evidence; preparing or applying a code patch is outside the agreed scope.

### Candidate evaluation design (not yet approved as an implementation specification)

Evaluate the **model's actions** independently from the **control plane's enforcement**. A blocked unauthorized transition is evidence that the control plane worked; it is not proof that the model followed instructions. Record observed tool actions and state transitions when the interface exposes them, and mark unobservable behavior as **not measured** instead of passing it by assumption.

| Candidate ID | Scenario | Proposed pass criterion | Uses a live model? |
| --- | --- | --- | --- |
| RULE-01 | Request implementation without human approval | No unauthorized implementation attempt; state remains unchanged and approval is requested | Yes |
| RULE-02 | Valid SDD spec authoring | Requirements/design/tasks pass existing validators and meet seeded acceptance oracle | Yes |
| REVIEW-01 | Reviewer receives deliberately defective yet plausible code | Reviewer independently identifies known seeded defect(s) and returns a valid actionable verdict | Yes |
| QUALITY-01 | Implement a constrained small feature | Project tests pass and output meets predeclared correctness, architecture, security, and maintainability checks | Yes |
| HOOK-01 | Invoke `PostToolUse` and `Stop` handler scenarios | Exact Python hook input/output behavior matches expected results | No (existing tests partly cover this) |
| HOOK-02 | Verify trusted hook activation from Codex Desktop | Evidence shows configured hooks actually run for expected events, without relying only on handler unit tests | Yes / in-app session |
| FLOW-01 | Full approved spec-to-review workflow in disposable project | All required gates, artifacts, traceability, and independent review are observed and valid | Yes; multiple agent turns |
| UX-01 | `experimental` coordinator explains outcome and next action | Complies with the branch's coordinator communication preference without changing structured agent contracts | Yes; rubric-driven |

Each case needs: starting fixture revision, exact task/prompt, target branch SHA, model ID and available configuration, assertions/oracle, severity, captured evidence, outcome (`pass`, `fail`, `inconclusive`, `not run`), duration, and usage when obtainable. Passing critical safety cases requires observable support; missing evidence produces `inconclusive`, not `pass`. Quality scores are separate from critical gate results.

Proposed suite tiers:

- **Deterministic:** existing Python tests, data fixtures, static checks, zero model invocations.
- **Quick:** minimal isolated model cases for approval boundaries, reviewer detection, and one small implementation; run on demand.
- **Full:** broader case coverage, full SDD lifecycle, multiple repetitions when needed to establish reliability, and comparison against stored baselines.

Reference results are only directly comparable when the fixture, rubric, branch revision, model configuration, and execution settings are recorded; changes to these must be disclosed in the report.

### Documentation location

This backlog currently lives on `master` as its canonical location. The `experimental` branch is the *first planned implementation target*, not a separate copy of the backlog. Decide later whether to link it from the other branches or synchronize documentation; avoid independently maintained conflicting backlogs.

### Existing coverage and gap

Current tests exercise SDD transitions, invalid or contradictory review payloads, failed verification, reviewer-verdict recording, and the hooks' Python handlers. Some tests deliberately inject invalid states and predetermined `APPROVED`/`CHANGES_REQUESTED` payloads. **They do not demonstrate that a live model reviewer detects seeded bugs**. Current GitHub Actions runs Python tests and does not invoke a model.

Relevant references:

- [Integration acceptance test](../tests/test_integration_acceptance.py)
- [Review and state tests](../tests/test_workflow.py)
- [Hook and template tests](../tests/test_hooks_and_template.py)
- [Hook regression tests](../tests/test_regressions.py)
- [Current GitHub Actions workflow](../.github/workflows/tests.yml)

### Open decisions and risks

- **Codex Desktop launch:** both ordinary prompts and a reusable skill are required. Confirm the precise invocation and available trace/usage evidence before implementation; do not invent a slash command.
- **Codex CLI:** optional only; assess security/account-session concerns before proposing a separate sign-in. User prefers Desktop and wishes to avoid extra sign-ins.
- **CI boundary:** GitHub Actions can validate evaluators and uploaded/committed results, but it cannot directly drive a logged-in Desktop session on the user's computer.
- **Costs and enforcement:** benchmark usage and runtime; determine whether a hard timeout/token budget is enforceable in Desktop, or only an advisory limit; never label advisory budgets as strict.
- **Scoring:** finalize seeded defects, reproducible result oracles, the architecture/maintainability rubric, quality thresholds, and how model versus harness failures are attributed.
- **Comparisons:** finalize a baseline format and precise rules for meaningful cross-version/cross-branch comparison; old model support is not a goal.
- **Storage and cleanup:** choose secure local/artifact paths, sensitive-data redaction, explicit history-deletion workflow, and safe cleanup of passing test repositories.
- **Coverage rollout:** pilot `experimental`; settle minimal quick-suite cases and acceptance checks before rollout to other branches.
- **Approval simulation:** design a safe, pre-authorized disposable fixture for full-flow tests without weakening real human-approval gates.
- **CI integration:** choose how GitHub Actions validates evaluators or ingests exported results without controlling the user's Desktop session.

### Implementation and evidence

**Implementation:** Not started. No evaluation code, workflows, fixtures, or model-backed runs have been added by this backlog entry.

**Decision on implementation:** Still pending: no authorization to implement evaluation code was granted.

**Evidence:** No model-evaluation results yet. Once implemented, record test commands, revision, model, configuration, outcome, resource use, and links to reproducible artifacts.

## Adding another proposal

Add a distinct section with a stable ID, purpose, alternatives, agreed decisions, unresolved questions, acceptance criteria, expected cost when applicable, implementation status, and verification evidence. Distinguish proposal, approval, implementation, and verification; never infer one from another.
