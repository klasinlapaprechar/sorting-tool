"""
__main__.py
===========
Command-line entry point for the MRI Sorting Tool.

HOW THIS FITS IN
----------------
Invoked by::

    python -m sorting_tool
    sorting-tool          # console_script from package install

Parses ``--input`` / ``--output`` (or prompts interactively), then hands off
to ``sorting_tool.app.run_app()``, which opens the PyQt6 GUI.

Pipeline::

    __main__.main()
        → argparse / input() for paths
        → app.run_app(input_dir, output_dir)
            → discovery.discover_scans()
            → MainWindow GUI

HOW TO EXTEND
-------------
* Add a CLI flag (e.g. ``--dataset-name``): extend ``argparse`` below and
  pass the new value into ``run_app`` / ``MainWindow``.
* Support non-interactive batch mode: add a flag, skip GUI prompts, and
  call labeling logic directly (keep copy-only semantics in ``bids``).
* Change the interactive prompt wording: edit the ``input(...)`` strings.
* Do not put GUI code here — keep this module thin so it can run headless
  argument parsing before Qt is imported.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """
    Parse CLI args (or prompt for paths) and launch the GUI.

    Parameters
    ----------
    argv :
        Optional argument list for tests; defaults to ``sys.argv[1:]``.

    Returns
    -------
    int
        Process exit code (0 on normal GUI quit, 1 on missing paths / errors).
    """
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

    # Interactive path prompts when flags omitted (common for lab users).
    # strip("'\"") removes quotes people paste from Finder / Explorer.
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

    # Deferred import: avoid loading Qt/nibabel until paths are known.
    from sorting_tool.app import run_app

    return run_app(args.input, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
