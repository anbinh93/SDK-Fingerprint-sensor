"""
Sensor Worker - Live streaming in background thread
"""
import time
from PyQt6.QtCore import QThread, pyqtSignal

from core.services.fingerprint_service import FingerprintService
from app.config import DEFAULT_FPS


class SensorWorker(QThread):
    """Worker thread for continuous fingerprint capture (live streaming)"""

    # Signals
    frame_captured = pyqtSignal(bytes, float, bool)  # image, quality, has_finger
    error_occurred = pyqtSignal(str)
    fps_updated = pyqtSignal(float)  # actual fps

    def __init__(self, service: FingerprintService, fps: int = DEFAULT_FPS):
        super().__init__()
        self._service = service
        self._fps = fps
        self._running = False
        self._frame_count = 0
        self._start_time = 0

    @property
    def fps(self) -> int:
        return self._fps

    @fps.setter
    def fps(self, value: int):
        self._fps = max(1, min(15, value))  # Clamp to 1-15 FPS

    def run(self):
        """Main worker loop"""
        self._running = True
        self._frame_count = 0
        self._start_time = time.time()

        delay_sec = 1.0 / self._fps

        while self._running:
            try:
                result = self._service.capture_image()

                if result.success:
                    self.frame_captured.emit(
                        result.image_data,
                        result.quality_score,
                        result.has_finger
                    )
                    self._frame_count += 1

                    # Calculate actual FPS every second
                    elapsed = time.time() - self._start_time
                    if elapsed >= 1.0:
                        actual_fps = self._frame_count / elapsed
                        self.fps_updated.emit(actual_fps)
                        self._frame_count = 0
                        self._start_time = time.time()
                else:
                    self.error_occurred.emit(result.error)

            except Exception as e:
                self.error_occurred.emit(str(e))

            # Sleep to maintain target FPS
            time.sleep(delay_sec)

    def stop(self):
        """Stop the worker"""
        self._running = False
        if self.isRunning():
            self.quit()
            if not self.wait(2000):  # Wait up to 2 seconds
                self.terminate()
                self.wait()
