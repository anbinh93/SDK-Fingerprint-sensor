"""
Enrollment Worker - Background enrollment process
"""
import time
from PyQt6.QtCore import QThread, pyqtSignal

from core.services.fingerprint_service import FingerprintService
from core.models import User
from app.config import QUALITY_THRESHOLD


class EnrollmentWorker(QThread):
    """Worker thread for fingerprint enrollment"""

    # Signals
    progress_updated = pyqtSignal(str, int)  # message, percentage
    image_captured = pyqtSignal(bytes, float)  # image, quality
    enrollment_complete = pyqtSignal(object)  # User object
    enrollment_failed = pyqtSignal(str)  # error message

    def __init__(self, service: FingerprintService, username: str,
                 save_bmp: bool = False, timeout_sec: float = 30.0):
        super().__init__()
        self._service = service
        self._username = username
        self._save_bmp = save_bmp
        self._timeout_sec = timeout_sec
        self._running = False
        self._captured_image = None

    def run(self):
        """Enrollment process"""
        self._running = True

        try:
            # Turn on green LED
            self._service.led_on(0x02)  # LED_GREEN

            # Step 1: Wait for finger
            self.progress_updated.emit("Place your finger on the sensor...", 10)

            image = self._wait_for_finger()
            if not self._running:
                return

            if image is None:
                self.enrollment_failed.emit("Timeout: No finger detected")
                return

            # Step 2: Capture image
            self.progress_updated.emit("Capturing fingerprint...", 40)
            self._captured_image = image

            quality = self._service.calculate_quality(image)
            self.image_captured.emit(image, quality)

            if quality < QUALITY_THRESHOLD:
                self.enrollment_failed.emit(f"Image quality too low: {quality:.1f}")
                return

            # Step 3: Enroll
            self.progress_updated.emit("Enrolling fingerprint...", 70)

            user, error = self._service.enroll_user(
                self._username,
                image,
                self._save_bmp
            )

            if user is None:
                self.enrollment_failed.emit(error or "Enrollment failed")
                return

            # Step 4: Success
            self.progress_updated.emit("Enrollment complete!", 100)
            self._service.beep(100)
            self.enrollment_complete.emit(user)

        except Exception as e:
            self.enrollment_failed.emit(str(e))

        finally:
            self._service.led_off()

    def _wait_for_finger(self, check_interval: float = 0.1) -> bytes:
        """Wait for finger on sensor"""
        start_time = time.time()

        while self._running and (time.time() - start_time) < self._timeout_sec:
            result = self._service.capture_image()

            if result.success and result.has_finger:
                return result.image_data

            time.sleep(check_interval)

        return None

    def stop(self):
        """Stop the worker"""
        self._running = False
        if self.isRunning():
            self.quit()
            if not self.wait(2000):
                self.terminate()
                self.wait()
