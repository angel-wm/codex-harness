# Harness improvement backlog

This document tracks proposed improvements to `codex-harness`, their explicit decisions, and implementation evidence. It is separate from the [approved harness design](codex-native-sdd-harness-adaptation.md) and from the feature queue installed into target projects at `template/harness/features.json`.

An agreed design direction is **not** approval to change executable code. No item below is implemented merely because it was discussed.

## EVAL-001: Model compatibility and code-quality evaluations

**Status:** Design under discussion. Scope and principles agreed; implementation not started or verified.

### Purpose

Evaluate **the harness's behavior with the newest Codex model the user intends to keep using**: adherence to established SDD rules, generated-code correctness and quality, and implementation efficiency. Identify adaptations to the harness; **do not grade the model for adoption or recommend staying on an old model**. Preserving compatibility with older models is not a requirement.

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
| Acceptance | Require 100% on critical controls, correctness, security, and mandatory architectural constraints. Report **functional outcome** and **code-quality outcome** separately. Provisional quality target is level **2/3 per applicable dimension** after rubric calibration. A confirmed level 1 means that case's **harness + selected model result requires adaptation**, not that the model is unusable; overall aggregation remains to be defined |
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
4. **Dual outcomes:** a solution can be *functionally correct* but have *insufficient code quality*. Report both separately so quality can be improved while preserving behavior. **Model adoption is not a decision made by this evaluation**; any failed quality score calls for harness investigation/adaptation.
5. **Evaluation method:** combine deterministic assertions and automated rubric-based assessment by an evaluator that is not shown a preassigned expected score. Calibrate the evaluator using cases with known defects and review disagreements as uncertainty, not indisputable facts.
6. **Seeded reviewer faults:** explicitly cover a functional defect, a security flaw, and a missed requirement. Whether to add a separate architectural defect and a maintainability defect as seeded reviewer cases is **still open**.
7. **Repetition:** begin with one live-model execution per case and rerun uncertain cases or when estimating consistency. Full-suite repeat counts should be stated explicitly rather than assumed.
8. **Challenging instructions:** include ambiguous or adversarial requests that pressure the agent to bypass SDD requirements in the full suite; preserve the human approval gate.
9. **Efficiency:** keep a sensible balance between delivered correctness/quality and model consumption. Report runtime, model turns, reviewer cycles, and usage/credits where observable, compared to a comparable baseline; avoid unnecessary extra reviews or token waste, but do not compromise critical rules or quality just to obtain a low consumption figure. An efficiency regression is a separate finding, not an automatic reason to remove a correct improvement.

**Historical note (now superseded by later interviews):** At this point rubric anchors, architecture/maintainability defect seeds, and evaluation/consumption policies were unresolved; later interview sections contain the current decisions. The remaining scoring work concerns concrete anchors, calibrated evidence, and severity.

### Fifth interview: decisions and evaluation independence

**Confirmed by the user:**

- **Branch-specific expectations:** share cases, fixtures and deterministic criteria where semantics match (particularly modular `master` and `experimental`), but maintain independent results and add branch-specific checks as their behavior diverges. The deliberately monolithic `legacy/monolithic` branch must not fail a modularity requirement; favor appropriate modularity for modular branches without penalizing justified cohesive code.
- **Quality threshold:** provisional **level 2 on a 0–3 anchored scale for each scored dimension**. Level 2 means all material expectations are met, **not** that only two thirds of requirements have passed. Define explicitly what distinguishes level 2 from 3, and make material omissions fail their mandatory gates regardless of averaged score.
- **Quality findings:** preserve separate results for functionality and internal code quality. Functionally correct but poorly designed work is reported as such and may be improved without regressing behavior. Summary labels must describe **harness compatibility with the selected model**, not the model's suitability.
- **Reviewer defect injection:** include architectural and maintainability defects in the **full** suite in addition to known functional, security and requirement defects. Keep real model reviewer detection distinguishable from scripted verdict validation.
- **Uncertain grader output:** mark `inconclusive`, capture reasons/evidence, and selectively rerun or investigate; do not claim a definitive quality score without sufficient evidence.
- **Efficiency diagnosis:** report cost tradeoffs and recommend reverting or reworking an inefficient harness change when evidence justifies it, **never revert automatically**. Preserve human authority to accept, reject or modify recommendations.
- **Realism:** test small, medium and complex tasks across suite tiers; include deliberately ambiguous or conflicting instructions to assess robustness.
- **Conclusions (terminology to adapt):** the previously selected four outcomes were **Apt / Apt with improvements / Not apt / Inconclusive**. Reframe their subject as **the evaluated harness configuration**, never the model; proposed clearer labels are **Harness compatible / Compatible with improvements / Harness adaptation needed / Inconclusive**. Confirm exact labels and aggregation rules before implementation.

