"""Orthogonal MRI viewports with slice and brightness sliders."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class PlaneView(QWidget):
    """One plane: image, horizontal slice slider, vertical brightness slider."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self._volume: np.ndarray | None = None
        self._axis = 0  # which volume axis to slice
        self._slice_count = 1

        self.image_label = QLabel(title)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(280, 200)
        self.image_label.setStyleSheet(
            "background-color: #1a3a6b; color: white; border: 1px solid #0d213f;"
        )
        self.image_label.setScaledContents(False)

        self.slice_slider = QSlider(Qt.Orientation.Horizontal)
        self.slice_slider.setMinimum(0)
        self.slice_slider.setMaximum(0)
        self.slice_slider.valueChanged.connect(self._refresh)

        self.brightness_slider = QSlider(Qt.Orientation.Vertical)
        self.brightness_slider.setMinimum(1)
        self.brightness_slider.setMaximum(100)
        self.brightness_slider.setValue(50)
        self.brightness_slider.valueChanged.connect(self._refresh)

        right = QVBoxLayout()
        right.addWidget(QLabel("B"))
        right.addWidget(self.brightness_slider, stretch=1)

        mid = QHBoxLayout()
        mid.addWidget(self.image_label, stretch=1)
        mid.addLayout(right)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(QLabel(title))
        layout.addLayout(mid, stretch=1)
        layout.addWidget(self.slice_slider)

    def set_volume(self, volume: np.ndarray, axis: int) -> None:
        self._volume = np.asarray(volume)
        self._axis = axis
        self._slice_count = max(int(self._volume.shape[axis]), 1)
        self.slice_slider.blockSignals(True)
        self.slice_slider.setMaximum(self._slice_count - 1)
        self.slice_slider.setValue(self._slice_count // 2)
        self.slice_slider.blockSignals(False)
        self._refresh()

    def clear(self) -> None:
        self._volume = None
        self.image_label.setText(self.title)
        self.image_label.setPixmap(QPixmap())

    def _refresh(self) -> None:
        if self._volume is None:
            return
        idx = int(self.slice_slider.value())
        slc = [slice(None)] * self._volume.ndim
        slc[self._axis] = idx
        plane = np.asarray(self._volume[tuple(slc)], dtype=np.float64)
        if plane.ndim > 2:
            plane = plane[..., 0]

        finite = plane[np.isfinite(plane)]
        if finite.size == 0:
            self.image_label.setText("empty")
            return

        lo, hi = np.percentile(finite, [1, 99])
        if hi <= lo:
            lo, hi = float(finite.min()), float(finite.max())
            if hi <= lo:
                hi = lo + 1.0

        # Brightness slider: 50 = default window; lower = brighter (wider floor)
        bright = self.brightness_slider.value() / 50.0
        mid = (lo + hi) / 2.0
        half = (hi - lo) / 2.0 / max(bright, 0.05)
        lo_w, hi_w = mid - half, mid + half

        norm = np.clip((plane - lo_w) / (hi_w - lo_w), 0, 1)
        img8 = (norm * 255).astype(np.uint8)
        # Flip for radiological-ish display of axial (axis 2 often z)
        img8 = np.ascontiguousarray(np.flipud(img8))
        h, w = img8.shape
        qimg = QImage(img8.data, w, h, w, QImage.Format.Format_Grayscale8).copy()
        pix = QPixmap.fromImage(qimg)
        scaled = pix.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._refresh()


class OrthoViewer(QWidget):
    """Stacked Axial / Sagittal / Coronal views."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.axial = PlaneView("Axial Image")
        self.sagittal = PlaneView("Sagittal Image")
        self.coronal = PlaneView("Coronal Image")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.axial, stretch=1)
        layout.addWidget(self.sagittal, stretch=1)
        layout.addWidget(self.coronal, stretch=1)

    def set_volume(self, data: np.ndarray) -> None:
        # Assume RAS-like array indices [i, j, k] ~ (x, y, z)
        vol = np.asarray(data)
        if vol.ndim > 3:
            vol = vol[..., 0]
        if vol.ndim != 3:
            raise ValueError(f"Expected 3D volume, got shape {vol.shape}")
        # Axial: slice along z (axis 2); Sagittal along x (0); Coronal along y (1)
        self.axial.set_volume(vol, axis=2)
        self.sagittal.set_volume(vol, axis=0)
        self.coronal.set_volume(vol, axis=1)

    def clear(self) -> None:
        self.axial.clear()
        self.sagittal.clear()
        self.coronal.clear()
