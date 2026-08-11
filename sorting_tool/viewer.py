"""Orthogonal MRI viewports with slice, brightness, stretch amount, and zoom/pan."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QImage, QMouseEvent, QPainter, QPixmap, QWheelEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)
from scipy import ndimage


class ImageCanvas(QLabel):
    """Image label that forwards wheel / drag / double-click for zoom and pan."""

    def __init__(self, owner: "PlaneView", title: str):
        super().__init__(title)
        self._owner = owner
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(280, 200)
        self.setStyleSheet(
            "background-color: #1a3a6b; color: white; border: 1px solid #0d213f;"
        )
        self.setScaledContents(False)
        self.setMouseTracking(True)
        self._dragging = False
        self._last_pos: QPoint | None = None

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        self._owner.handle_wheel(event)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._last_pos = event.position().toPoint()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging and self._last_pos is not None:
            pos = event.position().toPoint()
            delta = pos - self._last_pos
            self._last_pos = pos
            self._owner.handle_pan(delta.x(), delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._last_pos = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._owner.reset_view()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class PlaneView(QWidget):
    """One plane: image, slice slider, brightness slider, zoom/pan."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self._volume: np.ndarray | None = None
        self._axis = 0
        self._slice_count = 1
        self._row_zoom = 1.0
        self._col_zoom = 1.0
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._stretch = 0.0  # 0=fit, 1=full stretch
        self._base_img: np.ndarray | None = None

        self.image_label = ImageCanvas(self, title)

        self.slice_slider = QSlider(Qt.Orientation.Horizontal)
        self.slice_slider.setMinimum(0)
        self.slice_slider.setMaximum(0)
        self.slice_slider.valueChanged.connect(self._on_slice_or_bright)

        self.brightness_slider = QSlider(Qt.Orientation.Vertical)
        self.brightness_slider.setMinimum(1)
        self.brightness_slider.setMaximum(100)
        self.brightness_slider.setValue(50)
        self.brightness_slider.valueChanged.connect(self._on_slice_or_bright)

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

    def set_stretch(self, amount: float) -> None:
        """amount in [0, 1]: 0 keep aspect (fit), 1 fill viewport (stretch)."""
        self._stretch = float(np.clip(amount, 0.0, 1.0))
        self._refresh()

    def set_volume(
        self,
        volume: np.ndarray,
        axis: int,
        row_mm: float = 1.0,
        col_mm: float = 1.0,
    ) -> None:
        self._volume = np.asarray(volume)
        self._axis = axis
        self._row_zoom = max(float(row_mm), 1e-6)
        self._col_zoom = max(float(col_mm), 1e-6)
        self._slice_count = max(int(self._volume.shape[axis]), 1)
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self.slice_slider.blockSignals(True)
        self.slice_slider.setMaximum(self._slice_count - 1)
        self.slice_slider.setValue(self._slice_count // 2)
        self.slice_slider.blockSignals(False)
        self._rebuild_base()
        self._refresh()

    def clear(self) -> None:
        self._volume = None
        self._base_img = None
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self.image_label.setText(self.title)
        self.image_label.setPixmap(QPixmap())

    def reset_view(self) -> None:
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._refresh()

    def handle_wheel(self, event: QWheelEvent) -> None:
        if self._base_img is None:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else 1 / 1.15
        new_zoom = float(np.clip(self._zoom * factor, 0.5, 8.0))

        pos = event.position()
        lw = max(self.image_label.width(), 1)
        lh = max(self.image_label.height(), 1)
        cx = (pos.x() - lw / 2 - self._pan_x) / self._zoom
        cy = (pos.y() - lh / 2 - self._pan_y) / self._zoom
        self._zoom = new_zoom
        self._pan_x = pos.x() - lw / 2 - cx * self._zoom
        self._pan_y = pos.y() - lh / 2 - cy * self._zoom
        self._refresh()

    def handle_pan(self, dx: int, dy: int) -> None:
        if self._base_img is None:
            return
        self._pan_x += dx
        self._pan_y += dy
        self._refresh()

    def _on_slice_or_bright(self) -> None:
        self._rebuild_base()
        self._refresh()

    def _rebuild_base(self) -> None:
        if self._volume is None:
            self._base_img = None
            return
        idx = int(self.slice_slider.value())
        slc = [slice(None)] * self._volume.ndim
        slc[self._axis] = idx
        plane = np.asarray(self._volume[tuple(slc)], dtype=np.float64)
        if plane.ndim > 2:
            plane = plane[..., 0]

        finite = plane[np.isfinite(plane)]
        if finite.size == 0:
            self._base_img = None
            return

        lo, hi = np.percentile(finite, [1, 99])
        if hi <= lo:
            lo, hi = float(finite.min()), float(finite.max())
            if hi <= lo:
                hi = lo + 1.0

        bright = self.brightness_slider.value() / 50.0
        mid = (lo + hi) / 2.0
        half = (hi - lo) / 2.0 / max(bright, 0.05)
        lo_w, hi_w = mid - half, mid + half

        norm = np.clip((plane - lo_w) / (hi_w - lo_w), 0, 1)
        img8 = (norm * 255).astype(np.uint8)
        img8 = np.flipud(img8)

        min_mm = min(self._row_zoom, self._col_zoom)
        zoom_factors = (self._row_zoom / min_mm, self._col_zoom / min_mm)
        if abs(zoom_factors[0] - 1.0) > 1e-3 or abs(zoom_factors[1] - 1.0) > 1e-3:
            img8 = ndimage.zoom(img8, zoom_factors, order=1)
        self._base_img = np.ascontiguousarray(img8)

    def _target_size(self, pix: QPixmap, label_w: int, label_h: int) -> tuple[int, int]:
        """Interpolate between fit (aspect) and fill (stretch) by self._stretch."""
        fit = pix.scaled(
            label_w,
            label_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        fill = pix.scaled(
            label_w,
            label_h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        t = self._stretch
        w = int(round(fit.width() * (1 - t) + fill.width() * t))
        h = int(round(fit.height() * (1 - t) + fill.height() * t))
        return max(w, 1), max(h, 1)

    def _refresh(self) -> None:
        if self._base_img is None:
            if self._volume is not None:
                self.image_label.setText("empty")
            return

        img8 = self._base_img
        h, w = img8.shape
        qimg = QImage(img8.data, w, h, w, QImage.Format.Format_Grayscale8).copy()
        pix = QPixmap.fromImage(qimg)

        label_w = max(self.image_label.width(), 1)
        label_h = max(self.image_label.height(), 1)
        tw, th = self._target_size(pix, label_w, label_h)
        if abs(self._zoom - 1.0) > 1e-3:
            tw = max(int(tw * self._zoom), 1)
            th = max(int(th * self._zoom), 1)

        fitted = pix.scaled(
            tw,
            th,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        canvas = QPixmap(label_w, label_h)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        x = int((label_w - fitted.width()) / 2 + self._pan_x)
        y = int((label_h - fitted.height()) / 2 + self._pan_y)
        painter.drawPixmap(x, y, fitted)
        painter.end()
        self.image_label.setPixmap(canvas)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._refresh()


class OrthoViewer(QWidget):
    """Stacked Axial / Sagittal / Coronal views with a global stretch slider."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.axial = PlaneView("Axial Image")
        self.sagittal = PlaneView("Sagittal Image")
        self.coronal = PlaneView("Coronal Image")
        self._planes = (self.axial, self.sagittal, self.coronal)

        self.stretch_slider = QSlider(Qt.Orientation.Horizontal)
        self.stretch_slider.setMinimum(0)
        self.stretch_slider.setMaximum(100)
        self.stretch_slider.setValue(0)  # default = Fit
        self.stretch_slider.setToolTip("0 = Fit (aspect preserved), 100 = full Stretch")
        self.stretch_value = QLabel("0%")
        self.stretch_slider.valueChanged.connect(self._on_stretch)

        stretch_row = QHBoxLayout()
        stretch_row.addWidget(QLabel("Stretch"))
        stretch_row.addWidget(self.stretch_slider, stretch=1)
        stretch_row.addWidget(self.stretch_value)
        stretch_row.addWidget(QLabel("(Fit ← → Fill)"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(stretch_row)
        layout.addWidget(self.axial, stretch=1)
        layout.addWidget(self.sagittal, stretch=1)
        layout.addWidget(self.coronal, stretch=1)

    def _on_stretch(self, value: int) -> None:
        self.stretch_value.setText(f"{value}%")
        amount = value / 100.0
        for plane in self._planes:
            plane.set_stretch(amount)

    def set_volume(
        self,
        data: np.ndarray,
        zooms: tuple[float, float, float] | None = None,
    ) -> None:
        vol = np.asarray(data)
        if vol.ndim > 3:
            vol = vol[..., 0]
        if vol.ndim != 3:
            raise ValueError(f"Expected 3D volume, got shape {vol.shape}")
        zx, zy, zz = (1.0, 1.0, 1.0) if zooms is None else tuple(float(z) for z in zooms[:3])

        amount = self.stretch_slider.value() / 100.0
        self.axial.set_volume(vol, axis=2, row_mm=zy, col_mm=zx)
        self.sagittal.set_volume(vol, axis=0, row_mm=zz, col_mm=zy)
        self.coronal.set_volume(vol, axis=1, row_mm=zz, col_mm=zx)
        for plane in self._planes:
            plane.set_stretch(amount)

    def clear(self) -> None:
        for plane in self._planes:
            plane.clear()
