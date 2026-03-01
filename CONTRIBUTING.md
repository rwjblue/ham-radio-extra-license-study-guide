# Contributing

This document is for contributors and maintainers of this repository.

## Prerequisites

- `mise`
- `uv`
- Python 3.11 (managed via `mise`)

Install and sync:

```bash
mise install
mise run sync
```

## Common Tasks

```bash
mise run lint
mise run typecheck
mise run test
```

Pipeline tasks:

```bash
mise run extract
mise run build
mise run prose
mise run full-build
mise run compare
```

## Architecture Notes

- Canonical source: NCVEC public Extra Class `.docx`.
- Extraction and parsing are deterministic and rule-based.
- Intermediate format is JSON (`dist/extra_pool.json`) and is the source for downstream build steps.
- Withdrawn/removed/deleted questions are excluded.
- Group ordering is preserved from source publication order.

## Release Process

There is a GitHub Actions workflow at `.github/workflows/release.yml` that publishes release artifacts.

Repository secret:
- `OPENAI_API_KEY` (optional; enables prose artifacts in release builds)

Recommended maintainer flow:

```bash
mise run release
```

`mise run release` will:
- bump version using `uv` (`patch` by default; set `BUMP=minor` or `BUMP=major`)
- create a jj commit for the version bump
- run `jj tug`
- run `jj git push --tracked`
- create and push a Git tag (`vX.Y.Z`) to trigger the release workflow

## Repo-Specific Workflow

- This repository uses jj. Prefer jj-native commands for commit/push flow.
- Ignore generated outputs and caches (`dist/`, `.cache/`, `__pycache__/`, etc.).
- See [AGENTS.md](/Users/rwjblue/src/github/rwjblue/ham-radio-extra-license-study-guide/AGENTS.md) for repository agent constraints.
