"""
bids.py
=======
Build BIDS-like destination paths and **copy** labeled scans into the
output tree (never move or overwrite source files).

HOW THIS FITS IN
----------------
app.MainWindow.save_scan()
    → save_to_bids(...)
        → build_bids_paths() / build_stem()
        → shutil.copy2(source → dest)
        → write new dest JSON with SortingTool block
        → discovery.mark_saved()

Folder layout::

    <output>/<dataset>/sub-<id|unknown>/ses-<id|unknown>/
        [sub-…]_[ses-…]_acq-…_voi-…_ce-true|false[_run-N]_<suffix>.nii.gz
        …same stem….json

HOW TO EXTEND
-------------
* Change filename entity order: edit ``build_stem()``.
* Add a new entity (e.g. ``desc-``): update stem builder + ``save_to_bids``
  payload and the GUI; remember lab policy currently omits ``desc-``.
* Change collision handling: adjust the ``_run-N`` loop in ``build_bids_paths``.
* Destination sidecar ``SortingTool`` keys today::

      source, dataset, subject_id, session_id, acq, voi, ce, type
      (+ optional extra keys from the ``labels`` dict argument)
* Keep copy-only: never ``unlink`` / rewrite the source NIfTI or its JSON.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from sorting_tool.discovery import mark_saved
from sorting_tool.metadata import sidecar_for


def sanitize_entity(value: str) -> str:
    """Alphanumeric-only entity value (for sub/ses/acq/voi)."""
    text = str(value).strip()
    text = re.sub(r"^sub-", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^ses-", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[^A-Za-z0-9]+", "", text)
    return text


def sanitize_suffix(value: str) -> str:
    """Keep letters, digits, and underscores (e.g. mtoff_MTS)."""
    text = str(value).strip()
    return re.sub(r"[^A-Za-z0-9_]+", "", text)


def sanitize_optional_id(value: str) -> str:
    """Optional free-text id; empty string if blank."""
    return sanitize_entity(value)


def folder_id(value: str, default: str = "unknown") -> str:
    """Folder component: use sanitized id or default when blank."""
    cleaned = sanitize_optional_id(value)
    return cleaned if cleaned else default


def normalize_ce(value: str) -> str:
    """
    Normalize contrast-enhancement to the strings ``true`` or ``false``.

    Accepts common aliases (1/0, yes/no). Raises ``ValueError`` otherwise.
    """
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return "true"
    if text in {"false", "0", "no"}:
        return "false"
    raise ValueError(f"CE must be true or false, got: {value!r}")


def _nii_extension(source_nii: Path) -> str:
    """Preserve ``.nii.gz`` vs ``.nii`` on the destination copy."""
    name = source_nii.name.lower()
    if name.endswith(".nii.gz"):
        return ".nii.gz"
    return ".nii"


def build_stem(
    subject_id: str,
    session_id: str,
    acq: str,
    voi: str,
    ce: str,
    scan_type: str,
    run: int | None = None,
) -> str:
    """
    Build the BIDS-like filename stem (no extension).

    Pattern::

        sub-<id>_ses-<id>_acq-<acq>_voi-<voi>_ce-<true|false>[_run-N]_<suffix>

    Subject and session entities are omitted from the filename when blank
    (folders still use ``sub-unknown`` / ``ses-unknown`` via ``folder_id``).
    """
    parts: list[str] = []
    sub = sanitize_optional_id(subject_id)
    ses = sanitize_optional_id(session_id)
    if sub:
        parts.append(f"sub-{sub}")
    if ses:
        parts.append(f"ses-{ses}")
    parts.append(f"acq-{sanitize_entity(acq).lower()}")
    parts.append(f"voi-{sanitize_entity(voi).lower()}")
    parts.append(f"ce-{normalize_ce(ce)}")
    if run is not None:
        parts.append(f"run-{run}")
    suffix = sanitize_suffix(scan_type)
    if not suffix:
        raise ValueError("scan type / suffix is required")
    return "_".join(parts) + f"_{suffix}"


def dataset_root(output_dir: Path, dataset_name: str) -> Path:
    """
    Return ``<output_dir>/<dataset_name>`` (basename only for safety).

    Using ``Path(...).name`` strips any accidental directory components so
    a pasted path cannot escape the output parent.
    """
    name = Path(str(dataset_name).strip()).name
    if not name:
        raise ValueError("dataset name is required")
    return Path(output_dir).expanduser().resolve() / name


def build_bids_paths(
    output_dir: Path,
    dataset_name: str,
    subject_id: str,
    session_id: str,
    acq: str,
    voi: str,
    ce: str,
    scan_type: str,
    ext: str = ".nii.gz",
) -> tuple[Path, Path]:
    """
    Return ``(nii_dest, json_dest)`` under ``<output>/<dataset>/sub-*/ses-*/``.

    Creates the session directory if needed. If the default stem already
    exists, inserts ``_run-1``, ``_run-2``, … until a free name is found.
    """
    root = dataset_root(output_dir, dataset_name)
    if not str(scan_type).strip():
        raise ValueError("scan type is required")

    ses_dir = root / f"sub-{folder_id(subject_id)}" / f"ses-{folder_id(session_id)}"
    ses_dir.mkdir(parents=True, exist_ok=True)

    def paths(run: int | None = None) -> tuple[Path, Path]:
        stem = build_stem(subject_id, session_id, acq, voi, ce, scan_type, run=run)
        return ses_dir / f"{stem}{ext}", ses_dir / f"{stem}.json"

    nii, js = paths()
    if not nii.exists():
        return nii, js

    # Collision: keep incrementing run until both names are free.
    run = 1
    while True:
        nii, js = paths(run)
        if not nii.exists():
            return nii, js
        run += 1


def save_to_bids(
    source_nii: Path,
    output_dir: Path,
    dataset_name: str,
    subject_id: str,
    session_id: str,
    acq: str,
    voi: str,
    ce: str,
    scan_type: str,
    labels: dict | None = None,
) -> Path:
    """
    Copy NIfTI into BIDS layout; write a new sidecar at the destination.

    Never modifies the source NIfTI or its original JSON sidecar.
    Subject and session IDs are optional free-text strings.

    Returns
    -------
    Path
        Absolute path of the destination NIfTI copy.
    """
    source_nii = Path(source_nii).resolve()
    if not source_nii.is_file():
        raise FileNotFoundError(source_nii)

    # Validate required GUI labels before touching the filesystem.
    missing = []
    if not acq:
        missing.append("Acq")
    if not voi:
        missing.append("VOI")
    if ce is None or str(ce).strip() == "":
        missing.append("CE")
    if not scan_type:
        missing.append("Type")
    if missing:
        raise ValueError("Missing required labels: " + ", ".join(missing))

    ce_norm = normalize_ce(ce)

    ext = _nii_extension(source_nii)
    dest_nii, dest_json = build_bids_paths(
        output_dir,
        dataset_name,
        subject_id,
        session_id,
        acq,
        voi,
        ce_norm,
        scan_type,
        ext=ext,
    )

    # Copy only — source mtime/content stay untouched.
    shutil.copy2(source_nii, dest_nii)

    # Start from a copy of the source sidecar (if any), then add our block.
    payload: dict = {}
    src_json = sidecar_for(source_nii)
    if src_json is not None:
        with src_json.open("r") as f:
            payload = json.load(f)

    payload["SortingTool"] = {
        "source": str(source_nii),
        "dataset": Path(str(dataset_name)).name,
        "subject_id": sanitize_optional_id(subject_id) or None,
        "session_id": sanitize_optional_id(session_id) or None,
        "acq": sanitize_entity(acq).lower(),
        "voi": sanitize_entity(voi).lower(),
        "ce": ce_norm,
        "type": sanitize_suffix(scan_type),
        **(labels or {}),
    }

    with dest_json.open("w") as f:
        json.dump(payload, f, indent=2)

    # Progress is stored under the dataset root (same place the GUI checks).
    root = dataset_root(output_dir, dataset_name)
    mark_saved(root, source_nii, dest_nii)
    return dest_nii