**Dimensions requested and clarification:**

The six original dimensions are readability, duplication, complexity, coupling, ease of modification, and test quality. **Four further dimensions have now been accepted for separate provisional scoring (0–3): error handling, dependency management, runtime stability/robustness, and testability.** Keep their definitions distinct and calibrate for overlap before introducing weighting or an aggregate score. `Test quality` assesses existing tests (assertions, coverage of edge cases, reliable tests); `testability` assesses how easily code can be isolated and tested, including dependency injection, controlled side effects, and ability to test failure paths. These overlap but are not identical. Clarify which receive independent 0–3 scores versus mandatory checks without proliferating redundant weighted dimensions.

`Portability` means working across supported execution environments (e.g., Windows and POSIX), **not** whether Codex can generate code in multiple programming languages. User assigns it low product priority; retain existing cross-platform harness regression checks as compatibility invariants rather than a new subjective quality dimension. Observability remains **medium priority** (diagnosable failures, logs or evidence where useful), not a high-priority new score.

**Independent assessment using only Codex subscription (proposed, pending confirmation):**

No external Claude account or paid API is required. The same latest Codex model may act as both implementer and evaluator **in separate sessions or context-isolated roles**, with the evaluator read-only, given only the implementation, approved requirements, and blind rubric, and **not** shown the original implementer's reasoning or seeded-defect answer key. This reduces contextual leakage but **does not eliminate correlated model-family bias**, even with an isolated directory. Use deterministic tests and seeded-defect oracles as the primary ground truth; assess the grader against both known-good and known-bad controls, report disagreements/inconclusive cases, and use human review only when needed. Exact Desktop session and filesystem isolation must be validated, not assumed.

**Open acceptance details:** calibrate rubric with concrete 0/1/2/3 examples for all ten dimensions, distinguish mandatory from subjective checks, specify how one low-scoring case influences the **harness-with-selected-model** summary, and determine what makes an evaluator disagreement inconclusive.

### Sixth interview: additional dimensions, grading independence and Linux evidence

**Explicitly accepted:**

