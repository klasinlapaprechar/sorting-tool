"""Extract subject / session / protocol metadata and label guesses."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ACQ_OPTIONS = ["Axial", "Sagittal", "Coronal"]
VOI_OPTIONS = ["cervicalspine", "thoracicspine", "lumbarspine", "pelvis"]
CE_OPTIONS = ["True", "False"]
TYPE_OPTIONS = [
    "T1w",
    "T2w",
    "T1wfatsat",
    "T2wfatsat",
    "stir",
    "flair",
    "dwi",
    "func",
    "fat",
    "water",
    "inphase",
    "outphase",
]

_SUB_RE = re.compile(r"(?:^|[/_\-])sub-([A-Za-z0-9]+)", re.IGNORECASE)
_DATE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DATE_COMPACT = re.compile(r"(?<!\d)(\d{8})(?!\d)")


@dataclass
class ScanMeta:
    path: Path
    protocol: str = ""
    series: str = ""
    subject_id: str = ""
    session_date: str = ""  # MMDDYYYY or unknown
    sidecar: dict = field(default_factory=dict)
    guess_acq: str | None = None
    guess_voi: str | None = None
    guess_ce: str | None = None
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
        # PatientName can be dict-like in some dumps
        text = text.replace("^", "").replace(" ", "")
        if text.lower().startswith("sub-"):
            text = text[4:]
        return text
    return ""


def _subject_from_path(path: Path) -> str:
    # Prefer nearest parent folder named sub-*
    for part in reversed(path.parts):
        m = re.match(r"sub-([A-Za-z0-9]+)$", part, re.IGNORECASE)
        if m:
            return m.group(1)
    m = _SUB_RE.search(str(path))
    if m:
        return m.group(1)
    return ""


def _date_to_mmddyyyy(year: str, month: str, day: str) -> str:
    return f"{month}{day}{year}"


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
            return _date_to_mmddyyyy(m.group(1), m.group(2), m.group(3))
        # DICOM YYYYMMDD
        m = re.search(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)", text)
        if m:
            return _date_to_mmddyyyy(m.group(1), m.group(2), m.group(3))
    return ""


def _session_from_path(path: Path) -> str:
    for part in path.parts:
        m = re.match(r"ses-.*?(\d{8})$", part, re.IGNORECASE)
        if m:
            # already MMDDYYYY or YYYYMMDD — keep trailing 8 digits as-is if looks MMDDYYYY
            digits = m.group(1)
            # if starts with 20/19 treat as YYYYMMDD
            if digits.startswith(("19", "20")):
                return _date_to_mmddyyyy(digits[:4], digits[4:6], digits[6:8])
            return digits
    m = _DATE_COMPACT.search(path.name)
    if m:
        digits = m.group(1)
        if digits.startswith(("19", "20")):
            return _date_to_mmddyyyy(digits[:4], digits[4:6], digits[6:8])
        return digits
    return ""


def _guess_acq(sidecar: dict, path: Path) -> str | None:
    text = " ".join(
        str(sidecar.get(k, ""))
        for k in ("ImageOrientationText", "SeriesDescription", "ProtocolName")
    ).lower()
    text += " " + path.name.lower()
    if re.search(r"\b(ax|axial)\b", text):
        return "Axial"
    if re.search(r"\b(sag|sagittal)\b", text):
        return "Sagittal"
    if re.search(r"\b(cor|coronal)\b", text):
        return "Coronal"
    return None


def _guess_voi(sidecar: dict, path: Path) -> str | None:
    text = " ".join(
        str(sidecar.get(k, ""))
        for k in ("SeriesDescription", "ProtocolName", "BodyPartExamined")
    ).lower()
    text += " " + path.name.lower()
    mapping = [
        (r"cervical|c.?spine|cspines?", "cervicalspine"),
        (r"thoracic|t.?spine|tspines?", "thoracicspine"),
        (r"lumbar|l.?spine|lspines?", "lumbarspine"),
        (r"pelvis|pelvic", "pelvis"),
    ]
    for pattern, voi in mapping:
        if re.search(pattern, text):
            return voi
    return None


def _guess_ce(sidecar: dict, path: Path) -> str | None:
    text = " ".join(
        str(sidecar.get(k, "")) for k in ("SeriesDescription", "ProtocolName")
    ).lower()
    text += " " + path.name.lower()
    if re.search(r"(\+c\b|post.?contrast|gadolinium|\bce\b)", text):
        return "True"
    if re.search(r"(pre.?contrast|\-c\b|no.?contrast)", text):
        return "False"
    return None


def _guess_type(sidecar: dict, path: Path) -> str | None:
    name = path.name
    # Prefer BIDS-like suffix in filename
    for t in TYPE_OPTIONS:
        if re.search(rf"(?:^|_){re.escape(t)}(?:\.|_)", name, re.IGNORECASE):
            return t
    text = " ".join(
        str(sidecar.get(k, "")) for k in ("SeriesDescription", "ProtocolName")
    ).lower()
    text += " " + name.lower()
    checks = [
        (r"t1w?.*fat.?sat|t1.*fs\b|t1wfatsat", "T1wfatsat"),
        (r"t2w?.*fat.?sat|t2.*fs\b|t2wfatsat", "T2wfatsat"),
        (r"\bstir\b", "stir"),
        (r"\bflair\b", "flair"),
        (r"\bdwi\b|diffusion", "dwi"),
        (r"\bfunc\b|bold|fmri", "func"),
        (r"\bin.?phase\b|inphase", "inphase"),
        (r"\bout.?phase\b|outphase|opposed", "outphase"),
        (r"\bfat\b", "fat"),
        (r"\bwater\b", "water"),
        (r"\bt1w?\b", "T1w"),
        (r"\bt2w?\b", "T2w"),
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
        guess_ce=_guess_ce(sidecar, path),
        guess_type=_guess_type(sidecar, path),
    )
