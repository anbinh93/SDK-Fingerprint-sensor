"""
MDGT Edge — PyQt5 Desktop Application for Fingerprint Verification.

Runs directly on Jetson Nano with real-time sensor visualization.
"""
from __future__ import annotations

import sys
import time
import struct
import numpy as np
from typing import Optional

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QLabel, QPushButton, QGroupBox, QStatusBar,
    QListWidget, QListWidgetItem, QLineEdit, QComboBox,
    QProgressBar, QMessageBox, QSplitter, QFrame,
    QApplication, QSizePolicy, QSpacerItem,
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QImage, QPixmap, QFont, QPalette, QColor, QIcon

from mdgt_edge.sensor.base import USBSensorDriver, CaptureResult, SensorInfo, LEDColor


# ============================================================
# Worker thread for blocking sensor operations
# ============================================================

class SensorWorker(QThread):
    """Background thread for sensor operations."""
    capture_done = pyqtSignal(object)  # CaptureResult
    finger_detected = pyqtSignal(bool)
    match_done = pyqtSignal(bool, int)  # matched, user_id
    enroll_done = pyqtSignal(bool, int)  # success, user_id
    error = pyqtSignal(str)

    def __init__(self, driver: USBSensorDriver):
        super().__init__()
        self._driver = driver
        self._task: Optional[str] = None
        self._task_args: dict = {}
        self._running = False

    def capture(self):
        self._task = "capture"
        self.start()

    def check_finger(self):
        self._task = "check_finger"
        self.start()

    def match(self, timeout: float = 5.0):
        self._task = "match"
        self._task_args = {"timeout": timeout}
        self.start()

    def enroll(self, user_id: Optional[int] = None):
        self._task = "enroll"
        self._task_args = {"user_id": user_id}
        self.start()

    def run(self):
        try:
            if self._task == "capture":
                result = self._driver.capture_image()
                self.capture_done.emit(result)
            elif self._task == "check_finger":
                has = self._driver.check_finger()
                self.finger_detected.emit(has)
            elif self._task == "match":
                ok, uid = self._driver.match_fingerprint(
                    self._task_args.get("timeout", 5.0)
                )
                self.match_done.emit(ok, uid)
            elif self._task == "enroll":
                ok, uid = self._driver.add_user(
                    self._task_args.get("user_id")
                )
                self.enroll_done.emit(ok, uid)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._task_args = {}


# ============================================================
# Fingerprint display widget
# ============================================================

