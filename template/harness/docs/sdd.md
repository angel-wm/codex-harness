# Specification-driven development

## States

```text
pending → spec_ready → in_progress → done
                     ↘ blocked ↗
```

An SDD feature in `pending` has no approved implementation scope. A spec author
creates `requirements.md`, `design.md`, and `tasks.md`; the coordinator validates
them and moves the feature to `spec_ready`. A human reviews and commits those
artifacts, then explicitly approves them. The control plane records their digest
and Git baseline while moving to `in_progress`.

`done` requires completed tasks, traceability, fresh successful verification,
and an independent approval for the current implementation fingerprint. Normal
commands cannot reopen a completed feature. `blocked` records the prior state,
reason, and UTC time; explicit human direction is required to resume.

## Strict English EARS

Every requirement has a stable sequential heading (`## R1`, `## R2`, …), is
verifiable, and contains exactly one uppercase `MUST` obligation in one of these
forms:

- `The system MUST ...`
- `WHEN ..., the system MUST ...`
- `WHILE ..., the system MUST ...`
- `WHERE ..., the system MUST ...`
- `IF ... THEN the system MUST ...`

Every original acceptance criterion maps to at least one requirement. Do not use
soft obligations such as “may,” “could,” or “should.”

Record mappings immediately after the requirement statement using one-based
acceptance IDs from the feature entry:

```markdown
Acceptance: A1, A3
```

## Design

`design.md` identifies files and interfaces, describes data/control flow and
error behavior, connects decisions to project architecture, and records at least
one rejected alternative. It does not silently add product behavior.

## Tasks and traceability

Every executable task is an ordered checkbox with a stable identifier and one or
more requirement references, for example:

```markdown
- [ ] T1 — Add the parser entry. Covers: R1, R2.
```

The implementer checks completed tasks and writes
`harness/progress/impl_<feature>.md` with an explicit evidence map:

```markdown
- R1 → `tests/test_cli.py::test_default_behavior`
```
