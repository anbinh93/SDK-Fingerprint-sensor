"""
Domain Models
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
import base64
import json


@dataclass
class User:
    """User entity"""
    id: Optional[int] = None
    device_user_id: int = 0  # Device hardware ID (1-1000)
    username: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "device_user_id": self.device_user_id,
            "username": self.username,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class Fingerprint:
    """Fingerprint entity"""
    id: Optional[int] = None
    user_id: int = 0
    image_path: Optional[str] = None  # Path to saved BMP/PNG
    quality_score: float = 0.0  # StdDev quality metric
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "image_path": self.image_path,
            "quality_score": self.quality_score,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class FEAFile:
    """FEA format container for import/export"""
    version: str = "1.0"
    user_id: int = 0
    username: str = ""
    image_data: bytes = field(default_factory=bytes)
    width: int = 192
    height: int = 192
    quality_score: float = 0.0
    captured_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize to JSON string"""
        return json.dumps({
            "version": self.version,
            "format": "FEA",
            "user": {
                "id": self.user_id,
                "username": self.username
            },
            "fingerprint": {
                "image": base64.b64encode(self.image_data).decode('utf-8'),
                "width": self.width,
                "height": self.height,
                "depth": 8,
                "format": "grayscale"
            },
            "quality": {
                "score": self.quality_score,
                "metric": "stddev"
            },
            "metadata": {
                "captured_at": self.captured_at.isoformat(),
                **self.metadata
            }
        }, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'FEAFile':
        """Deserialize from JSON string"""
        data = json.loads(json_str)

        return cls(
            version=data.get("version", "1.0"),
            user_id=data.get("user", {}).get("id", 0),
            username=data.get("user", {}).get("username", ""),
            image_data=base64.b64decode(data.get("fingerprint", {}).get("image", "")),
            width=data.get("fingerprint", {}).get("width", 192),
            height=data.get("fingerprint", {}).get("height", 192),
            quality_score=data.get("quality", {}).get("score", 0.0),
            captured_at=datetime.fromisoformat(
                data.get("metadata", {}).get("captured_at", datetime.now().isoformat())
            ),
            metadata={k: v for k, v in data.get("metadata", {}).items()
                     if k != "captured_at"}
        )


@dataclass
class MatchResult:
    """Result of fingerprint matching"""
    matched: bool = False
    user_id: int = 0
    user: Optional[User] = None
    confidence: float = 0.0
    engine_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "matched": self.matched,
            "user_id": self.user_id,
            "user": self.user.to_dict() if self.user else None,
            "confidence": self.confidence,
            "engine_name": self.engine_name
        }


@dataclass
class CaptureResult:
    """Result of image capture"""
    success: bool = False
    image_data: bytes = field(default_factory=bytes)
    quality_score: float = 0.0
    has_finger: bool = False
    error: str = ""
