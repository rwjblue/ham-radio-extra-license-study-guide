# FCC Amateur Extra Statements of Fact Generator

Reproducible CLI pipeline to generate a study guide from the **public NCVEC Element 4 (Amateur Extra) question pool DOCX**.

Outputs:
- `extra_pool.json` (typed intermediate question-pool representation)
- `extra_pool_prose.json` (optional LLM-enriched pool with prose facts + validation metadata)
- `dist/static/extra_facts.txt` + `dist/static/extra_facts.pdf` (always generated)
- `dist/prose/extra_facts.txt` + `dist/prose/extra_facts.pdf` (generated when `OPENAI_API_KEY` is set)

Each fact line includes the question ID plus a declarative restatement of the question meaning and the correct answer.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
# one-time local env setup for prose generation
cp .env.example .env
# then set OPENAI_API_KEY in .env

mise run deps-dev
# or runtime-only:
# mise run deps
```

```bash
mise run sync
```

## Usage

Recommended one-shot pipeline (static always, prose if API key exists):

```bash
mise run full-build
```

This writes static outputs to `dist/static/`.
If `OPENAI_API_KEY` is present, it also writes prose outputs to `dist/prose/`.

Quick text comparison:

```bash
mise run compare
```

Manual flow:

Step 1: extract source into intermediate JSON (no fact generation):

```bash
mise run -- uv run extra-facts extract \
  --source-url "https://ncvec.org/downloads/2024-2028%20Extra%20Class%20Question%20Pool%20and%20Syllabus%20Public%20Release%20with%204th%20Errata%20Feb%204%202026.docx" \
  --out-json dist/extra_pool.json \
  --cache .cache
```

Step 2: build facts from intermediate JSON:

```bash
mise run -- uv run extra-facts build \
  --pool-json dist/extra_pool.json \
  --out-dir dist \
  --mode literal
```

Extract from local DOCX:

```bash
mise run -- uv run extra-facts extract \
  --docx /path/to/ncvec-extra-question-pool.docx \
  --out-json dist/extra_pool.json
```

TTS mode without question IDs:

```bash
mise run -- uv run extra-facts build \
  --pool-json dist/extra_pool.json \
  --out-dir dist \
  --mode tts \
  --omit-id
```

Optional Step 3: generate LLM prose facts (requires `OPENAI_API_KEY`):

```bash
mise run -- uv run extra-facts prose \
  --pool-json dist/extra_pool.json \
  --out-json dist/extra_pool_prose.json \
  --model gpt-5-mini \
  --prompt-version v1 \
  --max-attempts 3
```

The prose command prints per-question progress with running acceptance,
fallback, and error counts.

Build using prose mode:

```bash
mise run -- uv run extra-facts build \
  --pool-json dist/extra_pool_prose.json \
  --out-dir dist \
  --mode prose
```

CLI summary includes parsed questions, groups, excluded withdrawn items, and output paths.

## CLI

```bash
extra-facts extract --source-url <docx-url> --out-json dist/extra_pool.json [--cache .cache]
extra-facts extract --docx <local.docx> --out-json dist/extra_pool.json
extra-facts prose --pool-json dist/extra_pool.json --out-json dist/extra_pool_prose.json [--model gpt-5-mini] [--prompt-version v1] [--workers 6] [--max-attempts 3] [--max-questions N] [--resume]
extra-facts build --pool-json dist/extra_pool.json --out-dir dist --mode literal|tts|prose [--omit-id]
```

`prose` uses parallel API requests with `--workers` (default: `6`) and can retry failed validations per question with `--max-attempts` (default: `3`).

## Determinism

- Parsing is rule-based and deterministic.
- Group ordering is preserved from source order (`E1A`, `E1B`, etc.).
- No remote scraping beyond an explicit NCVEC source URL.

## Development Commands

```bash
mise run sync
mise run deps
mise run deps-dev
mise run lock
mise run lint
mise run typecheck
mise run test
mise run extract
mise run prose
mise run build
mise run full-build
mise run full-prose-build
mise run compare
# local extract: DOCX=/path/to/pool.docx mise run extract-local
```

## Notes

- Primary extraction path is `.docx` paragraph text.
- Prose generation is optional and includes automatic validation with deterministic fallback.
- PDF extraction support remains in the extraction module for fallback experimentation.
- Withdrawn/removed/deleted questions are excluded when detected in question/answer text.
