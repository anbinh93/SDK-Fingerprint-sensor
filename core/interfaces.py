"""
Abstract Interfaces
"""
from abc import ABC, abstractmethod
from typing import Tuple, Optional, List
from .models import MatchResult


class MatchingEngine(ABC):
    """Abstract matching engine interface for extensibility"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Engine identifier"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if engine is ready to use"""
        pass

    @abstractmethod
    def enroll(self, image: bytes, user_id: int) -> Tuple[bool, str]:
        """
        Enroll fingerprint.
        Returns (success, error_message)
        """
        pass

    @abstractmethod
    def match(self, image: bytes, timeout_sec: float = 10.0) -> MatchResult:
        """
        Match fingerprint against enrolled templates.
        Returns MatchResult with matched user info
        """
        pass

    @abstractmethod
    def verify(self, image: bytes, user_id: int) -> Tuple[bool, float]:
        """
        Verify fingerprint against specific user (1:1 matching).
        Returns (matched, confidence)
        """
        pass

    @abstractmethod
    def delete(self, user_id: int) -> bool:
        """Delete enrollment for user"""
        pass

    @abstractmethod
    def delete_all(self) -> bool:
        """Delete all enrollments"""
        pass

    @abstractmethod
    def get_enrolled_count(self) -> int:
        """Get number of enrolled users"""
        pass


class ImageProcessor(ABC):
    """Abstract image processor for preprocessing"""

    @abstractmethod
    def enhance(self, image: bytes) -> bytes:
        """Enhance image quality"""
        pass

    @abstractmethod
    def extract_features(self, image: bytes) -> Optional[bytes]:
        """Extract feature vector from image"""
        pass

    @abstractmethod
    def calculate_quality(self, image: bytes) -> float:
        """Calculate quality score (StdDev)"""
        pass
