"""
Matching Tab - Fingerprint matching workflow
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt

from core.services.fingerprint_service import FingerprintService
from core.workers.matching_worker import MatchingWorker
from core.models import MatchResult
from ui.widgets.fingerprint_canvas import FingerprintCanvas


class MatchingTab(QWidget):
    """Tab for fingerprint matching"""

    def __init__(self, service: FingerprintService, parent=None):
        super().__init__(parent)
        self._service = service
        self._worker = None

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Status indicator at top
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)

        self._status_label = QLabel("Click 'Start Matching' and place your finger")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet("font-size: 14px; padding: 10px;")
        status_layout.addWidget(self._status_label)

        layout.addWidget(status_group)

        # Preview group
        preview_group = QGroupBox("Fingerprint Preview")
        preview_layout = QVBoxLayout(preview_group)

        self._canvas = FingerprintCanvas(size=280)
        preview_layout.addWidget(self._canvas, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(preview_group)

        # Result group
        result_group = QGroupBox("Match Result")
        result_layout = QVBoxLayout(result_group)

        self._result_frame = QFrame()
        self._result_frame.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        result_inner = QVBoxLayout(self._result_frame)

        self._result_icon = QLabel("--")
        self._result_icon.setStyleSheet("font-size: 36px; color: #999; font-weight: bold;")
        self._result_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._result_text = QLabel("No match attempted")
        self._result_text.setStyleSheet("font-size: 18px;")
        self._result_text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._user_info = QLabel("")
        self._user_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._user_info.setStyleSheet("color: #666;")

        result_inner.addWidget(self._result_icon)
        result_inner.addWidget(self._result_text)
        result_inner.addWidget(self._user_info)

        result_layout.addWidget(self._result_frame)
        layout.addWidget(result_group)

        # Buttons
        btn_layout = QHBoxLayout()

        self._match_btn = QPushButton("Start Matching")
        self._match_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 10px;")
        self._match_btn.clicked.connect(self._start_matching)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._cancel_matching)
        self._cancel_btn.setEnabled(False)

        btn_layout.addStretch()
        btn_layout.addWidget(self._cancel_btn)
        btn_layout.addWidget(self._match_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

    def _start_matching(self):
        # Reset result display
        self._result_icon.setText("...")
        self._result_icon.setStyleSheet("font-size: 36px; color: #999; font-weight: bold;")
        self._result_text.setText("Waiting for finger...")
        self._user_info.setText("")

        # Start worker
        self._worker = MatchingWorker(self._service)
        self._worker.progress_updated.connect(self._on_progress)
        self._worker.image_captured.connect(self._on_image_captured)
        self._worker.match_complete.connect(self._on_match_complete)
        self._worker.match_failed.connect(self._on_match_failed)
        self._worker.start()

        # Update UI
        self._match_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)

    def _cancel_matching(self):
        if self._worker:
            self._worker.stop()
            self._worker = None

        self._reset_ui()
        self._status_label.setText("Matching cancelled")

    def _on_progress(self, message: str):
        self._status_label.setText(message)

    def _on_image_captured(self, image: bytes, quality: float):
        self._canvas.set_image(image, quality, True)

    def _on_match_complete(self, result: MatchResult):
        self._reset_ui()

        if result.matched:
            self._result_icon.setText("OK")
            self._result_icon.setStyleSheet("font-size: 36px; color: #4CAF50; font-weight: bold;")
            self._result_text.setText("MATCH FOUND")
            self._result_text.setStyleSheet("font-size: 18px; color: #4CAF50; font-weight: bold;")

            if result.user:
                self._user_info.setText(
                    f"User: {result.user.username}\n"
                    f"Device ID: {result.user.device_user_id}"
                )
            else:
                self._user_info.setText(f"Device User ID: {result.user_id}")

            self._result_frame.setStyleSheet("""
                QFrame {
                    background-color: #E8F5E9;
                    border: 2px solid #4CAF50;
                    border-radius: 8px;
                    padding: 15px;
                }
            """)
        else:
            self._result_icon.setText("X")
            self._result_icon.setStyleSheet("font-size: 36px; color: #F44336; font-weight: bold;")
            self._result_text.setText("NO MATCH")
            self._result_text.setStyleSheet("font-size: 18px; color: #F44336; font-weight: bold;")
            self._user_info.setText("Fingerprint not recognized")

            self._result_frame.setStyleSheet("""
                QFrame {
                    background-color: #FFEBEE;
                    border: 2px solid #F44336;
                    border-radius: 8px;
                    padding: 15px;
                }
            """)

        self._status_label.setText("Ready for next match")

    def _on_match_failed(self, error: str):
        self._reset_ui()

        self._result_icon.setText("ERR")
        self._result_icon.setStyleSheet("font-size: 28px; color: #FF9800; font-weight: bold;")
        self._result_text.setText("ERROR")
        self._result_text.setStyleSheet("font-size: 18px; color: #FF9800;")
        self._user_info.setText(error)

        self._status_label.setText(f"Error: {error}")

    def _reset_ui(self):
        self._match_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._worker = None

    def closeEvent(self, event):
        if self._worker:
            self._worker.stop()
        super().closeEvent(event)
