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
| Triggers | Run on demand when a new model becomes available or the harness changes; do not assume automatic discovery of new model releases. Treat these as **two distinct experiment types** |
| Branch coverage | Evaluate `master`, `legacy/monolithic`, and `experimental` separately; **start implementation on `experimental`**, then extend after validation |
| Comparisons | Compare against both predeclared ideal expectations and historical baselines; compare different models on the same harness revision, or harness revisions on the same current model. Keep history until intentional user deletion |
| Evaluation targets | Measure harness rule compliance and generated-code quality separately; include correctness, tests, security, architecture, and maintainability. Prefer **appropriate modular design**, accounting for branch and project constraints |
| Critical invariants | Require 100% pass on human approval, state transitions, scope boundaries, safety constraints, and established SDD gates |
| Reviewer competence | Include deliberately defective implementations (functional fault, security flaw, and requirements violation) and test whether the **actual model reviewer** identifies seeded defects; architectural/maintainability defect cases remain an option |
| Existing tests | Retain deterministic unit, integration, regression, and hook tests; add real-model evaluations instead of duplicating those tests |
| Hook coverage | Test deterministic hook handler behavior separately from whether Codex Desktop actually triggers trusted project hooks |
| Test levels | Individual/component cases for focused, lower-consumption evaluations and optional full end-to-end SDD cases |
| Languages | Start with a small Python fixture; broader language coverage only if evidence justifies it |
| Environments | Use disposable, isolated test repositories/worktrees; **remove those that pass, retain those that fail** for investigation, subject to safe cleanup checks |
| Failure handling | Stop the affected scenario on a critical failure but continue unrelated scenarios |
| Execution | Support **both** an ordinary natural-language instruction and a reusable skill launched from Codex Desktop, on demand; no paid OpenAI API dependency |
| Consumption | **Do not design token-limit enforcement or automatic stopping.** Optimize redundant work without sacrificing validity; measure usage/time when available, run quick or full suites on demand, and permit the user to monitor or interrupt manually |
| Reporting | Store readable Markdown reports and structured machine-readable evidence **within the repository folder but outside Git tracking**, available to Codex locally; preserve reports independently from temporary test repositories |
| Diagnoses | Report violated criteria, supporting evidence, suspected components, and **specific recommended changes** (without automatically generating or applying patches) |
| Acceptance | Require 100% on critical controls, correctness, security, and mandatory architectural constraints. Report **functional pass** and **quality assessment** separately, using a four-level calibrated rubric; the quality blocking threshold is still undecided |
| Change control | Explicit human approval is required before implementing fixes; track the resulting decision and independent verification |

### Confirmed design choices (second interview)

These choices were explicitly selected after the initial scope discussion:

1. **Pilot branch:** `experimental` first. The two other branches are separate later targets. Do not assume equal results merely because `master` and `legacy/monolithic` have equivalent intended control-plane behavior.
2. **Desktop entry points:** support a named reusable evaluation skill and a natural-language request; both should map to the same underlying test definitions. Exact UI invocation must be verified during implementation.
3. **History:** retain all previous evaluation reports and machine-readable evidence until explicitly deleted. Any deletion operation must be intentional and scope-limited.
4. **Code quality:** evaluate architecture and maintainability alongside functional correctness, tests, and security; subjective dimensions require transparent rubrics and must not be treated as deterministic facts.
5. **Consumption principle (superseded by fourth interview):** initial interest in limits meant conserving usage, not requiring a stopping mechanism. See the latest decision below; no bounded-mode requirement remains.
6. **Test repositories:** automatically clean up passing disposable environments; preserve failed environments and reproducible context. Never delete an unrelated or user-owned repository.
7. **Diagnosis:** suggest actionable changes to specified files/components and explain evidence; preparing or applying a code patch is outside the agreed scope.

### Third interview: confirmed choices and clarified intent

- **Pilot cases accepted:** start `experimental` with no-approval rule enforcement, seeded-defect detection by the live reviewer, small-code implementation quality, and experimental coordinator communication. Expand to SDD end-to-end tests later. Existing deterministic verification remains available.
- **Automatic code evaluation accepted:** combine executable, objective assertions with automated rubric-based assessment for maintainability and architecture. Rubric judgments are less reliable than tests; design/maintainability score thresholds and allowable variation remain **undecided**. Mandatory constraints and critical correctness/security checks may not be compensated for by a high aggregate score.
- **Report location clarified:** write output inside the working repository directory, in a proposed ignored local folder such as `.eval-results/`, so Codex Desktop can inspect it. Results should not be committed to Git by default. The exact path and `.gitignore` change are **not yet implemented**. Passing test workspaces may be deleted while their reports remain; failed workspaces stay available for inspection.
- **Comparison preference confirmed:** use **both** expectation-based pass/fail and historical reference results. Preserve comparable older results but do not optimize the harness for old models.
- **Single-source-of-truth accepted:** keep this backlog canonical on `master`, then link from other branches if appropriate during implementation rather than maintaining three independent backlogs.

#### Two evaluation questions

1. **New model adaptation:** hold the selected branch/harness commit, evaluation fixture, and rubric constant. Compare the new model with a stored run of the previously supported model (when evidence is comparable), then diagnose and improve the harness for the **new** model. Backward compatibility is optional, not an acceptance condition.
2. **Harness improvement:** hold the **latest selected model**, test fixture, and rubric constant. Compare a saved baseline of the existing harness against the modified harness; use the baseline to assess whether the change actually helps. This mode does not require testing older model versions.

