# AGENTS.md — Specification-driven development policy

This repository uses the reusable Codex SDD harness under `harness/`.

For an implementation request such as “implement the next pending feature,”
invoke `$sdd-workflow` and follow its state machine. Pure questions, inspection,
and other read-only work do not invoke the workflow automatically.

Hard rules:

- Work on one feature at a time.
- Never infer specification approval. Only an explicit human approval of the
  current `spec_ready` feature permits the `approve` transition.
- Do not implement an SDD feature before approval is recorded.
- Run configured verification and obtain an independent read-only review before
  completion.
- Preserve unrelated files and stop on an invariant failure instead of inventing
  a workaround.
- The harness never pushes, publishes, creates branches, opens pull requests, or
  changes remotes.

Use `harness/docs/` for project policy, `harness/specs/` for feature specs, and
`harness/progress/` for durable execution evidence.

## Coordinator communication

These presentation preferences apply only to the primary coordinator's
conversational replies to the user:

- Lead result reports with the outcome, failure, or decision needed; omit
  unnecessary introductions.
- When useful, briefly show completed work, remaining work, and supporting
  evidence. Do not repeat status mechanically in every interaction.
- When human input is needed, state the concrete action required. If nothing
  remains, finish without inventing another step.

Preserve essential information and uncertainty, and give detailed explanations
when requested. Use no fixed line, word, or step quotas and no artificial time
estimates. These preferences add no workflow stages and do not apply to the spec
author, implementer, reviewer, subagent JSON, EARS requirements, tasks, evidence,
progress files, or other structured formats. Existing safety, human approval,
traceability, and SDD gates take precedence.
