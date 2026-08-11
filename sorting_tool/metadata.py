"""Extract subject / session / protocol metadata and label guesses."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ACQ_OPTIONS = ["axial", "sagittal"]
VOI_OPTIONS = ["cervical", "lumbar", "brain", "thoracic"]
DESC_OPTIONS = ["none", "fatSat_Pre_gad", "fatSat_Post_gad"]
TYPE_OPTIONS = ["t2w", "t2star", "t1"]

_SUB_RE = re.compile(r"(?:^|[/_\-])sub-([A-Za-z0-9]+)", re.IGNORECASE)
_DATE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DATE_COMPACT = re.compile(r"(?<!\d)(\d{8})(?!\d)")


@dataclass
class ScanMeta:
    path: Path
    protocol: str = ""
    series: str = ""
    subject_id: str = ""
    session_date: str = ""  # YYYYMMDD or unknown
    sidecar: dict = field(default_factory=dict)
    guess_acq: str | None = None
    guess_voi: str | None = None
    guess_desc: str | None = None
    guess_type: str | None = None


def sidecar_for(nifti_path: Path) -> Path | None:
    nifti_path = Path(nifti_path)
    name = nifti_path.name
    if name.endswith(".nii.gz"):
        stem = name[: -len(".nii.gz")]
    elif name.endswith(".nii"):
        stem = name[: -len(".nii")]
    else:
        stem = nifti_path.stem
    candidate = nifti_path.with_name(stem + ".json")
    return candidate if candidate.is_file() else None


def load_sidecar(nifti_path: Path) -> dict:
    path = sidecar_for(nifti_path)
    if path is None:
        return {}
    with path.open() as f:
        return json.load(f)


def _subject_from_sidecar(sidecar: dict) -> str:
    for key in ("PatientID", "PatientName", "Subject", "subject_id"):
        val = sidecar.get(key)
        if val is None:
            continue
        text = str(val).strip()
        if not text:
            continue
        text = text.replace("^", "").replace(" ", "")
        if text.lower().startswith("sub-"):
            text = text[4:]
        return text
    return ""


def _subject_from_path(path: Path) -> str:
    for part in reversed(path.parts):
        m = re.match(r"sub-([A-Za-z0-9]+)$", part, re.IGNORECASE)
        if m:
            return m.group(1)
    m = _SUB_RE.search(str(path))
    if m:
        return m.group(1)
    return ""


def _date_to_yyyymmdd(year: str, month: str, day: str) -> str:
    return f"{year}{month}{day}"


def _normalize_date_digits(digits: str) -> str:
    """Return YYYYMMDD when possible."""
    if len(digits) != 8:
        return digits
    if digits.startswith(("19", "20")):
        return digits  # already YYYYMMDD
    # treat as MMDDYYYY
    return _date_to_yyyymmdd(digits[4:8], digits[0:2], digits[2:4])


def _session_from_sidecar(sidecar: dict) -> str:
    for key in (
        "AcquisitionDateTime",
        "AcquisitionDate",
        "SeriesDate",
        "StudyDate",
    ):
        val = sidecar.get(key)
        if not val:
            continue
        text = str(val)
        m = _DATE_ISO.search(text)
        if m:
            return _date_to_yyyymmdd(m.group(1), m.group(2), m.group(3))
        m = re.search(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)", text)
        if m:
            return _date_to_yyyymmdd(m.group(1), m.group(2), m.group(3))
    return ""


def _session_from_path(path: Path) -> str:
    for part in path.parts:
        m = re.match(r"ses-.*?(\d{8})", part, re.IGNORECASE)
        if m:
            return _normalize_date_digits(m.group(1))
    m = _DATE_COMPACT.search(path.name)
    if m:
        return _normalize_date_digits(m.group(1))
    return ""


def _guess_acq(sidecar: dict, path: Path) -> str | None:
    text = " ".join(
        str(sidecar.get(k, ""))
        for k in ("ImageOrientationText", "SeriesDescription", "ProtocolName")
    ).lower()
    text += " " + path.name.lower()
    if re.search(r"\b(ax|axial)\b", text):
        return "axial"
    if re.search(r"\b(sag|sagittal)\b", text):
        return "sagittal"
    return None


def _guess_voi(sidecar: dict, path: Path) -> str | None:
    text = " ".join(
        str(sidecar.get(k, ""))
        for k in ("SeriesDescription", "ProtocolName", "BodyPartExamined")
    ).lower()
    text += " " + path.name.lower()
    mapping = [
        (r"cervical|c.?spine|cspines?", "cervical"),
        (r"thoracic|t.?spine|tspines?", "thoracic"),
        (r"lumbar|l.?spine|lspines?", "lumbar"),
        (r"\bbrain\b|cerebral|cranial", "brain"),
    ]
    for pattern, voi in mapping:
        if re.search(pattern, text):
            return voi
    return None


def _guess_desc(sidecar: dict, path: Path) -> str | None:
    text = " ".join(
        str(sidecar.get(k, "")) for k in ("SeriesDescription", "ProtocolName")
    ).lower()
    text += " " + path.name.lower()
    fatsat = bool(re.search(r"fat.?sat|\bfs\b", text))
    post = bool(re.search(r"(\+c\b|post.?contrast|post.?gad|\bgad\b)", text))
    pre = bool(re.search(r"(pre.?contrast|\-c\b|pre.?gad)", text))
    if fatsat and post:
        return "fatSat_Post_gad"
    if fatsat and pre:
        return "fatSat_Pre_gad"
    if fatsat:
        return "fatSat_Pre_gad"
    return "none"


def _guess_type(sidecar: dict, path: Path) -> str | None:
    name = path.name
    for t in TYPE_OPTIONS:
        if re.search(rf"(?:^|_){re.escape(t)}(?:\.|_)", name, re.IGNORECASE):
            return t
    # common BIDS uppercase
    if re.search(r"(?:^|_)T2w(?:\.|_)", name):
        return "t2w"
    if re.search(r"(?:^|_)T1w(?:\.|_)", name):
        return "t1"
    if re.search(r"(?:^|_)T2star(?:\.|_)", name, re.IGNORECASE):
        return "t2star"

    text = " ".join(
        str(sidecar.get(k, "")) for k in ("SeriesDescription", "ProtocolName")
    ).lower()
    text += " " + name.lower()
    checks = [
        (r"t2\*|t2star|t2.?star|gre.*t2", "t2star"),
        (r"\bt2w?\b", "t2w"),
        (r"\bt1w?\b", "t1"),
    ]
    for pattern, typ in checks:
        if re.search(pattern, text):
            return typ
    return None


def extract_meta(nifti_path: Path) -> ScanMeta:
    path = Path(nifti_path).resolve()
    sidecar = load_sidecar(path)
    subject = _subject_from_sidecar(sidecar) or _subject_from_path(path)
    session = _session_from_sidecar(sidecar) or _session_from_path(path)
    return ScanMeta(
        path=path,
        protocol=str(sidecar.get("ProtocolName") or sidecar.get("Protocol") or ""),
        series=str(sidecar.get("SeriesDescription") or ""),
        subject_id=subject,
        session_date=session,
        sidecar=sidecar,
        guess_acq=_guess_acq(sidecar, path),
        guess_voi=_guess_voi(sidecar, path),
        guess_desc=_guess_desc(sidecar, path),
        guess_type=_guess_type(sidecar, path),
    )
