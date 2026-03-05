# FCC Amateur Extra Statements of Fact Generator

Generate a clean study guide from the public NCVEC Element 4 (Amateur Extra) pool.

This project produces:
- static facts (`dist/static/facts.txt`, `dist/static/facts.pdf`, `dist/static/facts-dark.pdf`, and `dist/static/facts.epub`)
- Q & A facts (`dist/qa/qa.txt`, `dist/qa/qa.pdf`, `dist/qa/qa-dark.pdf`, and `dist/qa/qa.epub`)
- optional augmented facts (`dist/augmented/facts.txt`, `dist/augmented/facts.pdf`, `dist/augmented/facts-dark.pdf`, and `dist/augmented/facts.epub`)
- optional augmented Q & A facts (`dist/augmented/qa.txt`, `dist/augmented/qa.pdf`, `dist/augmented/qa-dark.pdf`, and `dist/augmented/qa.epub`)
- fact-based audio script (`dist/audio/fact/script.txt`)
- Q & A audio script (`dist/audio/qa/script.txt`)
- per-chapter fact audio script files (`dist/audio/fact/chapters/chapter-01.txt`, ...)
- fact audio chapter manifest (`dist/audio/fact/manifest.json`)
- optional rendered chapter audio (`dist/audio/fact/chapters/chapter-01.mp3`, ...)
- optional merged audio (`dist/audio/fact/book.mp3`)
- intermediate JSON files (`dist/pool/extra_pool.json`, `dist/pool/extra_pool_prose.json`)

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
# set TTS provider credentials for audio render
# TTS_PROVIDER=elevenlabs
# ELEVENLABS_API_KEY=...
```

3. Build:

```bash
mise run full-build
```

`mise run full-build` generates static + Q & A books, augmented books when
`OPENAI_API_KEY` is set, and both fact/Q&A audio scripts.
Audio rendering is opt-in:

```bash
mise run full-build --include-audio
```

When `--include-audio` is used, rendered/verified MP3 generation runs only if a
provider key is available (`ELEVENLABS_API_KEY` by default, or
`OPENAI_API_KEY` when `TTS_PROVIDER=openai`).

If you want to regenerate only the fact audio script from the static pool:

```bash
POOL_JSON=dist/pool/extra_pool.json MODE=tts OUT_DIR=dist/audio/fact mise run audio-script
```

Render MP3 audio from chapter text files:

```bash
mise run audio-render
```

Verify rendered MP3s, timing metadata, and chapter markers:

```bash
mise run audio-verify
```

4. Compare static vs augmented text:

```bash
mise run compare
```

## Output Locations

- Static outputs:
  `dist/static/facts.txt`
  `dist/static/facts.pdf`
  `dist/static/facts-dark.pdf`
  `dist/static/facts.epub`
- Q & A outputs:
  `dist/qa/qa.txt`
  `dist/qa/qa.pdf`
  `dist/qa/qa-dark.pdf`
  `dist/qa/qa.epub`
- Augmented outputs (only when `OPENAI_API_KEY` is set):
  `dist/augmented/facts.txt`
  `dist/augmented/facts.pdf`
  `dist/augmented/facts-dark.pdf`
  `dist/augmented/facts.epub`
  `dist/augmented/qa.txt`
  `dist/augmented/qa.pdf`
  `dist/augmented/qa-dark.pdf`
  `dist/augmented/qa.epub`
- Audio script output:
  `dist/audio/fact/script.txt`
  `dist/audio/fact/chapters/chapter-01.txt` ... `chapter-10.txt`
  `dist/audio/fact/manifest.json`
  `dist/audio/fact/chapters/chapter-01.mp3` ... `chapter-10.mp3`
  `dist/audio/fact/book.mp3`
  `dist/audio/qa/script.txt`
- Intermediate pool JSON:
  `dist/pool/extra_pool.json`
  `dist/pool/extra_pool_prose.json`
  `dist/release/extra_pool_with_assets.tar.gz`
  `dist/release/extra_pool_prose_with_assets.tar.gz`

## GitHub Pages Site

To publish a Pages payload from the current `dist/` artifacts, run:

```bash
mise run gh-pages-site
```

This creates `docs/` with:
- `docs/pool/extra_pool.json`
- `docs/pool/extra_pool_prose.json` (if available)
- `docs/pool/assets/*.png`
- `docs/static/facts.txt`, `docs/static/facts.pdf`, `docs/static/facts-dark.pdf`, `docs/static/facts.epub`
- `docs/qa/qa.txt`, `docs/qa/qa.pdf`, `docs/qa/qa-dark.pdf`, `docs/qa/qa.epub`
- `docs/augmented/{facts,qa}.{txt,pdf,*-dark.pdf,epub}` (if available)
- `docs/audio/fact/{script.txt,manifest.json,book.mp3}`
- `docs/audio/qa/{script.txt,manifest.json,book.mp3}`
- placeholder files `docs/audio/{fact,qa}/book.mp3.placeholder.txt` when merged MP3s have not been rendered yet
- root-level alias downloads using `amateur-extra-license-prep-*` filenames for cleaner saved file names in browsers
- `docs/artifacts.json` (manifest consumed by `docs/index.html`)
- `docs/artifacts.js` (inline manifest for local `file://` browsing without fetch/CORS issues)
- `docs/index.html`

For downloadable JSON+assets bundles, use GitHub Releases.

The repository workflow `.github/workflows/pages.yml` deploys `docs/` to GitHub Pages on pushes to `main` (when `docs/**` changes) or manual dispatch.

## CLI

```bash
extra-facts extract --source-url <docx-url> --out-json dist/pool/extra_pool.json [--cache .cache]
extra-facts extract --docx <local.docx> --out-json dist/pool/extra_pool.json
extra-facts prose --pool-json dist/pool/extra_pool.json --out-json dist/pool/extra_pool_prose.json [--model gpt-5] [--prompt-version v1] [--workers 6] [--max-attempts 3] [--max-questions N] [--resume]
extra-facts build --pool-json dist/pool/extra_pool.json --out-dir dist --mode literal|tts|prose|qa [--omit-id]
extra-facts audio-script --pool-json dist/pool/extra_pool_prose.json --out-dir dist/audio/fact --mode prose|qa [--include-id]
extra-facts audio-render --manifest dist/audio/fact/manifest.json --out-dir dist/audio/fact [--provider elevenlabs|openai] [--model <provider-model>] [--voice <provider-voice>] [--elevenlabs-output-format mp3_44100_128] [--elevenlabs-language-code en] [--speed 1.0] [--instructions "Custom style override"] [--no-qc-openai-transcribe] [--qc-openai-model gpt-4o-mini-transcribe] [--qc-expected-language en] [--qc-max-wer 0.35] [--qc-max-extra-tokens 2] [--qc-max-attempts 3] [--qc-llm-judge] [--qc-llm-model gpt-4.1-mini] [--no-merge] [--no-chapter-markers]
extra-facts audio-verify --manifest dist/audio/fact/manifest.json [--allow-missing-merged] [--skip-chapter-marker-check]
```

## Notes

- Source is the NCVEC public pool DOCX release.
- Parsing is deterministic and excludes withdrawn/removed/deleted questions.
- Group order is preserved as published.
- DOCX figures are exported to `assets/` next to the extracted pool JSON with question-linked names (for example `e1a04-01.png`) and linked per question via `image_paths` in the JSON.
- Release workflow publishes pool bundles (`extra_pool*_with_assets.tar.gz`) so JSON consumers can resolve `image_paths` without additional downloads.
- OpenAI prose calls use on-disk HTTP caching by default at `.cache/openai-http` (override via `OPENAI_HTTP_CACHE_DIR`, disable with `OPENAI_HTTP_CACHE=0`).
- Audio render defaults to ElevenLabs (`TTS_PROVIDER=elevenlabs`) with `TTS_MODEL=eleven_multilingual_v2` and `TTS_VOICE=JBFqnCBsd6RMkjVDRZzb`; switch to OpenAI by setting `TTS_PROVIDER=openai`.
- ElevenLabs requests include `language_code` (default `en`; override with `ELEVENLABS_LANGUAGE_CODE` or `--elevenlabs-language-code`).
- ElevenLabs audio-render calls use on-disk HTTP caching at `.cache/elevenlabs-http` (override via `ELEVENLABS_HTTP_CACHE_DIR`, disable with `ELEVENLABS_HTTP_CACHE=0`).
- OpenAI audio-render calls use the same HTTP cache controls as prose.
- Audio scripts insert a neutral `[[SHORT_PAUSE]]` marker after chapter titles and each spoken item; during `audio-render` this is converted per provider (`...` for OpenAI, `... ...` for ElevenLabs) so transitions sound distinct without depending on SSML support.
- Audio render instructions are currently applied to OpenAI only; set `INSTRUCTIONS` (for `mise run audio-render`) or `--instructions` (CLI) to override OpenAI delivery style.
- OpenAI transcription QC is enabled by default for `audio-render` and auto-retries unit renders when transcript mismatch/language drift thresholds are exceeded. Disable with `--no-qc-openai-transcribe` (or `QC_OPENAI_TRANSCRIBE=0` with `mise run audio-render`).
- Optional semantic judge: add `--qc-llm-judge` (or `QC_LLM_JUDGE=1`) to run a fast OpenAI text model against expected script vs ASR transcript for additional gibberish/artifact filtering.
- `audio-render` uses `ffprobe` (duration extraction) and `ffmpeg` (MP3 merge + chapter markers).
- `audio-render` reuses existing chapter MP3 files when chapter text and render settings are unchanged.

## Contributing

Development, testing, repository workflow, and release-maintainer details are in [CONTRIBUTING.md](CONTRIBUTING.md).
