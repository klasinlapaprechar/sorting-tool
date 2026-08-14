"""
discovery.py
============
Find NIfTI scans under an input folder and track which ones have already
been saved to the BIDS output tree.

HOW THIS FITS IN
----------------
app.run_app() -> discover_scans(input_dir)
app.MainWindow.save_scan() -> bids.save_to_bids() -> mark_saved()
app.MainWindow.load_index() -> is_saved() to show "[already saved]"

HOW TO EXTEND
-------------
* Support another extension (e.g. .mgz): add it in discover_scans().
* Change where progress is stored: edit PROGRESS_NAME / progress_path().
* Progress JSON shape::

    {"saved": {"/abs/path/source.nii.gz": "/abs/path/dest.nii.gz", ...}}
"""

from __future__ import annotations

import json
from pathlib import Path

# Filename written under the dataset output folder to remember completed saves.
PROGRESS_NAME = "sorting_progress.json"


def discover_scans(input_dir: Path) -> list[Path]:
    """
    Recursively find every NIfTI file under input_dir.

    Returns
    -------
    list[Path]
        Absolute paths, sorted for stable Previous/Next order in the GUI.

    Notes
    -----
    Matches both ``*.nii`` and ``*.nii.gz``. Nested BIDS trees are fine;
    every matching file is queued for labeling.
    """
    input_dir = Path(input_dir).expanduser().resolve()
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    scans: list[Path] = []
    # rglob("*") walks the whole tree; we filter by extension below.
    for path in sorted(input_dir.rglob("*")):
        if not path.is_file():
            continue
        name = path.name.lower()
        # Check .nii.gz BEFORE .nii so compressed files are not double-counted.
        if name.endswith(".nii.gz") or name.endswith(".nii"):
            scans.append(path.resolve())
    return scans


def progress_path(output_dir: Path) -> Path:
    """Return the full path to sorting_progress.json under output_dir."""
    return Path(output_dir).expanduser().resolve() / PROGRESS_NAME


def load_progress(output_dir: Path) -> dict:
    """
    Load the progress JSON, or return an empty {"saved": {}} if missing.

    The GUI uses this to show "[already saved]" on scans that were copied
    earlier in this (or a previous) session against the same output folder.
    """
    path = progress_path(output_dir)
    if not path.is_file():
        return {"saved": {}}
    with path.open() as f:
        data = json.load(f)
    if "saved" not in data:
        data["saved"] = {}
    return data


def mark_saved(output_dir: Path, source: Path, dest: Path) -> None:
    """
    Record that ``source`` was successfully copied to ``dest``.

    Keys/values are absolute path strings so the same file is recognized
    across relative-path launches.
    """
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    data = load_progress(output_dir)
    data["saved"][str(Path(source).resolve())] = str(Path(dest).resolve())
    with progress_path(output_dir).open("w") as f:
        json.dump(data, f, indent=2)


def is_saved(output_dir: Path, source: Path) -> bool:
    """True if ``source`` already appears in sorting_progress.json."""
    data = load_progress(output_dir)
    return str(Path(source).resolve()) in data.get("saved", {})