class FingerprintView(QLabel):
    """Widget that displays a 192x192 grayscale fingerprint image."""

    def __init__(self, size: int = 256, parent=None):
        super().__init__(parent)
        self._display_size = size
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "background-color: #1B2631; border: 2px solid #2C3E50; border-radius: 8px;"
        )
        self._show_placeholder()

    def _show_placeholder(self):
        self.setText("No Image")
        self.setStyleSheet(
            "background-color: #1B2631; border: 2px solid #2C3E50; "
            "border-radius: 8px; color: #5D6D7E; font-size: 14px;"
        )

    def update_image(self, image_data: bytes, width: int = 192, height: int = 192):
        """Update the displayed fingerprint image from raw grayscale bytes."""
        if not image_data or len(image_data) < width * height:
            self._show_placeholder()
            return

        arr = np.frombuffer(image_data, dtype=np.uint8).reshape((height, width))
        qimg = QImage(arr.data, width, height, width, QImage.Format_Grayscale8)
        pixmap = QPixmap.fromImage(qimg).scaled(
            self._display_size, self._display_size,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.setPixmap(pixmap)
        self.setStyleSheet(
            "background-color: #1B2631; border: 2px solid #27AE60; border-radius: 8px;"
        )

    def clear_image(self):
        self._show_placeholder()


# ============================================================
# Status indicator widget
# ============================================================

class StatusDot(QWidget):
    """Small colored dot indicator."""

    def __init__(self, color: str = "#E74C3C", size: int = 12, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._color = color
        self._update_style()

    def set_color(self, color: str):
        self._color = color
        self._update_style()

    def _update_style(self):
        self.setStyleSheet(
            f"background-color: {self._color}; border-radius: {self.width() // 2}px;"
        )


# ============================================================
# Live View Tab
# ============================================================

class LiveViewTab(QWidget):
    """Real-time fingerprint sensor visualization."""

    def __init__(self, driver: USBSensorDriver, parent=None):
        super().__init__(parent)
        self._driver = driver
        self._streaming = False
        self._worker = SensorWorker(driver)
        self._worker.capture_done.connect(self._on_capture)
        self._worker.error.connect(self._on_error)

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_capture)

        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)

        # Left: fingerprint display
        left = QVBoxLayout()
        self._fp_view = FingerprintView(320)
        left.addWidget(self._fp_view, alignment=Qt.AlignCenter)

        self._quality_label = QLabel("Quality: --")
        self._quality_label.setAlignment(Qt.AlignCenter)
        self._quality_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2C3E50;")
        left.addWidget(self._quality_label)

        self._finger_label = QLabel("Finger: --")
        self._finger_label.setAlignment(Qt.AlignCenter)
        self._finger_label.setStyleSheet("font-size: 14px; color: #5D6D7E;")
        left.addWidget(self._finger_label)

        # Controls
        btn_layout = QHBoxLayout()
        self._start_btn = QPushButton("▶ Start Stream")
        self._start_btn.setStyleSheet(
            "QPushButton { background-color: #27AE60; color: white; font-size: 14px; "
            "font-weight: bold; padding: 10px 24px; border-radius: 6px; }"
            "QPushButton:hover { background-color: #229954; }"
        )
        self._start_btn.clicked.connect(self._toggle_stream)
        btn_layout.addWidget(self._start_btn)

        self._capture_btn = QPushButton("📸 Single Capture")
        self._capture_btn.setStyleSheet(
            "QPushButton { background-color: #2980B9; color: white; font-size: 14px; "
            "font-weight: bold; padding: 10px 24px; border-radius: 6px; }"
            "QPushButton:hover { background-color: #2471A3; }"
        )
        self._capture_btn.clicked.connect(self._single_capture)
        btn_layout.addWidget(self._capture_btn)

        left.addLayout(btn_layout)

        layout.addLayout(left, stretch=2)

        # Right: info panel
        right = QVBoxLayout()

        info_group = QGroupBox("Sensor Info")
        info_layout = QGridLayout()
        self._info_labels = {}
        rows = [
            ("Status", "status"), ("Hardware", "hardware"),
            ("Resolution", "resolution"), ("Image Size", "image_size"),
            ("Users", "users"), ("Compare Level", "compare"),
        ]
        for i, (label, key) in enumerate(rows):
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet("font-weight: bold; color: #2C3E50;")
            val = QLabel("--")
            val.setStyleSheet("color: #5D6D7E;")
            info_layout.addWidget(lbl, i, 0)
            info_layout.addWidget(val, i, 1)
            self._info_labels[key] = val
        info_group.setLayout(info_layout)
        right.addWidget(info_group)

        # LED controls
        led_group = QGroupBox("LED Control")
        led_layout = QHBoxLayout()
        for color_name, color_val in [("Green", LEDColor.GREEN), ("Red", LEDColor.RED),
                                       ("Blue", LEDColor.BLUE), ("Off", LEDColor.OFF)]:
            btn = QPushButton(color_name)
            btn.setStyleSheet(
                f"padding: 6px 16px; border-radius: 4px; font-weight: bold;"
            )
            btn.clicked.connect(lambda checked, c=color_val: self._set_led(c))
            led_layout.addWidget(btn)
        led_group.setLayout(led_layout)
        right.addWidget(led_group)

        # Capture history
        hist_group = QGroupBox("Recent Captures")
        hist_layout = QVBoxLayout()
        self._history_list = QListWidget()
        self._history_list.setMaximumHeight(200)
        hist_layout.addWidget(self._history_list)
        hist_group.setLayout(hist_layout)
        right.addWidget(hist_group)

        right.addStretch()
        layout.addLayout(right, stretch=1)

    def refresh_info(self):
        if not self._driver.is_connected():
            self._info_labels["status"].setText("Disconnected")
            self._info_labels["status"].setStyleSheet("color: #E74C3C; font-weight: bold;")
            return

        info = self._driver.get_info()
        self._info_labels["status"].setText("Connected")
        self._info_labels["status"].setStyleSheet("color: #27AE60; font-weight: bold;")
        self._info_labels["hardware"].setText(info.name)
        self._info_labels["resolution"].setText(f"{info.resolution_dpi} DPI")
        self._info_labels["image_size"].setText(f"{info.image_width}x{info.image_height}")

        try:
            count = self._driver.get_user_count()
            self._info_labels["users"].setText(str(count) if count >= 0 else "N/A")
        except Exception:
            self._info_labels["users"].setText("N/A")

        try:
            level = self._driver.get_compare_level()
            self._info_labels["compare"].setText(str(level) if level >= 0 else "N/A")
        except Exception:
            self._info_labels["compare"].setText("N/A")

    def _toggle_stream(self):
        if self._streaming:
            self._stop_stream()
        else:
            self._start_stream()

    def _start_stream(self):
        self._streaming = True
        self._start_btn.setText("⏹ Stop Stream")
        self._start_btn.setStyleSheet(
            "QPushButton { background-color: #E74C3C; color: white; font-size: 14px; "
            "font-weight: bold; padding: 10px 24px; border-radius: 6px; }"
            "QPushButton:hover { background-color: #C0392B; }"
        )
        self._poll_timer.start(200)  # 5 FPS

    def _stop_stream(self):
        self._streaming = False
        self._poll_timer.stop()
        self._start_btn.setText("▶ Start Stream")
        self._start_btn.setStyleSheet(
            "QPushButton { background-color: #27AE60; color: white; font-size: 14px; "
            "font-weight: bold; padding: 10px 24px; border-radius: 6px; }"
            "QPushButton:hover { background-color: #229954; }"
        )

    def _poll_capture(self):
        if not self._worker.isRunning():
            self._worker.capture()

    def _single_capture(self):
        if not self._worker.isRunning():
            self._worker.capture()

    def _on_capture(self, result: CaptureResult):
        if result.success:
            self._fp_view.update_image(result.image_data, result.width, result.height)
            q = result.quality_score
            color = "#27AE60" if q >= 60 else "#F39C12" if q >= 30 else "#E74C3C"
            self._quality_label.setText(f"Quality: {q:.1f}")
            self._quality_label.setStyleSheet(
                f"font-size: 16px; font-weight: bold; color: {color};"
            )
            self._finger_label.setText(
                f"Finger: {'Detected' if result.has_finger else 'Not detected'}"
            )
            ts = time.strftime("%H:%M:%S")
            self._history_list.insertItem(
                0, f"[{ts}] Q={q:.1f} finger={'Y' if result.has_finger else 'N'}"
            )
            if self._history_list.count() > 50:
                self._history_list.takeItem(self._history_list.count() - 1)
        else:
            self._quality_label.setText(f"Error: {result.error}")
            self._quality_label.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: #E74C3C;"
            )

    def _on_error(self, msg: str):
        self._quality_label.setText(f"Error: {msg}")

    def _set_led(self, color: int):
        if color == LEDColor.OFF:
            self._driver.led_off()
        else:
            self._driver.led_on(color)

    def stop(self):
        self._stop_stream()


