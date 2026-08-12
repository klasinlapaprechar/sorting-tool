"""Extract subject / session / protocol metadata and label guesses."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ACQ_OPTIONS = ["axial", "sagittal", "coronal"]

VOI_OPTIONS = [
    "brain",
    "cervicalspine",
    "cervicothoracicspine",
    "thoracicspine",
    "thoracolumbarspine",
    "lumbarspine",
    "fullspine",
    "pelvis",
    "hip",
    "thigh",
    "knee",
    "leg",
    "ankle",
    "foot",
    "shoulder",
    "arm",
    "elbow",
    "forearm",
    "hand",
    "abdomen",
    "thorax",
    "liver",
    "heart",
    "head",
    "jaw",
]

CE_OPTIONS = ["true", "false"]

TYPE_OPTIONS = [
    "t1w",
    "t2w",
    "t2sfatsat",
    "t1wfatsat",
    "t2star",
    "mtoff_MTS",
    "mton_MTS",
    "t1w_MTS",
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
    session_id: str = ""  # optional free-text (often YYYYMMDD when known)
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
    if len(digits) != 8:
        return digits
    if digits.startswith(("19", "20")):
        return digits
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
        m = re.match(r"ses-([A-Za-z0-9]+)", part, re.IGNORECASE)
        if m:
            body = m.group(1)
            dig = re.search(r"(\d{8})", body)
            if dig:
                return _normalize_date_digits(dig.group(1))
            return body
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
    if re.search(r"\b(cor|coronal)\b", text):
        return "coronal"
    return None


def _guess_voi(sidecar: dict, path: Path) -> str | None:
    text = " ".join(
        str(sidecar.get(k, ""))
        for k in ("SeriesDescription", "ProtocolName", "BodyPartExamined")
    ).lower()
    text += " " + path.name.lower()
    mapping = [
        (r"cervicothoracic|c.?t.?spine", "cervicothoracicspine"),
        (r"thoracolumbar|t.?l.?spine", "thoracolumbarspine"),
        (r"full.?spine|whole.?spine|entire.?spine", "fullspine"),
        (r"cervical|c.?spine|cspines?", "cervicalspine"),
        (r"thoracic|t.?spine|tspines?", "thoracicspine"),
        (r"lumbar|l.?spine|lspines?", "lumbarspine"),
        (r"\bbrain\b|cerebral|cranial", "brain"),
        (r"pelvis|pelvic", "pelvis"),
        (r"\bhip\b", "hip"),
        (r"thigh|femur", "thigh"),
        (r"\bknee\b", "knee"),
        (r"\bleg\b|lower.?extrem", "leg"),
        (r"ankle", "ankle"),
        (r"\bfoot\b", "foot"),
        (r"shoulder", "shoulder"),
        (r"\belbow\b", "elbow"),
        (r"forearm", "forearm"),
        (r"\bhand\b|wrist", "hand"),
        (r"\barm\b|humerus", "arm"),
        (r"abdomen|abdominal", "abdomen"),
        (r"\bthorax\b|chest", "thorax"),
        (r"\bliver\b", "liver"),
        (r"\bheart\b|cardiac", "heart"),
        (r"\bjaw\b|mandible|tmj", "jaw"),
        (r"\bhead\b", "head"),
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
    if re.search(r"(\+c\b|post.?contrast|gadolinium|post.?gad|\bce\b)", text):
        return "true"
    if re.search(r"(pre.?contrast|\-c\b|no.?contrast|pre.?gad)", text):
        return "false"
    return None


def _guess_type(sidecar: dict, path: Path) -> str | None:
    name = path.name
    ordered = sorted(TYPE_OPTIONS, key=len, reverse=True)
    for t in ordered:
        if re.search(rf"(?:^|_){re.escape(t)}(?:\.|_)", name, re.IGNORECASE):
            return t
    if re.search(r"(?:^|_)T2w(?:\.|_)", name):
        return "t2w"
    if re.search(r"(?:^|_)T1w(?:\.|_)", name):
        return "t1w"
    if re.search(r"(?:^|_)T2star(?:\.|_)", name, re.IGNORECASE):
        return "t2star"

    text = " ".join(
        str(sidecar.get(k, "")) for k in ("SeriesDescription", "ProtocolName")
    ).lower()
    text += " " + name.lower()
    checks = [
        (r"mtoff|mt.?off", "mtoff_MTS"),
        (r"mton|mt.?on", "mton_MTS"),
        (r"t1w?.?mts|mts.*t1", "t1w_MTS"),
        (r"t2.?sfatsat|t2w?.*fat.?sat|t2.*\bfs\b", "t2sfatsat"),
        (r"t1.?wfatsat|t1w?.*fat.?sat|t1.*\bfs\b", "t1wfatsat"),
        (r"t2\*|t2star|t2.?star", "t2star"),
        (r"\bstir\b", "stir"),
        (r"\bflair\b", "flair"),
        (r"\bdwi\b|diffusion", "dwi"),
        (r"\bfunc\b|bold|fmri", "func"),
        (r"\bin.?phase\b|inphase", "inphase"),
        (r"\bout.?phase\b|outphase|opposed", "outphase"),
        (r"\bfat\b", "fat"),
        (r"\bwater\b", "water"),
        (r"\bt2w?\b", "t2w"),
        (r"\bt1w?\b", "t1w"),
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
        session_id=session,
        sidecar=sidecar,
        guess_acq=_guess_acq(sidecar, path),
        guess_voi=_guess_voi(sidecar, path),
        guess_ce=_guess_ce(sidecar, path),
        guess_type=_guess_type(sidecar, path),
    )
