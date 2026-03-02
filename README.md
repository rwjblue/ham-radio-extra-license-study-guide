# FCC Amateur Extra Statements of Fact Generator

Generate a clean study guide from the public NCVEC Element 4 (Amateur Extra) pool.

This project produces:
- static facts (`dist/static/static-extra_facts.txt` and `dist/static/static-extra_facts.pdf`)
- optional LLM prose facts (`dist/prose/prose-extra_facts.txt` and `dist/prose/prose-extra_facts.pdf`)
- optional listenable script (`dist/audio/extra_facts_audio.txt`)
- per-chapter audio script files (`dist/audio/chapters/chapter-01.txt`, ...)
- audio chapter manifest (`dist/audio/audio_chapters_manifest.json`)
- optional rendered chapter audio (`dist/audio/chapters/chapter-01.mp3`, ...)
- optional merged audio (`dist/audio/extra_facts_audio.mp3`)
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
# optional: tweak HTTP cache behavior for OpenAI calls
# OPENAI_HTTP_CACHE=1
# OPENAI_HTTP_CACHE_DIR=.cache/openai-http
```

3. Build:

```bash
mise run full-build
```

`mise run full-build` now also generates the listenable audio script.

If you want to regenerate only the audio script from the static pool:

```bash
POOL_JSON=dist/extra_pool.json MODE=tts mise run audio-script
```

Render MP3 audio from chapter text files:

```bash
mise run audio-render
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
- Audio script output:
  `dist/audio/extra_facts_audio.txt`
  `dist/audio/chapters/chapter-01.txt` ... `chapter-10.txt`
  `dist/audio/audio_chapters_manifest.json`
  `dist/audio/chapters/chapter-01.mp3` ... `chapter-10.mp3`
  `dist/audio/extra_facts_audio.mp3`
- Intermediate pool JSON:
  `dist/extra_pool.json`
  `dist/extra_pool_prose.json`

## CLI

```bash
extra-facts extract --source-url <docx-url> --out-json dist/extra_pool.json [--cache .cache]
extra-facts extract --docx <local.docx> --out-json dist/extra_pool.json
extra-facts prose --pool-json dist/extra_pool.json --out-json dist/extra_pool_prose.json [--model gpt-5-mini] [--prompt-version v1] [--workers 6] [--max-attempts 3] [--max-questions N] [--resume]
extra-facts build --pool-json dist/extra_pool.json --out-dir dist --mode literal|tts|prose [--omit-id]
extra-facts audio-script --pool-json dist/extra_pool_prose.json --out-dir dist/audio --mode prose [--include-id]
extra-facts audio-render --manifest dist/audio/audio_chapters_manifest.json --out-dir dist/audio [--model gpt-4o-mini-tts] [--voice alloy] [--speed 1.0] [--no-merge]
```

## Notes

- Source is the NCVEC public pool DOCX release.
- Parsing is deterministic and excludes withdrawn/removed/deleted questions.
- Group order is preserved as published.
- OpenAI prose calls use on-disk HTTP caching by default at `.cache/openai-http` (override via `OPENAI_HTTP_CACHE_DIR`, disable with `OPENAI_HTTP_CACHE=0`).
- `audio-render` uses `ffprobe` (duration extraction) and `ffmpeg` (MP3 merge).

## Contributing

Development, testing, repository workflow, and release-maintainer details are in [CONTRIBUTING.md](CONTRIBUTING.md).
