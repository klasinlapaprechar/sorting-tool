"""Build BIDS-like destinations and save labeled scans."""

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
    ce: str,
    scan_type: str,
    run: int | None = None,
) -> str:
    sub = sanitize_entity(subject_id)
    ses = sanitize_entity(session_date) or "unknown"
    voi_e = sanitize_entity(voi).lower()
    acq_e = sanitize_entity(acq).lower()
    type_e = str(scan_type).strip()
    ce_part = "_ce-true" if str(ce).lower() in {"true", "1", "yes"} else ""
    run_part = f"_run-{run}" if run is not None else ""
    return f"sub-{sub}_ses-{ses}_voi-{voi_e}_acq-{acq_e}{ce_part}{run_part}_{type_e}"


def build_bids_paths(
    output_dir: Path,
    subject_id: str,
    session_date: str,
    voi: str,
    acq: str,
    ce: str,
    scan_type: str,
    ext: str = ".nii.gz",
) -> tuple[Path, Path]:
    """Return (nii_dest, json_dest) with collision-safe run entity if needed."""
    output_dir = Path(output_dir).expanduser().resolve()
    sub = sanitize_entity(subject_id)
    ses = sanitize_entity(session_date) or "unknown"
    if not str(scan_type).strip():
        raise ValueError("scan type is required")

    ses_dir = output_dir / f"sub-{sub}" / f"ses-{ses}"
    ses_dir.mkdir(parents=True, exist_ok=True)

    def paths(run: int | None = None) -> tuple[Path, Path]:
        stem = build_stem(subject_id, session_date, voi, acq, ce, scan_type, run=run)
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
    subject_id: str,
    session_date: str,
    voi: str,
    acq: str,
    ce: str,
    scan_type: str,
    labels: dict | None = None,
) -> Path:
    """Copy NIfTI (+ sidecar) into BIDS layout using UI label values."""
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
    if ce is None or str(ce).strip() == "":
        missing.append("CE")
    if not scan_type:
        missing.append("Type")
    if missing:
        raise ValueError("Missing required labels: " + ", ".join(missing))

    ext = _nii_extension(source_nii)
    dest_nii, dest_json = build_bids_paths(
        output_dir,
        subject_id,
        session_date,
        voi,
        acq,
        ce,
        scan_type,
        ext=ext,
    )

    shutil.copy2(source_nii, dest_nii)

    src_json = sidecar_for(source_nii)
    payload: dict = {}
    if src_json is not None:
        with src_json.open() as f:
            payload = json.load(f)

    payload["SortingTool"] = {
        "source": str(source_nii),
        "subject_id": sanitize_entity(subject_id),
        "session_date": sanitize_entity(session_date) or "unknown",
        "voi": sanitize_entity(voi).lower(),
        "acq": sanitize_entity(acq).lower(),
        "ce": str(ce),
        "type": str(scan_type),
        **(labels or {}),
    }

    with dest_json.open("w") as f:
        json.dump(payload, f, indent=2)

    mark_saved(output_dir, source_nii, dest_nii)
    return dest_nii
