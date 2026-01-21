"""
Matching Worker - Background matching process
"""
import time
from PyQt6.QtCore import QThread, pyqtSignal

from core.services.fingerprint_service import FingerprintService
from core.models import MatchResult
from app.config import MATCH_TIMEOUT_SEC


class MatchingWorker(QThread):
    """Worker thread for fingerprint matching"""

    # Signals
    progress_updated = pyqtSignal(str)  # status message
    image_captured = pyqtSignal(bytes, float)  # image, quality for preview
    match_complete = pyqtSignal(object)  # MatchResult object
    match_failed = pyqtSignal(str)  # error message

    def __init__(self, service: FingerprintService,
                 timeout_sec: float = MATCH_TIMEOUT_SEC):
        super().__init__()
        self._service = service
        self._timeout_sec = timeout_sec
        self._running = False

    def run(self):
        """Matching process"""
        self._running = True

        try:
            # Turn on blue LED
            self._service.led_on(0x04)  # LED_BLUE

            self.progress_updated.emit("Place your finger on the sensor...")

            # Wait for finger and capture preview
            image = self._wait_for_finger()
            if not self._running:
                return

            if image is not None:
                quality = self._service.calculate_quality(image)
                self.image_captured.emit(image, quality)

            self.progress_updated.emit("Matching fingerprint...")

            # Perform matching
            result = self._service.match_fingerprint(self._timeout_sec)

            if result.matched:
                self._service.beep(100)
                self.match_complete.emit(result)
            else:
                self.match_complete.emit(result)

        except Exception as e:
            self.match_failed.emit(str(e))

        finally:
            self._service.led_off()

    def _wait_for_finger(self, check_interval: float = 0.1) -> bytes:
        """Wait for finger and return captured image"""
        timeout = 5.0  # Quick timeout for preview capture
        start_time = time.time()

        while self._running and (time.time() - start_time) < timeout:
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
