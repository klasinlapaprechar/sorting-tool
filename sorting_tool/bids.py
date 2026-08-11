"""Build BIDS-like destinations and save labeled scans (copy-only)."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from sorting_tool.discovery import mark_saved
from sorting_tool.metadata import sidecar_for


def sanitize_entity(value: str) -> str:
    text = str(value).strip()
    text = re.sub(r"^sub-", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[^A-Za-z0-9]+", "", text)
    return text


def sanitize_desc(value: str) -> str:
    text = str(value).strip()
    if not text or text.lower() == "none":
        return ""
    return re.sub(r"[^A-Za-z0-9_]+", "", text)


def sanitize_session(value: str) -> str:
    text = str(value).strip()
    if not text:
        return "unknown"
    if text.lower() == "unknown":
        return "unknown"
    digits = re.sub(r"\D", "", text)
    if len(digits) == 8:
        return digits
    return sanitize_entity(text) or "unknown"


def _nii_extension(source_nii: Path) -> str:
    name = source_nii.name.lower()
    if name.endswith(".nii.gz"):
        return ".nii.gz"
    return ".nii"


def build_stem(
    subject_id: str,
    session_date: str,
    voi: str,
    acq: str,
    desc: str,
    scan_type: str,
    run: int | None = None,
) -> str:
    sub = sanitize_entity(subject_id)
    ses = sanitize_session(session_date)
    voi_e = sanitize_entity(voi).lower()
    acq_e = sanitize_entity(acq).lower()
    type_e = sanitize_entity(scan_type).lower()
    desc_e = sanitize_desc(desc)
    desc_part = f"_desc-{desc_e}" if desc_e else ""
    run_part = f"_run-{run}" if run is not None else ""
    return f"sub-{sub}_ses-{ses}_voi-{voi_e}_acq-{acq_e}{desc_part}{run_part}_{type_e}"


def dataset_root(output_dir: Path, dataset_name: str) -> Path:
    name = Path(str(dataset_name).strip()).name
    if not name:
        raise ValueError("dataset name is required")
    return Path(output_dir).expanduser().resolve() / name


def build_bids_paths(
    output_dir: Path,
    dataset_name: str,
    subject_id: str,
    session_date: str,
    voi: str,
    acq: str,
    desc: str,
    scan_type: str,
    ext: str = ".nii.gz",
) -> tuple[Path, Path]:
    """Return (nii_dest, json_dest) under <output>/<dataset>/sub-*/ses-*/."""
    root = dataset_root(output_dir, dataset_name)
    sub = sanitize_entity(subject_id)
    ses = sanitize_session(session_date)
    if not str(scan_type).strip():
        raise ValueError("scan type is required")

    ses_dir = root / f"sub-{sub}" / f"ses-{ses}"
    ses_dir.mkdir(parents=True, exist_ok=True)

    def paths(run: int | None = None) -> tuple[Path, Path]:
        stem = build_stem(subject_id, session_date, voi, acq, desc, scan_type, run=run)
        return ses_dir / f"{stem}{ext}", ses_dir / f"{stem}.json"

    nii, js = paths()
    if not nii.exists():
        return nii, js

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
    session_date: str,
    voi: str,
    acq: str,
    desc: str,
    scan_type: str,
    labels: dict | None = None,
) -> Path:
    """Copy NIfTI into BIDS layout; write a new sidecar at the destination.

    Never modifies the source NIfTI or its original JSON sidecar.
    """
    source_nii = Path(source_nii).resolve()
    if not source_nii.is_file():
        raise FileNotFoundError(source_nii)

    missing = []
    if not sanitize_entity(subject_id):
        missing.append("Subject ID")
    if not str(session_date).strip():
        missing.append("Session date")
    if not voi:
        missing.append("VOI")
    if not acq:
        missing.append("Acq")
    if desc is None or str(desc).strip() == "":
        missing.append("Desc")
    if not scan_type:
        missing.append("Type")
    if missing:
        raise ValueError("Missing required labels: " + ", ".join(missing))

    ext = _nii_extension(source_nii)
    dest_nii, dest_json = build_bids_paths(
        output_dir,
        dataset_name,
        subject_id,
        session_date,
        voi,
        acq,
        desc,
        scan_type,
        ext=ext,
    )

    # Copy image bytes only — do not open source for writing
    shutil.copy2(source_nii, dest_nii)

    # Read original sidecar (read-only) and write a *new* JSON next to the copy
    payload: dict = {}
    src_json = sidecar_for(source_nii)
    if src_json is not None:
        with src_json.open("r") as f:
            payload = json.load(f)

    payload["SortingTool"] = {
        "source": str(source_nii),
        "dataset": Path(str(dataset_name)).name,
        "subject_id": sanitize_entity(subject_id),
        "session_date": sanitize_session(session_date),
        "voi": sanitize_entity(voi).lower(),
        "acq": sanitize_entity(acq).lower(),
        "desc": sanitize_desc(desc) or "none",
        "type": sanitize_entity(scan_type).lower(),
        **(labels or {}),
    }

    with dest_json.open("w") as f:
        json.dump(payload, f, indent=2)

    root = dataset_root(output_dir, dataset_name)
    mark_saved(root, source_nii, dest_nii)
    return dest_nii
