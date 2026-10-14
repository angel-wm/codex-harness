# Experimental variant

`experimental` starts from modular `master` at
`7c0f2978bd4248ee4a8754421a9f4a9c46d14887`, including its stable-corrections
documentation commit. It keeps the modular architecture and existing SDD gates.
`master` and `legacy/monolithic` remain independent stable variants; the historical
tags are unchanged.

## Purpose and source

The experiment makes the primary coordinator's replies easier to act on through
a small presentation preference in `template/AGENTS.md`. That file is already the
durable policy copied into target repositories; the root development `AGENTS.md`
and the SDD orchestration skill need no duplicate instructions. Copying this
branch's template carries the preference into a target project. Existing
installations are not changed automatically.

The inspiration is [I Have ADHD](https://github.com/ayghri/i-have-adhd), reviewed
on 2026-10-14 at commit `1ecea1993b7fce257ffbd686c070948b5e07eda6`:
its [README](https://github.com/ayghri/i-have-adhd/blob/1ecea1993b7fce257ffbd686c070948b5e07eda6/README.md)
and [original skill](https://github.com/ayghri/i-have-adhd/blob/1ecea1993b7fce257ffbd686c070948b5e07eda6/skills/i-have-adhd/SKILL.md).
Only general communication principles are adapted in original wording. The
upstream repository and skill are not installed or copied.

## Adopted and excluded behavior

The authoritative instructions are the single `Coordinator communication`
section in `template/AGENTS.md`. They favor outcome-first result reports, useful
visibility of progress and evidence, and a concrete next action when human input
is needed. They preserve essential detail and uncertainty, including full
explanations on request. Finished work needs no invented follow-up.

The adaptation does not import the upstream assumptions about the reader having
ADHD, session mode activation/deactivation, mandatory numbering, a five-item list
cap, status restatement every turn, time estimates, an obligatory final action,
or blanket bans on introductions and recaps. It adds no rigid line, word, or step
limits, planning tool requirement, diagnostic procedure, or new approval rule.
RTK and Matt Pocock's methodologies are not integrated in this variant.

## Exact differences from the base

| File | Change |
|---|---|
| `template/AGENTS.md` | One section scoped to the primary coordinator's conversational replies to the user. |
| `README.md` | Identifies this branch and links to this document. |
| `docs/experimental.md` | Records the source, scope, exclusions, validation boundary, and reversal. |

The communication preference does not govern the spec author, implementer,
reviewer, or their JSON contracts. It does not change EARS requirements, tasks,
evidence, progress files, or other structured formats. Safety, explicit human
approval, traceability, verification, independent review, and completion retain
their existing authority. No hook, validator, state machine, agent definition,
configuration, dependency, or SDD workflow stage is added or changed. Its only
behavioral effect is how the coordinator presents conversational information.

## Validation and reversal

Use the existing `python -m unittest discover -s tests -v` suite for regression
and configuration checks. Review the diff from the base above to confirm that
only the three listed files differ and that the new instructions exclude agent
contracts and structured artifacts. These checks do not measure conversational
quality or guarantee that every future response follows the preference.

To remove just the behavior in this source template or an installed target,
delete the `Coordinator communication` section from the relevant `AGENTS.md`.
To undo the whole isolated adaptation commit, use `git revert <adaptation-commit>`
after inspecting a clean worktree and checking for later overlapping edits.
That commit contains only the three changes listed above; reverting it preserves
the base's stable corrections and all SDD controls. No uninstall or data migration
is required.
