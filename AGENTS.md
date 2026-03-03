# AGENTS.md

## Repo Workflow Rules

- Use `mise` tasks for all developer commands; do not add or use `Makefile`.
- Prefer standalone task scripts in `mise/tasks/` over inline bash in `mise.toml`.
- Compose higher-level tasks from smaller tasks using task dependencies.
- Add `sources` and `outputs` metadata to tasks where practical so mise can skip up-to-date work.
- Preferred commands:
  - `mise run deps-dev`
  - `mise run lint`
  - `mise run typecheck`
  - `mise run test`

## Completion Gate

- Before declaring the requested work complete (i.e., before the final handoff to the user), run and pass:
  - `mise run lint`
  - `mise run typecheck`
  - `mise run test`
- Running them individually is fine.
- If any check fails, report the failure and continue working until all pass, or clearly state why completion is blocked.

## Source and Input Rules

- Canonical upstream source is the NCVEC public Extra Class `.docx` release URL.
- Keep parsing deterministic and rule-based; do not use HamStudy scraping.
- Exclude withdrawn, removed, or deleted questions cleanly.
- Preserve output grouping order by subelement/group (`E1A`, `E1B`, and so on) as published.

## VCS Rules (jj)

- Before commit/snapshot, ensure cache and build artifacts are untracked.
- If needed, run:
  - `jj file untrack 'glob:**/__pycache__/**' 'glob:**/*.py[cod]'`

## Ignore Policy

- Never commit generated artifacts or local caches:
  - `__pycache__/`, `*.py[cod]`
  - `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `.cache/`
  - `dist/`, `build/`
