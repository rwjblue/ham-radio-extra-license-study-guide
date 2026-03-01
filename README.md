# FCC Amateur Extra Statements of Fact Generator

Reproducible CLI pipeline to generate a study guide from the **public NCVEC Element 4 (Amateur Extra) question pool DOCX**.

Outputs:
- `extra_pool.json` (typed intermediate question-pool representation)
- `extra_facts.txt` (UTF-8, one fact per line, blank line between groups)
- `extra_facts.pdf` (print-friendly)

Each fact line includes the question ID plus a declarative restatement of the question meaning and the correct answer.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
mise run deps-dev
# or runtime-only:
# mise run deps
```

```bash
mise run sync
```

## Usage

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

CLI summary includes parsed questions, groups, excluded withdrawn items, and output paths.

## CLI

```bash
extra-facts extract --source-url <docx-url> --out-json dist/extra_pool.json [--cache .cache]
extra-facts extract --docx <local.docx> --out-json dist/extra_pool.json
extra-facts build --pool-json dist/extra_pool.json --out-dir dist --mode literal|tts [--omit-id]
```

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
mise run build
mise run full-build
# local extract: DOCX=/path/to/pool.docx mise run extract-local
```

## Notes

- Primary extraction path is `.docx` paragraph text.
- PDF extraction support remains in the extraction module for fallback experimentation.
- Withdrawn/removed/deleted questions are excluded when detected in question/answer text.