- **Additional independently scored dimensions:** error handling, dependency hygiene, runtime stability/robustness, and testability, in addition to the original six. Use provisional 0–3 anchors for each; do not treat testability and *test quality* as identical, or double-penalize the same symptom. Separate mandatory defects from optional improvements. Refine the rubric with examples before relying on numeric scores.
- **Evaluator model:** use the same latest Codex model available under the user's ChatGPT subscription, in separate, read-only/context-isolated evaluation sessions with independent deterministic oracles. Another provider such as Claude is neither required nor available to this user. Isolation reduces context leakage but does not eliminate model-family bias.
- **Grade-1 classification (clarified in seventh interview):** user prefers a confirmed **1/3 in an applicable quality dimension** to flag the evaluated case **as requiring harness adaptation**, even if functionality passes. Always distinguish **functional tests: passed** from **quality: insufficient** and provide evidence. This **does not** mean the newest model should be rejected. Aggregation across cases remains pending; no automatic code changes or rollout controls are authorized.
- **Portability:** keep operating-system compatibility as a deterministic control, not a separately scored subjective dimension. The existing `experimental` CI run [38662939167](https://github.com/angel-wm/codex-harness/actions/runs/38662939167) (2026-10-15) passed on both `ubuntu-latest` and `windows-latest`, Python 3.11 and 3.13. This verifies that specific test suite on these runner configurations, **not** every Codex Desktop or runtime integration on Linux.
- **Observability:** medium-priority check where applicable; not an additional standalone grade.

**Still to define:**

- Observable anchors for 0/1/2/3 and examples of acceptable level-2 vs exceptional level-3 code across ten dimensions.
- Which failures are material enough to classify the **current harness with the chosen model** as requiring adaptation, versus a single test case only; do not treat one noisy subjective grade as decisive.
- How to verify the grading rubric against blinded known-good/known-bad fixtures and manage uncertainty or disagreement.
- Whether each quality dimension is relevant to every case; use `not applicable` with explanation, rather than forced numbers.

### Seventh interview: the model is fixed; evaluate and adapt the harness

**Important correction to earlier wording:** The newest available/selected Codex model **will be used regardless of these evaluation results**. EVAL-001 must **never** produce an overall verdict of "model not apt" or use older models as a fallback recommendation. The subject is always the **harness revision and branch running on the selected model**. When a case fails, identify a way to improve the harness, or document an external limitation with evidence if no harness-side remedy is known.

**Confirmed decisions:**

1. **Separate functional and quality outcomes:** even when the generated code passes all functional tests, inadequate architecture/maintainability warrants an explicit quality failure and an actionable harness adaptation recommendation. Preserve both signals instead of implying the model is unusable.
2. **Level 3 means justified excellence**, not more files, abstraction, tests or other complexity for its own sake.
3. **Calibrate the grader** against known-good and known-defective reference implementations before trusting subjective evaluations; reuse calibrations if the rubric and evaluation conditions have not changed.
4. **Diagnose likely origins**: record observed model behavior, harness instructions/control-plane contribution, interactions between them, or unknown cause, **only to decide what harness changes could help**. Do not overstate causal certainty and do not blame the model as a product-selection decision. A distinction such as model-behavior/harness-design/both/indeterminate is a diagnostic aid, not a suitability score.
5. **Specific recommendations:** cite affected files/components, observed failure, proposed textual or code-level adjustment, expected benefit and regression risks. No automatic patches or modifications; explicit human approval is still required.

**Report terminology (confirmed, subject to final aggregation rules):**

| Harness report outcome | Meaning |
| --- | --- |
| **Harness compatible** | Current harness revision on the selected latest model meets critical gates and the calibrated quality target |
| **Compatible with improvements** | Required gates and targets met, but non-blocking optimizations exist |
| **Harness adaptation needed** | Confirmed failure of a critical gate, functional check, or required quality target in the current harness/model pairing |
| **Inconclusive** | Insufficient evidence or unreliable/grader-disputed outcome; investigate or rerun |

A failure must describe the **current harness + selected model + exact test conditions**, not reject the model. Whether a single quality failure sets the overall harness status must be defined at the case-to-suite aggregation level. Recommendations should assess likely efficacy of harness changes without promising that every model behavioral limitation is fixable through prompts.

### Eighth interview: confirmed report labels, adaptation rechecks, known limitations, and read-only diagnosis

All four responses to the latest follow-up were accepted in conversation.

1. **Report labels confirmed:** use **Harness compatible**, **Compatible with improvements**, **Harness adaptation needed**, and **Inconclusive** (Spanish presentation may use `Compatible`, `Compatible con mejoras`, `Requiere adaptación`, `Inconcluso`). These describe the **evaluated harness configuration on the chosen latest model**, never the quality or eligibility of the model itself. The aggregation rule from case-level outcomes to suite-level labels still needs specification.
2. **Retest after adaptation:** rerun the specific failed cases and a targeted regression subset that protects the already-working harness rules. Reserve the full suite for broad changes, substantial uncertainty, or explicit user request. Record before/after evidence with the same current model.
3. **Unresolved limitations:** if the investigation finds no supported harness-side remedy, record a **known unresolved limitation**, its observed effect, attempted diagnoses, supporting evidence, and a future investigation path. Continue targeting the newest model; never claim the issue is solved or silently suppress its failing test.
4. **Evaluator permissions: strictly read-only:** the diagnostic reviewer may read existing instructions, `AGENTS.md`, skills, agent contracts, hooks, configuration, scripts, static code, test expectations, and historical reports. **It must not edit files, change Git state, apply patches, delete workspaces, alter config, or perform other repository mutations.** For strict interpretation of "read only", do not permit it to run arbitrary commands with side effects. A **separate deterministic test runner** may prepare disposable fixtures and perform execution, while a **separate reporting/coordinating component** writes Markdown/JSON to the ignored results directory; the read-only evaluator only returns its analysis as output. Verify that the actual Codex Desktop agent sandbox/permissions enforce this separation rather than merely relying on a prompt.

**Not authorized:** implementation code, automation activation, modifying branch-specific templates, or applying any recommended fixes.

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

- **Codex Desktop launch:** both ordinary prompts and a reusable skill are required. Confirm exact invocation and ability to enforce a genuinely read-only evaluator while a separate runner and reporter handle execution/output; do not invent a slash command.
- **Codex CLI:** optional only; assess security/account-session concerns before proposing a separate sign-in. User prefers Desktop and wishes to avoid extra sign-ins.
- **CI boundary:** GitHub Actions can validate evaluators and uploaded/committed results, but it cannot directly drive a logged-in Desktop session on the user's computer.
- **Resource transparency:** record runtime, model turns, review cycles, and observable token/credit usage for comparable runs; highlight costs and inefficiency while preserving quality. Do not build automatic interruption or budget enforcement.
- **Scoring:** finalize seeded fixtures and anchored 0–3 examples for ten separately visible dimensions, calibrate overlap and evaluator agreement, and establish how per-case findings map to the four confirmed **harness compatibility/adaptation** labels. The newest model is fixed, never rejected. Respect branch-specific architecture.
- **Comparisons:** finalize baseline format and exact comparable-experiment rules for (a) model upgrades at fixed harness revision and (b) harness upgrades at fixed newest model; older-model compatibility is not a goal.
- **Storage and cleanup:** finalize ignored in-repo results folder, sensitive-data redaction, intentional history deletion, cross-branch accessibility of local results, and safe cleanup of passing disposable test repositories.
- **Coverage rollout:** pilot `experimental` with four agreed quick cases; share common fixtures and oracles with modular `master`, add branch-specific tests when needed, and avoid a modularity requirement for `legacy/monolithic`. Include seeded architecture/maintainability defects in the full suite.
- **Approval simulation:** design a safe, pre-authorized disposable fixture for full-flow tests without weakening real human-approval gates.
- **CI integration:** choose how GitHub Actions validates evaluators or ingests exported results without controlling the user's Desktop session.

### Implementation and evidence

**Implementation:** Not started. No evaluation code, workflows, fixtures, or model-backed runs have been added by this backlog entry.

**Decision on implementation:** Still pending: no authorization to implement evaluation code was granted.

**Evidence:** No model-evaluation results yet. Once implemented, record test commands, revision, model, configuration, outcome, resource use, and links to reproducible artifacts.

## Adding another proposal

Add a distinct section with a stable ID, purpose, alternatives, agreed decisions, unresolved questions, acceptance criteria, expected cost when applicable, implementation status, and verification evidence. Distinguish proposal, approval, implementation, and verification; never infer one from another.
