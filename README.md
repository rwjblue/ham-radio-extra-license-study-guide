# FCC Amateur Extra Statements of Fact Generator

Generate a clean study guide from the public NCVEC Element 4 (Amateur Extra) pool.

This project produces:
- static facts (`dist/static/static-extra_facts.txt`, `dist/static/static-extra_facts.pdf`, and `dist/static/static-extra_facts-dark.pdf`)
- optional LLM prose facts (`dist/prose/prose-extra_facts.txt`, `dist/prose/prose-extra_facts.pdf`, and `dist/prose/prose-extra_facts-dark.pdf`)
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
# set TTS provider credentials for audio render
# TTS_PROVIDER=elevenlabs
# ELEVENLABS_API_KEY=...
```

3. Build:

```bash
mise run full-build
```

`mise run full-build` now also generates the listenable audio script, and
when the configured TTS provider key is set (`ELEVENLABS_API_KEY` by default,
or `OPENAI_API_KEY` when `TTS_PROVIDER=openai`) it renders and verifies
chapter/merged MP3 outputs.

If you want to regenerate only the audio script from the static pool:

```bash
POOL_JSON=dist/extra_pool.json MODE=tts mise run audio-script
```

Render MP3 audio from chapter text files:

```bash
mise run audio-render
```

Verify rendered MP3s, timing metadata, and chapter markers:

```bash
mise run audio-verify
```

4. Compare static vs prose text:

```bash
mise run compare
```

## Output Locations

- Static outputs:
  `dist/static/static-extra_facts.txt`
  `dist/static/static-extra_facts.pdf`
  `dist/static/static-extra_facts-dark.pdf`
- Prose outputs (only when `OPENAI_API_KEY` is set):
  `dist/prose/prose-extra_facts.txt`
  `dist/prose/prose-extra_facts.pdf`
  `dist/prose/prose-extra_facts-dark.pdf`
- Audio script output:
  `dist/audio/extra_facts_audio.txt`
  `dist/audio/chapters/chapter-01.txt` ... `chapter-10.txt`
  `dist/audio/audio_chapters_manifest.json`
  `dist/audio/chapters/chapter-01.mp3` ... `chapter-10.mp3`
  `dist/audio/extra_facts_audio.mp3`
- Intermediate pool JSON:
  `dist/extra_pool.json`
  `dist/extra_pool_prose.json`
  `dist/release/extra_pool_with_assets.tar.gz`
  `dist/release/extra_pool_prose_with_assets.tar.gz`

## GitHub Pages Site

To publish a Pages payload from the current `dist/` artifacts, run:

```bash
mise run gh-pages-site
```

This creates `docs/` with:
- `docs/amateur-extra-license-prep-pool.json`
- `docs/assets/*.png`
- `docs/amateur-extra-license-prep-script.txt`
- `docs/amateur-extra-license-prep.mp3`
- `docs/amateur-extra-license-prep-study-workbook.pdf`
- `docs/index.html`

For downloadable JSON+assets bundles, use GitHub Releases.

The repository workflow `.github/workflows/pages.yml` deploys `docs/` to GitHub Pages on pushes to `main` (when `docs/**` changes) or manual dispatch.

## CLI

```bash
extra-facts extract --source-url <docx-url> --out-json dist/extra_pool.json [--cache .cache]
extra-facts extract --docx <local.docx> --out-json dist/extra_pool.json
extra-facts prose --pool-json dist/extra_pool.json --out-json dist/extra_pool_prose.json [--model gpt-5-mini] [--prompt-version v1] [--workers 6] [--max-attempts 3] [--max-questions N] [--resume]
extra-facts build --pool-json dist/extra_pool.json --out-dir dist --mode literal|tts|prose [--omit-id]
extra-facts audio-script --pool-json dist/extra_pool_prose.json --out-dir dist/audio --mode prose [--include-id]
extra-facts audio-render --manifest dist/audio/audio_chapters_manifest.json --out-dir dist/audio [--provider elevenlabs|openai] [--model <provider-model>] [--voice <provider-voice>] [--elevenlabs-output-format mp3_44100_128] [--elevenlabs-language-code en] [--speed 1.0] [--instructions "Custom style override"] [--no-merge] [--no-chapter-markers]
extra-facts audio-verify --manifest dist/audio/audio_chapters_manifest.json [--allow-missing-merged] [--skip-chapter-marker-check]
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
- Audio render instructions are currently applied to OpenAI only; set `INSTRUCTIONS` (for `mise run audio-render`) or `--instructions` (CLI) to override OpenAI delivery style.
- `audio-render` uses `ffprobe` (duration extraction) and `ffmpeg` (MP3 merge + chapter markers).
- `audio-render` reuses existing chapter MP3 files when chapter text and render settings are unchanged.

## Contributing

Development, testing, repository workflow, and release-maintainer details are in [CONTRIBUTING.md](CONTRIBUTING.md).