# ============================================================
# Enrollment Tab
# ============================================================

class EnrollTab(QWidget):
    """Fingerprint enrollment tab."""

    def __init__(self, driver: USBSensorDriver, parent=None):
        super().__init__(parent)
        self._driver = driver
        self._worker = SensorWorker(driver)
        self._worker.enroll_done.connect(self._on_enroll_done)
        self._worker.error.connect(self._on_error)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Instructions
        instr = QLabel(
            "Place finger on sensor and click 'Enroll'. "
            "The sensor will capture 3 samples automatically.\n"
            "You can optionally specify a User ID, or leave blank for auto-assign."
        )
        instr.setWordWrap(True)
        instr.setStyleSheet("font-size: 14px; color: #5D6D7E; padding: 10px;")
        layout.addWidget(instr)

        # User ID input
        form = QHBoxLayout()
        form.addWidget(QLabel("User ID (optional):"))
        self._uid_input = QLineEdit()
        self._uid_input.setPlaceholderText("Auto-assign if empty")
        self._uid_input.setMaximumWidth(200)
        form.addWidget(self._uid_input)
        form.addStretch()
        layout.addLayout(form)

        # Enroll button
        self._enroll_btn = QPushButton("🖐 Enroll Fingerprint")
        self._enroll_btn.setStyleSheet(
            "QPushButton { background-color: #8E44AD; color: white; font-size: 16px; "
            "font-weight: bold; padding: 12px 32px; border-radius: 6px; }"
            "QPushButton:hover { background-color: #7D3C98; }"
            "QPushButton:disabled { background-color: #BDC3C7; }"
        )
        self._enroll_btn.clicked.connect(self._start_enroll)
        layout.addWidget(self._enroll_btn, alignment=Qt.AlignCenter)

        # Status
        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet("font-size: 16px; padding: 20px;")
        layout.addWidget(self._status)

        # Result log
        self._log = QListWidget()
        layout.addWidget(self._log)

        layout.addStretch()

    def _start_enroll(self):
        uid_text = self._uid_input.text().strip()
        uid = int(uid_text) if uid_text.isdigit() else None

        self._enroll_btn.setEnabled(False)
        self._status.setText("Place finger on sensor...")
        self._status.setStyleSheet("font-size: 16px; padding: 20px; color: #2980B9;")

        self._worker.enroll(uid)

    def _on_enroll_done(self, success: bool, user_id: int):
        self._enroll_btn.setEnabled(True)
        ts = time.strftime("%H:%M:%S")
        if success:
            self._status.setText(f"Enrolled! User ID: {user_id}")
            self._status.setStyleSheet(
                "font-size: 16px; padding: 20px; color: #27AE60; font-weight: bold;"
            )
            self._log.insertItem(0, f"[{ts}] ✓ Enrolled user {user_id}")
            self._driver.led_on(LEDColor.GREEN)
            QTimer.singleShot(1000, self._driver.led_off)
        else:
            self._status.setText("Enrollment failed. Try again.")
            self._status.setStyleSheet(
                "font-size: 16px; padding: 20px; color: #E74C3C; font-weight: bold;"
            )
            self._log.insertItem(0, f"[{ts}] ✗ Enrollment failed")

    def _on_error(self, msg: str):
        self._enroll_btn.setEnabled(True)
        self._status.setText(f"Error: {msg}")
        self._status.setStyleSheet(
            "font-size: 16px; padding: 20px; color: #E74C3C;"
        )


