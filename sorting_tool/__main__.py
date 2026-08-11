"""CLI entry: python -m sorting_tool  |  sorting-tool"""

from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="MRI Sorting Tool — label scans and save BIDS-like outputs."
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=None,
        help="Input directory to scan recursively for NIfTI files",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output directory for BIDS-like sorted data",
    )
    args = parser.parse_args(argv)

    # Interactive path prompts when flags omitted
    if args.input is None:
        text = input("Input folder path: ").strip().strip("'\"")
        if not text:
            print("Input path required.")
            return 1
        args.input = Path(text)
    if args.output is None:
        text = input("Output folder path: ").strip().strip("'\"")
        if not text:
            print("Output path required.")
            return 1
        args.output = Path(text)

    from sorting_tool.app import run_app

    return run_app(args.input, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
