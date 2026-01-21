"""
Fingerprint Service - Main orchestration service
"""
import threading
import math
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

from core.models import User, Fingerprint, MatchResult, CaptureResult
from core.interfaces import MatchingEngine
from core.services.database_service import DatabaseService
from core.services.fea_service import FEAService
from app.config import (
    IMAGE_WIDTH, IMAGE_HEIGHT, IMAGE_SIZE,
    QUALITY_THRESHOLD, IMAGES_DIR
)


class ThreadSafeSensor:
    """Thread-safe wrapper for FingerprintReader"""

    def __init__(self, sensor):
        self._sensor = sensor
        self._lock = threading.Lock()

    @property
    def sensor(self):
        return self._sensor

    def capture_image(self) -> Optional[bytes]:
        with self._lock:
            return self._sensor.capture_image()

    def check_finger(self) -> bool:
        with self._lock:
            return self._sensor.check_finger()

    def add_user(self, user_id: int = None) -> Tuple[bool, int]:
        with self._lock:
            return self._sensor.add_user(user_id)

    def match_fingerprint(self, timeout_sec: float = 5.0) -> Tuple[bool, int]:
        with self._lock:
            return self._sensor.match_fingerprint(timeout_sec)

    def delete_user(self, user_id: int) -> bool:
        with self._lock:
            return self._sensor.delete_user(user_id)

    def delete_all(self) -> bool:
        with self._lock:
            return self._sensor.delete_all()

    def get_user_count(self) -> int:
        with self._lock:
            return self._sensor.get_user_count()

    def led_on(self, color: int) -> bool:
        with self._lock:
            return self._sensor.led_on(color)

    def led_off(self) -> bool:
        with self._lock:
            return self._sensor.led_off()

    def beep(self, duration_ms: int = 100) -> bool:
        with self._lock:
            return self._sensor.beep(duration_ms)


class FingerprintService:
    """Main service orchestrating fingerprint operations"""

    def __init__(self, sensor, matching_engine: Optional[MatchingEngine] = None):
        """
        Args:
            sensor: FingerprintReader instance
            matching_engine: Optional MatchingEngine (default: DeviceMatchingEngine)
        """
        self._sensor = ThreadSafeSensor(sensor)
        self._db_service = DatabaseService()
        self._fea_service = FEAService()

        # Set up matching engine
        if matching_engine:
            self._matching_engine = matching_engine
        else:
            from core.services.matching_engine import DeviceMatchingEngine
            self._matching_engine = DeviceMatchingEngine(sensor)

    @property
    def sensor(self) -> ThreadSafeSensor:
        return self._sensor

    @property
    def database(self) -> DatabaseService:
        return self._db_service

    @property
    def fea(self) -> FEAService:
        return self._fea_service

    @property
    def matching_engine(self) -> MatchingEngine:
        return self._matching_engine

    def set_matching_engine(self, engine: MatchingEngine):
        """Switch matching engine"""
        self._matching_engine = engine

    # ==================== Image Operations ====================

    def capture_image(self) -> CaptureResult:
        """Capture fingerprint image"""
        try:
            image = self._sensor.capture_image()
            if image is None:
                return CaptureResult(
                    success=False,
                    error="Failed to capture image"
                )

            quality = self.calculate_quality(image)
            has_finger = quality > QUALITY_THRESHOLD

            return CaptureResult(
                success=True,
                image_data=image,
                quality_score=quality,
                has_finger=has_finger
            )

        except Exception as e:
            return CaptureResult(
                success=False,
                error=str(e)
            )

    @staticmethod
    def calculate_quality(image: bytes) -> float:
        """Calculate image quality (standard deviation)"""
        if not image or len(image) < 1000:
            return 0.0

        avg = sum(image) / len(image)
        variance = sum((x - avg) ** 2 for x in image) / len(image)
        return math.sqrt(variance)

    @staticmethod
    def has_fingerprint(image: bytes) -> bool:
        """Check if image contains a valid fingerprint"""
        quality = FingerprintService.calculate_quality(image)
        return quality > QUALITY_THRESHOLD

    def save_image_bmp(self, image: bytes, filepath: str) -> bool:
        """Save image as BMP file using Pillow"""
        try:
            from PIL import Image
            import numpy as np
            
            # Convert bytes to numpy array and reshape
            img_array = np.frombuffer(image, dtype=np.uint8).reshape((IMAGE_HEIGHT, IMAGE_WIDTH))
            
            # Create PIL Image and save
            img = Image.fromarray(img_array, mode='L')
            img.save(filepath)
            
            return True

        except Exception as e:
            print(f"BMP save error: {e}")
            return False

    # ==================== Enrollment ====================

    def enroll_user(self, username: str, image: Optional[bytes] = None,
                    save_bmp: bool = False) -> Tuple[Optional[User], str]:
        """
        Complete user enrollment flow.

        Args:
            username: Username for the new user
            image: Optional pre-captured image
            save_bmp: Whether to save image as BMP

        Returns:
            (User object, error_message)
        """
        try:
            # Get next device user ID
            device_user_id = self._db_service.get_next_device_id()

            # Enroll on device
            success, error_msg = self._matching_engine.enroll(image or b'', device_user_id)
            if not success:
                return None, f"Device enrollment failed: {error_msg}"

            # Create user in database
            user = self._db_service.add_user(username, device_user_id)

            # Save image if requested
            image_path = None
            if save_bmp and image:
                image_path = str(IMAGES_DIR / f"user_{device_user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bmp")
                self.save_image_bmp(image, image_path)

            # Record fingerprint
            quality = self.calculate_quality(image) if image else 0.0
            self._db_service.add_fingerprint(user.id, image_path, quality)

            return user, ""

        except Exception as e:
            return None, str(e)

    # ==================== Matching ====================

    def match_fingerprint(self, timeout_sec: float = 10.0) -> MatchResult:
        """
        Match fingerprint against enrolled users.

        Returns:
            MatchResult with matched user info
        """
        result = self._matching_engine.match(b'', timeout_sec)

        # If matched, fetch user from database
        if result.matched and result.user_id > 0:
            user = self._db_service.get_user_by_device_id(result.user_id)
            result.user = user

        return result

    # ==================== User Management ====================

    def delete_user(self, user_id: int) -> Tuple[bool, str]:
        """Delete user from database and device"""
        try:
            user = self._db_service.get_user(user_id)
            if not user:
                return False, "User not found"

            # Delete from device
            self._matching_engine.delete(user.device_user_id)

            # Delete from database
            self._db_service.delete_user(user_id)

            return True, ""

        except Exception as e:
            return False, str(e)

    def delete_all_users(self) -> Tuple[bool, str]:
        """Delete all users"""
        try:
            # Delete from device
            self._matching_engine.delete_all()

            # Delete from database
            self._db_service.delete_all_data()

            return True, ""

        except Exception as e:
            return False, str(e)

    # ==================== Device Control ====================

    def led_on(self, color: int) -> bool:
        return self._sensor.led_on(color)

    def led_off(self) -> bool:
        return self._sensor.led_off()

    def beep(self, duration_ms: int = 100) -> bool:
        return self._sensor.beep(duration_ms)

    def get_device_user_count(self) -> int:
        return self._sensor.get_user_count()