# ============================================================
# Verification Tab
# ============================================================

class VerifyTab(QWidget):
    """1:N fingerprint identification tab."""

    def __init__(self, driver: USBSensorDriver, parent=None):
        super().__init__(parent)
        self._driver = driver
        self._worker = SensorWorker(driver)
        self._worker.match_done.connect(self._on_match_done)
        self._worker.capture_done.connect(self._on_capture)
        self._worker.error.connect(self._on_error)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Top area: fingerprint + result side by side
        top = QHBoxLayout()

        # Fingerprint preview
        fp_layout = QVBoxLayout()
        self._fp_view = FingerprintView(256)
        fp_layout.addWidget(self._fp_view, alignment=Qt.AlignCenter)

        self._quality_label = QLabel("Quality: --")
        self._quality_label.setAlignment(Qt.AlignCenter)
        self._quality_label.setStyleSheet("font-size: 14px; color: #5D6D7E;")
        fp_layout.addWidget(self._quality_label)
        top.addLayout(fp_layout)

        # Result display
        result_layout = QVBoxLayout()
        self._result_icon = QLabel("?")
        self._result_icon.setAlignment(Qt.AlignCenter)
        self._result_icon.setFixedSize(120, 120)
        self._result_icon.setStyleSheet(
            "background-color: #ECF0F1; border-radius: 60px; "
            "font-size: 48px; color: #BDC3C7;"
        )
        result_layout.addWidget(self._result_icon, alignment=Qt.AlignCenter)

        self._result_label = QLabel("Place finger and click Identify")
        self._result_label.setAlignment(Qt.AlignCenter)
        self._result_label.setWordWrap(True)
        self._result_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2C3E50;")
        result_layout.addWidget(self._result_label)

        self._user_label = QLabel("")
        self._user_label.setAlignment(Qt.AlignCenter)
        self._user_label.setStyleSheet("font-size: 14px; color: #5D6D7E;")
        result_layout.addWidget(self._user_label)

        top.addLayout(result_layout)

        layout.addLayout(top)

        # Button
        btn_layout = QHBoxLayout()

        self._capture_btn = QPushButton("📸 Capture")
        self._capture_btn.setStyleSheet(
            "QPushButton { background-color: #2980B9; color: white; font-size: 14px; "
            "font-weight: bold; padding: 10px 24px; border-radius: 6px; }"
            "QPushButton:hover { background-color: #2471A3; }"
        )
        self._capture_btn.clicked.connect(self._do_capture)
        btn_layout.addWidget(self._capture_btn)

        self._identify_btn = QPushButton("🔍 Identify (1:N)")
        self._identify_btn.setStyleSheet(
            "QPushButton { background-color: #27AE60; color: white; font-size: 14px; "
            "font-weight: bold; padding: 10px 24px; border-radius: 6px; }"
            "QPushButton:hover { background-color: #229954; }"
            "QPushButton:disabled { background-color: #BDC3C7; }"
        )
        self._identify_btn.clicked.connect(self._do_identify)
        btn_layout.addWidget(self._identify_btn)

        layout.addLayout(btn_layout)

        # History
        self._log = QListWidget()
        layout.addWidget(self._log)

    def _do_capture(self):
        if not self._worker.isRunning():
            self._worker.capture()

    def _on_capture(self, result: CaptureResult):
        if result.success:
            self._fp_view.update_image(result.image_data, result.width, result.height)
            q = result.quality_score
            color = "#27AE60" if q >= 60 else "#F39C12" if q >= 30 else "#E74C3C"
            self._quality_label.setText(f"Quality: {q:.1f}")
            self._quality_label.setStyleSheet(f"font-size: 14px; color: {color};")

    def _do_identify(self):
        self._identify_btn.setEnabled(False)
        self._result_label.setText("Scanning...")
        self._result_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #2980B9;"
        )
        self._result_icon.setText("...")
        self._result_icon.setStyleSheet(
            "background-color: #D6EAF8; border-radius: 60px; "
            "font-size: 24px; color: #2980B9;"
        )
        self._user_label.setText("")
        self._worker.match(timeout=10.0)

    def _on_match_done(self, matched: bool, user_id: int):
        self._identify_btn.setEnabled(True)
        ts = time.strftime("%H:%M:%S")

        if matched:
            self._result_icon.setText("✓")
            self._result_icon.setStyleSheet(
                "background-color: #D5F5E3; border-radius: 60px; "
                "font-size: 48px; color: #27AE60;"
            )
            self._result_label.setText("MATCHED")
            self._result_label.setStyleSheet(
                "font-size: 24px; font-weight: bold; color: #27AE60;"
            )
            self._user_label.setText(f"User ID: {user_id}")
            self._log.insertItem(0, f"[{ts}] ✓ Matched user {user_id}")
            self._driver.led_on(LEDColor.GREEN)
            QTimer.singleShot(1500, self._driver.led_off)
        else:
            self._result_icon.setText("✗")
            self._result_icon.setStyleSheet(
                "background-color: #FADBD8; border-radius: 60px; "
                "font-size: 48px; color: #E74C3C;"
            )
            self._result_label.setText("NOT MATCHED")
            self._result_label.setStyleSheet(
                "font-size: 24px; font-weight: bold; color: #E74C3C;"
            )
            self._user_label.setText("")
            self._log.insertItem(0, f"[{ts}] ✗ No match")
            self._driver.led_on(LEDColor.RED)
            QTimer.singleShot(1500, self._driver.led_off)

    def _on_error(self, msg: str):
        self._identify_btn.setEnabled(True)
        self._result_label.setText(f"Error: {msg}")
        self._result_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #E74C3C;"
        )


