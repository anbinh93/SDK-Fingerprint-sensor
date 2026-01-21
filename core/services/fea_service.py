"""
FEA File Service - Import/Export fingerprint data
"""
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

from core.models import FEAFile, User
from app.config import FEA_VERSION, IMAGE_WIDTH, IMAGE_HEIGHT


class FEAService:
    """Service for FEA file operations"""

    def export_to_fea(self, user: User, image: bytes, output_path: str,
                      quality_score: float = 0.0,
                      metadata: Optional[dict] = None) -> bool:
        """
        Export fingerprint to FEA file.

        Args:
            user: User object
            image: Raw fingerprint image bytes
            output_path: Path to save FEA file
            quality_score: Image quality score
            metadata: Additional metadata

        Returns:
            True if successful
        """
        try:
            fea = FEAFile(
                version=FEA_VERSION,
                user_id=user.device_user_id,
                username=user.username,
                image_data=image,
                width=IMAGE_WIDTH,
                height=IMAGE_HEIGHT,
                quality_score=quality_score,
                captured_at=datetime.now(),
                metadata=metadata or {
                    "device": "USB Fingerprint Reader 0483:5720",
                    "sdk_version": "1.0"
                }
            )

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(fea.to_json())

            return True

        except Exception as e:
            print(f"FEA export error: {e}")
            return False

    def import_from_fea(self, fea_path: str) -> Optional[FEAFile]:
        """
        Import fingerprint from FEA file.

        Args:
            fea_path: Path to FEA file

        Returns:
            FEAFile object or None if failed
        """
        try:
            with open(fea_path, 'r', encoding='utf-8') as f:
                json_str = f.read()

            return FEAFile.from_json(json_str)

        except Exception as e:
            print(f"FEA import error: {e}")
            return None

    def validate_fea(self, fea_path: str) -> tuple[bool, str]:
        """
        Validate FEA file format.

        Args:
            fea_path: Path to FEA file

        Returns:
            (is_valid, error_message)
        """
        try:
            with open(fea_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Check required fields
            required_fields = ['version', 'user', 'fingerprint', 'quality']
            for field in required_fields:
                if field not in data:
                    return False, f"Missing required field: {field}"

            # Check version
            if data.get('version') != FEA_VERSION:
                return False, f"Unsupported version: {data.get('version')}"

            # Check fingerprint data
            fp_data = data.get('fingerprint', {})
            if 'image' not in fp_data:
                return False, "Missing fingerprint image data"

            if fp_data.get('width') != IMAGE_WIDTH or fp_data.get('height') != IMAGE_HEIGHT:
                return False, f"Invalid image dimensions: expected {IMAGE_WIDTH}x{IMAGE_HEIGHT}"

            return True, ""

        except json.JSONDecodeError as e:
            return False, f"Invalid JSON format: {e}"
        except Exception as e:
            return False, str(e)

    def get_fea_info(self, fea_path: str) -> Optional[dict]:
        """
        Get basic info from FEA file without loading full image.

        Returns:
            Dict with user info, quality, etc.
        """
        try:
            with open(fea_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return {
                'version': data.get('version'),
                'user_id': data.get('user', {}).get('id'),
                'username': data.get('user', {}).get('username'),
                'quality_score': data.get('quality', {}).get('score'),
                'width': data.get('fingerprint', {}).get('width'),
                'height': data.get('fingerprint', {}).get('height'),
                'captured_at': data.get('metadata', {}).get('captured_at'),
                'file_path': fea_path
            }

        except Exception:
            return None
