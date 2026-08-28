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