# ============================================================
# Users Tab
# ============================================================

class UsersTab(QWidget):
    """User management — list/delete enrolled users."""

    def __init__(self, driver: USBSensorDriver, parent=None):
        super().__init__(parent)
        self._driver = driver
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Actions
        btn_layout = QHBoxLayout()

        self._refresh_btn = QPushButton("🔄 Refresh Count")
        self._refresh_btn.setStyleSheet(
            "padding: 8px 20px; border-radius: 4px; font-weight: bold;"
        )
        self._refresh_btn.clicked.connect(self._refresh)
        btn_layout.addWidget(self._refresh_btn)

        self._delete_input = QLineEdit()
        self._delete_input.setPlaceholderText("User ID to delete")
        self._delete_input.setMaximumWidth(150)
        btn_layout.addWidget(self._delete_input)

        self._delete_btn = QPushButton("🗑 Delete User")
        self._delete_btn.setStyleSheet(
            "QPushButton { background-color: #E74C3C; color: white; "
            "padding: 8px 20px; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #C0392B; }"
        )
        self._delete_btn.clicked.connect(self._delete_user)
        btn_layout.addWidget(self._delete_btn)

        self._delete_all_btn = QPushButton("⚠ Delete ALL")
        self._delete_all_btn.setStyleSheet(
            "QPushButton { background-color: #922B21; color: white; "
            "padding: 8px 20px; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #7B241C; }"
        )
        self._delete_all_btn.clicked.connect(self._delete_all)
        btn_layout.addWidget(self._delete_all_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Info display
        self._info_label = QLabel("Click Refresh to see user count")
        self._info_label.setStyleSheet("font-size: 16px; padding: 20px; color: #2C3E50;")
        layout.addWidget(self._info_label)

        self._log = QListWidget()
        layout.addWidget(self._log)

    def _refresh(self):
        count = self._driver.get_user_count()
        level = self._driver.get_compare_level()
        self._info_label.setText(
            f"Enrolled users on device: {count}  |  Compare level: {level}"
        )
        ts = time.strftime("%H:%M:%S")
        self._log.insertItem(0, f"[{ts}] Refreshed: {count} users")

    def _delete_user(self):
        uid_text = self._delete_input.text().strip()
        if not uid_text.isdigit():
            QMessageBox.warning(self, "Error", "Enter a valid user ID number")
            return

        uid = int(uid_text)
        reply = QMessageBox.question(
            self, "Confirm", f"Delete user {uid}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ok = self._driver.delete_user(uid)
            ts = time.strftime("%H:%M:%S")
            if ok:
                self._log.insertItem(0, f"[{ts}] ✓ Deleted user {uid}")
                self._delete_input.clear()
                self._refresh()
            else:
                self._log.insertItem(0, f"[{ts}] ✗ Failed to delete user {uid}")

    def _delete_all(self):
        reply = QMessageBox.warning(
            self, "Delete ALL Users",
            "This will delete ALL enrolled fingerprints from the device.\n\nAre you sure?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ok = self._driver.delete_all()
            ts = time.strftime("%H:%M:%S")
            if ok:
                self._log.insertItem(0, f"[{ts}] ✓ All users deleted")
                self._refresh()
            else:
                self._log.insertItem(0, f"[{ts}] ✗ Failed to delete all users")


# ============================================================
# Main Window
# ============================================================

class MainWindow(QMainWindow):
    """MDGT Edge Fingerprint System — Main Window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MDGT Edge — Fingerprint Verification System")
        self.setMinimumSize(900, 600)

        # Initialize sensor
        self._driver = USBSensorDriver(
            vid=0x0483, pid=0x5720,
            sdk_path="/home/binhan2/jetson-fingerverify-app"
        )
        self._connected = self._driver.open()

        self._init_ui()
        self._update_status()

        # Periodic status refresh
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status)
        self._status_timer.start(5000)

    def _init_ui(self):
        # Central widget with tabs
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #D5D8DC; }"
            "QTabBar::tab { padding: 8px 20px; font-size: 14px; font-weight: bold; }"
            "QTabBar::tab:selected { background: #2980B9; color: white; }"
            "QTabBar::tab:!selected { background: #ECF0F1; color: #2C3E50; }"
        )

        # Tabs
        self._live_tab = LiveViewTab(self._driver)
        self._tabs.addTab(self._live_tab, "📷 Live View")

        self._verify_tab = VerifyTab(self._driver)
        self._tabs.addTab(self._verify_tab, "🔍 Verify")

        self._enroll_tab = EnrollTab(self._driver)
        self._tabs.addTab(self._enroll_tab, "🖐 Enroll")

        self._users_tab = UsersTab(self._driver)
        self._tabs.addTab(self._users_tab, "👤 Users")

        self.setCentralWidget(self._tabs)

        # Status bar
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)

        self._sensor_dot = StatusDot()
        self._statusbar.addPermanentWidget(self._sensor_dot)
        self._sensor_status = QLabel("Sensor: --")
        self._statusbar.addPermanentWidget(self._sensor_status)

    def _update_status(self):
        connected = self._driver.is_connected()
        if connected:
            self._sensor_dot.set_color("#27AE60")
            self._sensor_status.setText("Sensor: Connected")
            self._sensor_status.setStyleSheet("color: #27AE60; font-weight: bold;")
        else:
            self._sensor_dot.set_color("#E74C3C")
            self._sensor_status.setText("Sensor: Disconnected")
            self._sensor_status.setStyleSheet("color: #E74C3C; font-weight: bold;")

        # Refresh live view info when on that tab
        if self._tabs.currentIndex() == 0:
            self._live_tab.refresh_info()

    def closeEvent(self, event):
        self._live_tab.stop()
        self._status_timer.stop()
        self._driver.close()
        event.accept()


# ============================================================
# Entry point
# ============================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark-ish palette
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#F8F9F9"))
    palette.setColor(QPalette.WindowText, QColor("#2C3E50"))
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.AlternateBase, QColor("#ECF0F1"))
    palette.setColor(QPalette.ToolTipBase, QColor("#2C3E50"))
    palette.setColor(QPalette.ToolTipText, QColor("#FFFFFF"))
    palette.setColor(QPalette.Text, QColor("#2C3E50"))
    palette.setColor(QPalette.Button, QColor("#ECF0F1"))
    palette.setColor(QPalette.ButtonText, QColor("#2C3E50"))
    palette.setColor(QPalette.Highlight, QColor("#2980B9"))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
