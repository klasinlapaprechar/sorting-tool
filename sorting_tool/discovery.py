"""Recursive NIfTI discovery and save progress tracking."""

from __future__ import annotations

import json
from pathlib import Path

PROGRESS_NAME = "sorting_progress.json"


def discover_scans(input_dir: Path) -> list[Path]:
    """Return sorted list of .nii / .nii.gz paths under input_dir."""
    input_dir = Path(input_dir).expanduser().resolve()
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    scans: list[Path] = []
    for path in sorted(input_dir.rglob("*")):
        if not path.is_file():
            continue
        name = path.name.lower()
        if name.endswith(".nii.gz") or name.endswith(".nii"):
            scans.append(path.resolve())
    return scans


def progress_path(output_dir: Path) -> Path:
    return Path(output_dir).expanduser().resolve() / PROGRESS_NAME


def load_progress(output_dir: Path) -> dict:
    path = progress_path(output_dir)
    if not path.is_file():
        return {"saved": {}}
    with path.open() as f:
        data = json.load(f)
    if "saved" not in data:
        data["saved"] = {}
    return data


def mark_saved(output_dir: Path, source: Path, dest: Path) -> None:
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    data = load_progress(output_dir)
    data["saved"][str(Path(source).resolve())] = str(Path(dest).resolve())
    with progress_path(output_dir).open("w") as f:
        json.dump(data, f, indent=2)


def is_saved(output_dir: Path, source: Path) -> bool:
    data = load_progress(output_dir)
    return str(Path(source).resolve()) in data.get("saved", {})
