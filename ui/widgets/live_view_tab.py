"""
Live View Tab - Real-time fingerprint streaming
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QGroupBox
)
from PyQt6.QtCore import Qt

from core.services.fingerprint_service import FingerprintService
from core.workers.sensor_worker import SensorWorker
from ui.widgets.fingerprint_canvas import FingerprintCanvas
from app.config import DEFAULT_FPS


class LiveViewTab(QWidget):
    """Tab for live fingerprint streaming"""

    def __init__(self, service: FingerprintService, parent=None):
        super().__init__(parent)
        self._service = service
        self._worker = None
        self._is_streaming = False

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Canvas
        canvas_group = QGroupBox("Live Preview")
        canvas_layout = QVBoxLayout(canvas_group)

        self._canvas = FingerprintCanvas(size=300)
        canvas_layout.addWidget(self._canvas, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(canvas_group)

        # Info panel
        info_group = QGroupBox("Status")
        info_layout = QHBoxLayout(info_group)

        self._status_label = QLabel("Stopped")
        self._fps_label = QLabel("FPS: --")
        self._quality_label = QLabel("Quality: --")

        info_layout.addWidget(self._status_label)
        info_layout.addStretch()
        info_layout.addWidget(self._fps_label)
        info_layout.addWidget(self._quality_label)

        layout.addWidget(info_group)

        # Controls
        controls_group = QGroupBox("Controls")
        controls_layout = QHBoxLayout(controls_group)

        # FPS selector
        fps_label = QLabel("Target FPS:")
        self._fps_combo = QComboBox()
        self._fps_combo.addItems(["5", "10", "15"])
        self._fps_combo.setCurrentText(str(DEFAULT_FPS))
        self._fps_combo.currentTextChanged.connect(self._on_fps_changed)

        # Buttons
        self._start_btn = QPushButton("Start Streaming")
        self._start_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self._start_btn.clicked.connect(self._toggle_streaming)

        self._capture_btn = QPushButton("Capture Frame")
        self._capture_btn.clicked.connect(self._capture_single)
        self._capture_btn.setEnabled(False)

        controls_layout.addWidget(fps_label)
        controls_layout.addWidget(self._fps_combo)
        controls_layout.addStretch()
        controls_layout.addWidget(self._capture_btn)
        controls_layout.addWidget(self._start_btn)

        layout.addWidget(controls_group)
        layout.addStretch()

    def _toggle_streaming(self):
        if self._is_streaming:
            self._stop_streaming()
        else:
            self._start_streaming()

    def _start_streaming(self):
        fps = int(self._fps_combo.currentText())
        self._worker = SensorWorker(self._service, fps)
        self._worker.frame_captured.connect(self._on_frame_captured)
        self._worker.fps_updated.connect(self._on_fps_updated)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

        self._is_streaming = True
        self._start_btn.setText("Stop Streaming")
        self._start_btn.setStyleSheet("background-color: #F44336; color: white;")
        self._status_label.setText("Streaming...")
        self._capture_btn.setEnabled(False)
        self._fps_combo.setEnabled(False)

        # Turn on LED
        self._service.led_on(0x07)  # WHITE

    def _stop_streaming(self):
        if self._worker:
            self._worker.stop()
            self._worker = None

        self._is_streaming = False
        self._start_btn.setText("Start Streaming")
        self._start_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self._status_label.setText("Stopped")
        self._fps_label.setText("FPS: --")
        self._capture_btn.setEnabled(True)
        self._fps_combo.setEnabled(True)

        # Turn off LED
        self._service.led_off()

    def _on_frame_captured(self, image: bytes, quality: float, has_finger: bool):
        self._canvas.set_image(image, quality, has_finger)
        self._quality_label.setText(f"Quality: {quality:.1f}")

    def _on_fps_updated(self, fps: float):
        self._fps_label.setText(f"FPS: {fps:.1f}")

    def _on_fps_changed(self, fps_str: str):
        if self._worker:
            self._worker.fps = int(fps_str)

    def _on_error(self, error: str):
        self._status_label.setText(f"Error: {error}")

    def _capture_single(self):
        """Capture a single frame"""
        self._service.led_on(0x07)  # WHITE

        result = self._service.capture_image()
        if result.success:
            self._canvas.set_image(result.image_data, result.quality_score, result.has_finger)
            self._quality_label.setText(f"Quality: {result.quality_score:.1f}")

        self._service.led_off()

    def closeEvent(self, event):
        self._stop_streaming()
        super().closeEvent(event)
