from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from .build import (
    build_audio_script_from_pool_json,
    build_from_pool_json,
    extract_pool_from_source,
    extract_pool_from_url,
    generate_prose_for_pool,
)
from .prose import ProseProgressUpdate


def build_command(args: argparse.Namespace) -> int:
    if not args.pool_json:
        raise SystemExit("Provide --pool-json from the extract command")

    summary = build_from_pool_json(
        pool_json_path=Path(args.pool_json),
        out_dir=Path(args.out_dir),
        mode=args.mode,
        omit_id=args.omit_id,
    )

    print("Build complete")
    print(f"Questions parsed: {summary.question_count}")
    print(f"Groups: {summary.group_count}")
    print(f"Excluded items: {summary.excluded_count}")
    print(f"Intermediate JSON: {summary.intermediate_path}")
    print(f"Text output: {summary.text_path}")
    print(f"PDF output: {summary.pdf_path}")
    return 0




def audio_script_command(args: argparse.Namespace) -> int:
    if not args.pool_json:
        raise SystemExit("Provide --pool-json from the extract command")

    summary = build_audio_script_from_pool_json(
        pool_json_path=Path(args.pool_json),
        out_dir=Path(args.out_dir),
        mode=args.mode,
        omit_id=args.omit_id,
    )

    print("Audio script build complete")
    print(f"Questions parsed: {summary.question_count}")
    print(f"Groups: {summary.group_count}")
    print(f"Excluded items: {summary.excluded_count}")
    print(f"Intermediate JSON: {summary.intermediate_path}")
    print(f"Audio script: {summary.script_path}")
    print(f"Chapters: {summary.chapter_count}")
    print(f"Chapter texts dir: {summary.chapters_dir}")
    print(f"Chapter manifest: {summary.chapters_manifest_path}")
    return 0

def extract_command(args: argparse.Namespace) -> int:
    if not args.source_url and not args.docx:
        raise SystemExit("Provide either --source-url or --docx")
    if args.source_url and args.docx:
        raise SystemExit("Provide only one of --source-url or --docx")

    pool_json_path = Path(args.out_json)
    if args.source_url:
        summary = extract_pool_from_url(
            source_url=args.source_url,
            pool_json_path=pool_json_path,
            cache=Path(args.cache) if args.cache else None,
        )
    else:
        summary = extract_pool_from_source(
            source_path=Path(args.docx),
            pool_json_path=pool_json_path,
        )

    print("Extract complete")
    print(f"Questions parsed: {summary.question_count}")
    print(f"Groups: {summary.group_count}")
    print(f"Excluded items: {summary.excluded_count}")
    print(f"Intermediate JSON: {summary.intermediate_path}")
    return 0


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="extra-facts")
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser("extract", help="Extract question pool into intermediate JSON only")
    extract.add_argument("--source-url", help="URL for question pool DOCX")
    extract.add_argument("--docx", help="Local path to question pool DOCX")
    extract.add_argument("--out-json", default="dist/extra_pool.json", help="Output JSON path")
    extract.add_argument("--cache", help="Download cache directory")
    extract.set_defaults(func=extract_command)

    build = sub.add_parser("build", help="Build facts outputs from intermediate JSON")
    build.add_argument("--pool-json", help="Path to prebuilt intermediate question pool JSON")
    build.add_argument("--out-dir", default="dist", help="Output directory")
    build.add_argument("--mode", choices=["literal", "tts", "prose"], default="literal")
    build.add_argument("--omit-id", action="store_true", help="Omit question IDs in output lines")
    build.set_defaults(func=build_command)

    audio = sub.add_parser(
        "audio-script",
        help="Build listenable audio script text from intermediate JSON",
    )
    audio.add_argument("--pool-json", help="Path to prebuilt intermediate question pool JSON")
    audio.add_argument("--out-dir", default="dist/audio", help="Output directory")
    audio.add_argument("--mode", choices=["literal", "tts", "prose"], default="prose")
    audio.add_argument(
        "--omit-id",
        action="store_true",
        default=True,
        help="Omit question IDs in output lines (default: true)",
    )
    audio.add_argument(
        "--include-id",
        action="store_false",
        dest="omit_id",
        help="Include question IDs in output lines",
    )
    audio.set_defaults(func=audio_script_command)

    prose = sub.add_parser("prose", help="Generate LLM prose facts into enriched pool JSON")
    prose.add_argument("--pool-json", required=True, help="Input intermediate question pool JSON")
    prose.add_argument(
        "--out-json",
        default="dist/extra_pool_prose.json",
        help="Output enriched question pool JSON path",
    )
    prose.add_argument("--model", default="gpt-5-mini", help="Model name")
    prose.add_argument("--prompt-version", default="v1", help="Prompt version label")
    prose.add_argument("--workers", type=int, default=6, help="Parallel worker count")
    prose.add_argument("--max-attempts", type=int, default=3, help="Retry attempts per question")
    prose.add_argument("--max-questions", type=int, help="Limit generated questions for tuning")
    prose.add_argument("--resume", action="store_true", help="Skip already generated entries")
    prose.set_defaults(func=prose_command)

    return parser


def prose_command(args: argparse.Namespace) -> int:
    ci_mode = _is_ci()
    use_bar = not ci_mode and sys.stdout.isatty()
    non_tty_emit_interval_seconds = 5.0
    last_non_tty_emit = 0.0

    def _render_progress(update: ProseProgressUpdate) -> None:
        nonlocal last_non_tty_emit
        if update.total == 0:
            return
        if ci_mode:
            status = update.status.upper()
            print(
                (
                    f"[{update.completed}/{update.total}] "
                    f"ok={update.accepted} fb={update.fallback} err={update.errors} "
                    f"{update.question_id} {status}"
                ),
                flush=True,
            )
            return
        if not use_bar:
            now = time.monotonic()
            if (
                update.completed < update.total
                and (now - last_non_tty_emit) < non_tty_emit_interval_seconds
            ):
                return
            last_non_tty_emit = now
            status = update.status.upper()
            print(
                (
                    f"[{update.completed}/{update.total}] "
                    f"ok={update.accepted} fb={update.fallback} err={update.errors} "
                    f"{update.question_id} {status}"
                ),
                flush=True,
            )
            return
        width = 28
        ratio = update.completed / update.total
        filled = int(width * ratio)
        bar = "#" * filled + "-" * (width - filled)
        status = update.status.upper()
        print(
            (
                f"\r[{bar}] {update.completed}/{update.total} "
                f"ok={update.accepted} fb={update.fallback} err={update.errors} "
                f"{update.question_id} {status}"
            ),
            end="",
            flush=True,
        )

    summary = generate_prose_for_pool(
        pool_json_path=Path(args.pool_json),
        out_json_path=Path(args.out_json),
        model=args.model,
        prompt_version=args.prompt_version,
        workers=args.workers,
        max_attempts=args.max_attempts,
        max_questions=args.max_questions,
        resume=args.resume,
        progress_callback=_render_progress,
    )
    if summary.target > 0 and use_bar:
        print()
    print("Prose generation complete")
    print(f"Questions total: {summary.total}")
    print(f"Questions targeted: {summary.target}")
    print(f"Questions attempted: {summary.generated}")
    print(f"Accepted: {summary.accepted}")
    print(f"Fallback: {summary.fallback}")
    print(f"Errors: {summary.errors}")
    print(f"Output JSON: {Path(args.out_json)}")
    return 0


def _is_ci() -> bool:
    value = os.getenv("CI", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 1
    return func(args)


if __name__ == "__main__":
    raise SystemExit(main())
