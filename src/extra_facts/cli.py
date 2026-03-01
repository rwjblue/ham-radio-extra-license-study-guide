from __future__ import annotations

import argparse
from pathlib import Path

from .build import build_from_source, build_from_url


def build_command(args: argparse.Namespace) -> int:
    if not args.source_url and not args.docx:
        raise SystemExit("Provide either --source-url or --docx")
    if args.source_url and args.docx:
        raise SystemExit("Provide only one of --source-url or --docx")

    if args.source_url:
        summary = build_from_url(
            source_url=args.source_url,
            out_dir=Path(args.out_dir),
            mode=args.mode,
            omit_id=args.omit_id,
            cache=Path(args.cache) if args.cache else None,
        )
    else:
        summary = build_from_source(
            source_path=Path(args.docx),
            out_dir=Path(args.out_dir),
            mode=args.mode,
            omit_id=args.omit_id,
        )

    print("Build complete")
    print(f"Questions parsed: {summary.question_count}")
    print(f"Groups: {summary.group_count}")
    print(f"Excluded items: {summary.excluded_count}")
    print(f"Text output: {summary.text_path}")
    print(f"PDF output: {summary.pdf_path}")
    return 0


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="extra-facts")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Build facts outputs from NCVEC question pool DOCX")
    build.add_argument("--source-url", help="URL for question pool DOCX")
    build.add_argument("--docx", help="Local path to question pool DOCX")
    build.add_argument("--out-dir", default="dist", help="Output directory")
    build.add_argument("--mode", choices=["literal", "tts"], default="literal")
    build.add_argument("--omit-id", action="store_true", help="Omit question IDs in output lines")
    build.add_argument("--cache", help="Download cache directory")
    build.set_defaults(func=build_command)

    return parser


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
