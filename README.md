# FCC Amateur Extra Statements of Fact Generator

Generate a clean study guide from the public NCVEC Element 4 (Amateur Extra) pool.

This project produces:
- static facts (`dist/static/static-extra_facts.txt` and `dist/static/static-extra_facts.pdf`)
- optional LLM prose facts (`dist/prose/prose-extra_facts.txt` and `dist/prose/prose-extra_facts.pdf`)
- intermediate JSON files (`dist/extra_pool.json`, `dist/extra_pool_prose.json`)

Each fact line includes the question ID and a declarative restatement of the correct answer.

## Quick Start

1. Install tooling:

```bash
mise install
mise run deps-dev
```

2. Optional: enable prose generation:

```bash
cp .env.example .env
# set OPENAI_API_KEY in .env
```

3. Build:

```bash
mise run full-build
```

4. Compare static vs prose text:

```bash
mise run compare
```

## Output Locations

- Static outputs:
  `dist/static/static-extra_facts.txt`
  `dist/static/static-extra_facts.pdf`
- Prose outputs (only when `OPENAI_API_KEY` is set):
  `dist/prose/prose-extra_facts.txt`
  `dist/prose/prose-extra_facts.pdf`
- Intermediate pool JSON:
  `dist/extra_pool.json`
  `dist/extra_pool_prose.json`

## CLI

```bash
extra-facts extract --source-url <docx-url> --out-json dist/extra_pool.json [--cache .cache]
extra-facts extract --docx <local.docx> --out-json dist/extra_pool.json
extra-facts prose --pool-json dist/extra_pool.json --out-json dist/extra_pool_prose.json [--model gpt-5-mini] [--prompt-version v1] [--workers 6] [--max-attempts 3] [--max-questions N] [--resume]
extra-facts build --pool-json dist/extra_pool.json --out-dir dist --mode literal|tts|prose [--omit-id]
```

## Notes

- Source is the NCVEC public pool DOCX release.
- Parsing is deterministic and excludes withdrawn/removed/deleted questions.
- Group order is preserved as published.

## Contributing

Development, testing, repository workflow, and release-maintainer details are in [CONTRIBUTING.md](/Users/rwjblue/src/github/rwjblue/ham-radio-extra-license-study-guide/CONTRIBUTING.md).
