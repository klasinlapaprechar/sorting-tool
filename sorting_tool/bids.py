"""Build BIDS-like destinations and save labeled scans (copy-only)."""

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
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return "true"
    if text in {"false", "0", "no"}:
        return "false"
    raise ValueError(f"CE must be true or false, got: {value!r}")


def _nii_extension(source_nii: Path) -> str:
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
    sub-<id>_ses-<id>_acq-<acq>_voi-<voi>_ce-<true|false>[_run-N]_<suffix>

    Subject and session are omitted from the filename when blank.
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
    """Return (nii_dest, json_dest) under <output>/<dataset>/sub-*/ses-*/."""
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
    """Copy NIfTI into BIDS layout; write a new sidecar at the destination.

    Never modifies the source NIfTI or its original JSON sidecar.
    Subject and session IDs are optional free-text strings.
    """
    source_nii = Path(source_nii).resolve()
    if not source_nii.is_file():
        raise FileNotFoundError(source_nii)

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

    shutil.copy2(source_nii, dest_nii)

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

    root = dataset_root(output_dir, dataset_name)
    mark_saved(root, source_nii, dest_nii)
    return dest_nii
