# AGENTS.md — Codex Harness development guide

This repository builds the reusable Codex-native SDD template in `template/`.
Treat `docs/codex-native-sdd-harness-adaptation.md` as the approved design and
keep the sibling `harness-sdd-reference` repository read-only.

## Before changing the harness

1. Inspect `git status --short --branch` and preserve unrelated work.
2. Read the adaptation plan and the files relevant to the change.
3. Keep the template generic: target applications may use any language, while
   the harness control plane uses Python 3.11+ standard library only.
4. Run `python -m unittest discover -s tests -v` before declaring success.

## Invariants

- Do not add API keys, provider credentials, model pins, or OpenAI SDK calls.
- Do not stage, commit, push, publish, create branches, or mutate remotes unless
  the user explicitly authorizes that exact action.
- Never use `git add .` or `git add --all` in harness code.
- Execute target commands as argument arrays without a shell.
- Keep approval, verification, review, and completion as independent gates.
- Keep the reviewer read-only and implementation agents sequential.
- Update canonical code in `template/`; tests must exercise that copy directly.
