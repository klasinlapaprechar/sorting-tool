"""Main PyQt6 window for MRI sorting / BIDS labeling."""

from __future__ import annotations

from pathlib import Path

import nibabel as nib
import numpy as np
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from sorting_tool.bids import save_to_bids
from sorting_tool.discovery import discover_scans, is_saved
from sorting_tool.metadata import (
    ACQ_OPTIONS,
    CE_OPTIONS,
    TYPE_OPTIONS,
    VOI_OPTIONS,
    ScanMeta,
    extract_meta,
)
from sorting_tool.viewer import OrthoViewer


class RadioRow(QWidget):
    """Single-select group styled as a row of options."""

    def __init__(self, title: str, options: list[str], columns: int = 4, parent=None):
        super().__init__(parent)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(f"<b>{title}</b>"))
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        for i, opt in enumerate(options):
            btn = QRadioButton(opt)
            self.group.addButton(btn, i)
            grid.addWidget(btn, i // columns, i % columns)
        layout.addWidget(grid_host, stretch=1)
        self._options = options

    def selected(self) -> str | None:
        btn = self.group.checkedButton()
        return btn.text() if btn else None

    def set_selected(self, value: str | None) -> None:
        self.group.setExclusive(False)
        for btn in self.group.buttons():
            btn.setChecked(False)
        self.group.setExclusive(True)
        if value is None:
            return
        for btn in self.group.buttons():
            if btn.text().lower() == str(value).lower():
                btn.setChecked(True)
                return


class MainWindow(QMainWindow):
    def __init__(self, input_dir: Path, output_dir: Path, scans: list[Path]):
        super().__init__()
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.scans = scans
        self.index = 0
        self.current_meta: ScanMeta | None = None

        self.setWindowTitle("MRI Sorting Tool")
        self.resize(1200, 900)

        self.viewer = OrthoViewer()

        self.protocol_label = QLabel("Protocol Description: —")
        self.series_label = QLabel("Series Description: —")
        self.subject_edit = QLineEdit()
        self.subject_edit.setPlaceholderText("Subject ID")
        self.session_edit = QLineEdit()
        self.session_edit.setPlaceholderText("Session date MMDDYYYY or unknown")

        self.acq_row = RadioRow("Acq", ACQ_OPTIONS, columns=3)
        self.voi_row = RadioRow("VOI", VOI_OPTIONS, columns=2)
        self.ce_row = RadioRow("CE", CE_OPTIONS, columns=2)
        self.type_row = RadioRow("Type", TYPE_OPTIONS, columns=4)

        self.status_label = QLabel("")
        self.prev_btn = QPushButton("Previous Image Button")
        self.next_btn = QPushButton("Next Image Button")
        self.save_btn = QPushButton("Save Image to BIDS")
        for btn in (self.prev_btn, self.next_btn, self.save_btn):
            btn.setMinimumHeight(40)
            btn.setStyleSheet(
                "background-color: #2b6cb0; color: white; font-weight: bold;"
            )

        self.prev_btn.clicked.connect(self.prev_scan)
        self.next_btn.clicked.connect(self.next_scan)
        self.save_btn.clicked.connect(self.save_scan)

        meta_box = QGroupBox("Metadata / Labels")
        meta_layout = QVBoxLayout(meta_box)
        meta_layout.addWidget(self.protocol_label)
        meta_layout.addWidget(self.series_label)
        sub_row = QHBoxLayout()
        sub_row.addWidget(QLabel("Subject ID:"))
        sub_row.addWidget(self.subject_edit)
        meta_layout.addLayout(sub_row)
        ses_row = QHBoxLayout()
        ses_row.addWidget(QLabel("Session date:"))
        ses_row.addWidget(self.session_edit)
        meta_layout.addLayout(ses_row)
        meta_layout.addWidget(self.acq_row)
        meta_layout.addWidget(self.voi_row)
        meta_layout.addWidget(self.ce_row)
        meta_layout.addWidget(self.type_row)
        meta_layout.addStretch(1)
        meta_layout.addWidget(self.status_label)
        meta_layout.addWidget(self.prev_btn)
        meta_layout.addWidget(self.next_btn)
        meta_layout.addWidget(self.save_btn)

        central = QWidget()
        root = QHBoxLayout(central)
        root.addWidget(self.viewer, stretch=3)
        root.addWidget(meta_box, stretch=2)
        self.setCentralWidget(central)

        if self.scans:
            self.load_index(0)
        else:
            self.status_label.setText("No NIfTI scans found.")

    def load_index(self, idx: int) -> None:
        if not self.scans:
            return
        self.index = max(0, min(idx, len(self.scans) - 1))
        path = self.scans[self.index]
        try:
            img = nib.load(str(path))
            data = np.asarray(img.get_fdata(dtype=np.float32))
            zooms = tuple(float(z) for z in img.header.get_zooms()[:3])
        except Exception as exc:  # noqa: BLE001
            self.viewer.clear()
            QMessageBox.critical(self, "Load error", f"Failed to load {path}:\n{exc}")
            return

        try:
            self.viewer.set_volume(data, zooms=zooms)
        except Exception as exc:  # noqa: BLE001
            self.viewer.clear()
            QMessageBox.warning(self, "Display error", str(exc))

        meta = extract_meta(path)
        self.current_meta = meta
        self.protocol_label.setText(f"Protocol Description: {meta.protocol or '—'}")
        self.series_label.setText(f"Series Description: {meta.series or '—'}")
        self.subject_edit.setText(meta.subject_id)
        self.session_edit.setText(meta.session_date or "unknown")
        self.acq_row.set_selected(meta.guess_acq)
        self.voi_row.set_selected(meta.guess_voi)
        self.ce_row.set_selected(meta.guess_ce or "False")
        self.type_row.set_selected(meta.guess_type)

        saved = " [already saved]" if is_saved(self.output_dir, path) else ""
        self.status_label.setText(
            f"Scan {self.index + 1} / {len(self.scans)}{saved}\n{path.name}"
        )
        self.setWindowTitle(f"MRI Sorting Tool — {path.name}")

    def prev_scan(self) -> None:
        if self.index > 0:
            self.load_index(self.index - 1)

    def next_scan(self) -> None:
        if self.index < len(self.scans) - 1:
            self.load_index(self.index + 1)

    def save_scan(self) -> None:
        if self.current_meta is None:
            return
        acq = self.acq_row.selected()
        voi = self.voi_row.selected()
        ce = self.ce_row.selected()
        typ = self.type_row.selected()
        subject = self.subject_edit.text().strip()
        session = self.session_edit.text().strip()

        try:
            dest = save_to_bids(
                source_nii=self.current_meta.path,
                output_dir=self.output_dir,
                subject_id=subject,
                session_date=session,
                voi=voi or "",
                acq=acq or "",
                ce=ce or "",
                scan_type=typ or "",
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot save", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", str(exc))
            return

        QMessageBox.information(self, "Saved", f"Wrote:\n{dest}")
        # Advance to next unscanned if possible
        for j in range(self.index + 1, len(self.scans)):
            if not is_saved(self.output_dir, self.scans[j]):
                self.load_index(j)
                return
        self.load_index(self.index)


def prompt_directories() -> tuple[Path, Path] | None:
    app = QApplication.instance() or QApplication([])
    in_dir = QFileDialog.getExistingDirectory(None, "Select INPUT folder (scans)")
    if not in_dir:
        return None
    out_dir = QFileDialog.getExistingDirectory(None, "Select OUTPUT folder (BIDS)")
    if not out_dir:
        return None
    return Path(in_dir), Path(out_dir)


def run_app(input_dir: Path | None = None, output_dir: Path | None = None) -> int:
    import sys

    app = QApplication.instance() or QApplication(sys.argv)

    if input_dir is None or output_dir is None:
        dirs = prompt_directories()
        if dirs is None:
            return 1
        input_dir, output_dir = dirs

    input_dir = Path(input_dir).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        scans = discover_scans(input_dir)
    except FileNotFoundError as exc:
        QMessageBox.critical(None, "Input error", str(exc))
        return 1

    if not scans:
        QMessageBox.warning(None, "No scans", f"No .nii/.nii.gz files under:\n{input_dir}")
        return 1

    win = MainWindow(input_dir, output_dir, scans)
    win.show()
    return app.exec()