Label noncomparable history honestly when the scenario, model settings, test oracle, or branch changes. For both modes, passing objective acceptance criteria takes precedence over relative performance.

#### Latest consumption decision (fourth interview)

**Confirmed:** no automated token cutoff, execution-stop controller, hard budget mode, or advisory budget gate is required. The user can monitor Codex Desktop and manually interrupt a run when desired, but is willing to run expensive or long evaluations when they materially improve the evidence. Avoid waste by making tests targeted, reusing existing deterministic checks and historical comparable results, choosing representative fixtures, and repeating only when uncertainty warrants it. **Do not reduce meaningful coverage, realism, or reviewer-detection quality just to minimize token use.** Record elapsed time and token/credit usage where the platform exposes them; do not invent usage totals. The previous bounded-execution concept is explicitly superseded.

### Fourth interview: quality, reviewer reliability, and efficiency

**Confirmed decisions:**

1. **Architecture preference:** explicitly favor modular architectures where they improve cohesion, separation of responsibilities, and maintainability. Do **not** reward needless file splitting or penalize a branch simply because its documented design is intentionally monolithic; evaluate fidelity to each branch's architectural contract and distinguish comparative design preference from a required invariant.
2. **Maintainability criteria:** start with readability, duplication, complexity, coupling, ease of modification, and test quality. Other candidates (e.g., testability, error handling, dependency hygiene, portability, observability) may be considered but are **not yet adopted as separately weighted dimensions**.
3. **Quality rating:** use four anchored levels **0 (deficient), 1 (needs improvement), 2 (good), 3 (excellent)** for applicable qualitative dimensions. Define observable examples per level and calibrate before assigning acceptance thresholds.
4. **Dual outcomes:** a solution can be *functionally correct* but have *insufficient code quality*. Report both separately so quality can be improved while preserving behavior. Whether a low score independently blocks model adoption is **still open**.
5. **Evaluation method:** combine deterministic assertions and automated rubric-based assessment by an evaluator that is not shown a preassigned expected score. Calibrate the evaluator using cases with known defects and review disagreements as uncertainty, not indisputable facts.
6. **Seeded reviewer faults:** explicitly cover a functional defect, a security flaw, and a missed requirement. Whether to add a separate architectural defect and a maintainability defect as seeded reviewer cases is **still open**.
7. **Repetition:** begin with one live-model execution per case and rerun uncertain cases or when estimating consistency. Full-suite repeat counts should be stated explicitly rather than assumed.
8. **Challenging instructions:** include ambiguous or adversarial requests that pressure the agent to bypass SDD requirements in the full suite; preserve the human approval gate.
9. **Efficiency:** keep a sensible balance between delivered correctness/quality and model consumption. Report runtime, model turns, reviewer cycles, and usage/credits where observable, compared to a comparable baseline; avoid unnecessary extra reviews or token waste, but do not compromise critical rules or quality just to obtain a low consumption figure. An efficiency regression is a separate finding, not an automatic reason to remove a correct improvement.

**Unresolved calibration:** Define precise anchors for all six maintainability categories, objective architecture constraints versus subjective preference, whether low noncritical quality blocks model acceptance, whether to add architecture/maintainability defect seeds, and how to report regressions in consumption without an arbitrary hard threshold.

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
- **Resource transparency:** record runtime, model turns, review cycles, and observable token/credit usage for comparable runs; highlight costs and inefficiency while preserving quality. Do not build automatic interruption or budget enforcement.
- **Scoring:** finalize known-defect fixtures, the six-dimension rubric and sample anchors, evaluator variance/calibration, thresholds for subjective quality, and whether quality below threshold blocks adoption. Respect branch-specific architectural intent while favoring appropriate modularity.
- **Comparisons:** finalize baseline format and exact comparable-experiment rules for (a) model upgrades at fixed harness revision and (b) harness upgrades at fixed newest model; older-model compatibility is not a goal.
- **Storage and cleanup:** finalize ignored in-repo results folder, sensitive-data redaction, intentional history deletion, cross-branch accessibility of local results, and safe cleanup of passing disposable test repositories.
- **Coverage rollout:** pilot `experimental` with the four agreed case categories, determine individual acceptance checks and full-suite promotion before rollout to other branches.
- **Approval simulation:** design a safe, pre-authorized disposable fixture for full-flow tests without weakening real human-approval gates.
- **CI integration:** choose how GitHub Actions validates evaluators or ingests exported results without controlling the user's Desktop session.

### Implementation and evidence

**Implementation:** Not started. No evaluation code, workflows, fixtures, or model-backed runs have been added by this backlog entry.

**Decision on implementation:** Still pending: no authorization to implement evaluation code was granted.

**Evidence:** No model-evaluation results yet. Once implemented, record test commands, revision, model, configuration, outcome, resource use, and links to reproducible artifacts.

## Adding another proposal

Add a distinct section with a stable ID, purpose, alternatives, agreed decisions, unresolved questions, acceptance criteria, expected cost when applicable, implementation status, and verification evidence. Distinguish proposal, approval, implementation, and verification; never infer one from another.
