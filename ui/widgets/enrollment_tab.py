"""
Enrollment Tab - User enrollment workflow
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QCheckBox, QGroupBox, QProgressBar,
    QMessageBox, QFrame
)
from PyQt6.QtCore import Qt

from core.services.fingerprint_service import FingerprintService
from core.workers.enrollment_worker import EnrollmentWorker
from ui.widgets.fingerprint_canvas import FingerprintCanvas


class EnrollmentTab(QWidget):
    """Tab for fingerprint enrollment"""

    def __init__(self, service: FingerprintService, parent=None):
        super().__init__(parent)
        self._service = service
        self._worker = None

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Step indicator
        steps_group = QGroupBox("Enrollment Steps")
        steps_layout = QHBoxLayout(steps_group)

        self._step_labels = []
        step_names = ["1. Enter Name", "2. Place Finger", "3. Capture", "4. Complete"]
        for i, name in enumerate(step_names):
            step_label = QLabel(name)
            step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            step_label.setStyleSheet("padding: 8px; border-radius: 4px; background-color: #e0e0e0;")
            steps_layout.addWidget(step_label)
            self._step_labels.append(step_label)

        self._highlight_step(0)
        layout.addWidget(steps_group)

        # User info group
        user_group = QGroupBox("User Information")
        user_layout = QHBoxLayout(user_group)

        user_layout.addWidget(QLabel("Username:"))
        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText("Enter username...")
        self._username_input.textChanged.connect(self._on_username_changed)
        user_layout.addWidget(self._username_input)

        layout.addWidget(user_group)

        # Preview group
        preview_group = QGroupBox("Fingerprint Preview")
        preview_layout = QVBoxLayout(preview_group)

        self._canvas = FingerprintCanvas(size=280)
        preview_layout.addWidget(self._canvas, alignment=Qt.AlignmentFlag.AlignCenter)

        # Progress
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        preview_layout.addWidget(self._progress_bar)

        self._status_label = QLabel("Enter username and click Start Enrollment")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet("font-size: 14px; padding: 10px;")
        preview_layout.addWidget(self._status_label)

        layout.addWidget(preview_group)

        # Options group
        options_group = QGroupBox("Options")
        options_layout = QHBoxLayout(options_group)

        self._save_bmp_checkbox = QCheckBox("Save fingerprint as BMP")
        self._save_bmp_checkbox.setChecked(True)

        options_layout.addWidget(self._save_bmp_checkbox)
        options_layout.addStretch()

        layout.addWidget(options_group)

        # Buttons
        btn_layout = QHBoxLayout()

        self._enroll_btn = QPushButton("Start Enrollment")
        self._enroll_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        self._enroll_btn.clicked.connect(self._start_enrollment)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._cancel_enrollment)
        self._cancel_btn.setEnabled(False)

        btn_layout.addStretch()
        btn_layout.addWidget(self._cancel_btn)
        btn_layout.addWidget(self._enroll_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

    def _highlight_step(self, step_index: int):
        """Highlight the current step"""
        for i, label in enumerate(self._step_labels):
            if i < step_index:
                # Completed steps
                label.setStyleSheet("padding: 8px; border-radius: 4px; background-color: #4CAF50; color: white;")
            elif i == step_index:
                # Current step
                label.setStyleSheet("padding: 8px; border-radius: 4px; background-color: #2196F3; color: white; font-weight: bold;")
            else:
                # Future steps
                label.setStyleSheet("padding: 8px; border-radius: 4px; background-color: #e0e0e0;")

    def _on_username_changed(self, text: str):
        """Update step indicator when username is entered"""
        if text.strip():
            self._highlight_step(1)
        else:
            self._highlight_step(0)

    def _start_enrollment(self):
        username = self._username_input.text().strip()
        if not username:
            QMessageBox.warning(self, "Warning", "Please enter a username")
            return

        self._highlight_step(1)

        # Start enrollment worker
        self._worker = EnrollmentWorker(
            self._service,
            username,
            save_bmp=self._save_bmp_checkbox.isChecked()
        )
        self._worker.progress_updated.connect(self._on_progress)
        self._worker.image_captured.connect(self._on_image_captured)
        self._worker.enrollment_complete.connect(self._on_enrollment_complete)
        self._worker.enrollment_failed.connect(self._on_enrollment_failed)
        self._worker.start()

        # Update UI
        self._enroll_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._username_input.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)

    def _cancel_enrollment(self):
        if self._worker:
            self._worker.stop()
            self._worker = None

        self._reset_ui()
        self._highlight_step(0)
        self._status_label.setText("Enrollment cancelled")

    def _on_progress(self, message: str, percentage: int):
        self._status_label.setText(message)
        self._progress_bar.setValue(percentage)

        # Update step indicator based on progress
        if percentage < 30:
            self._highlight_step(1)  # Place Finger
        elif percentage < 80:
            self._highlight_step(2)  # Capture
        else:
            self._highlight_step(3)  # Complete

    def _on_image_captured(self, image: bytes, quality: float):
        self._canvas.set_image(image, quality, True)
        self._highlight_step(2)

    def _on_enrollment_complete(self, user):
        self._highlight_step(3)
        self._reset_ui()
        self._canvas.clear()
        self._username_input.clear()

        QMessageBox.information(
            self,
            "Success",
            f"User '{user.username}' enrolled successfully!\nDevice ID: {user.device_user_id}"
        )
        self._status_label.setText("Enrollment complete! Ready for next user.")
        self._highlight_step(0)

    def _on_enrollment_failed(self, error: str):
        self._reset_ui()
        self._highlight_step(0)

        QMessageBox.critical(self, "Enrollment Failed", error)
        self._status_label.setText(f"Failed: {error}")

    def _reset_ui(self):
        self._enroll_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._username_input.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._worker = None

    def closeEvent(self, event):
        if self._worker:
            self._worker.stop()
        super().closeEvent(event)
