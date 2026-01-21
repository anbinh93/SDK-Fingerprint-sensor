"""
Database Service - High-level database operations
"""
from typing import Optional, List

from core.models import User, Fingerprint
from data.repositories import UserRepository, FingerprintRepository


class DatabaseService:
    """High-level service for database operations"""

    def __init__(self):
        self._user_repo = UserRepository()
        self._fp_repo = FingerprintRepository()

    # ==================== User Operations ====================

    def add_user(self, username: str, device_user_id: int) -> User:
        """Add a new user"""
        return self._user_repo.create(username, device_user_id)

    def get_user(self, user_id: int) -> Optional[User]:
        """Get user by database ID"""
        return self._user_repo.get_by_id(user_id)

    def get_user_by_device_id(self, device_user_id: int) -> Optional[User]:
        """Get user by device user ID"""
        return self._user_repo.get_by_device_id(device_user_id)

    def get_all_users(self) -> List[User]:
        """Get all users"""
        return self._user_repo.get_all()

    def update_user(self, user: User) -> bool:
        """Update user"""
        return self._user_repo.update(user)

    def delete_user(self, user_id: int) -> bool:
        """Delete user and their fingerprints"""
        return self._user_repo.delete(user_id)

    def get_user_count(self) -> int:
        """Get total user count"""
        return self._user_repo.count()

    def get_next_device_id(self) -> int:
        """Get next available device user ID"""
        return self._user_repo.get_next_device_id()

    # ==================== Fingerprint Operations ====================

    def add_fingerprint(self, user_id: int, image_path: Optional[str] = None,
                        quality_score: float = 0.0) -> Fingerprint:
        """Add fingerprint record for user"""
        return self._fp_repo.create(user_id, image_path, quality_score)

    def get_fingerprints(self, user_id: int) -> List[Fingerprint]:
        """Get all fingerprints for a user"""
        return self._fp_repo.get_by_user_id(user_id)

    def get_all_fingerprints(self) -> List[Fingerprint]:
        """Get all fingerprints"""
        return self._fp_repo.get_all()

    def update_fingerprint(self, fingerprint: Fingerprint) -> bool:
        """Update fingerprint record"""
        return self._fp_repo.update(fingerprint)

    def delete_fingerprint(self, fp_id: int) -> bool:
        """Delete fingerprint by ID"""
        return self._fp_repo.delete(fp_id)

    def get_fingerprint_count(self, user_id: Optional[int] = None) -> int:
        """Get fingerprint count (for user if specified)"""
        if user_id is not None:
            return self._fp_repo.count_by_user(user_id)
        return self._fp_repo.count()

    # ==================== Combined Operations ====================

    def get_user_with_fingerprints(self, user_id: int) -> Optional[dict]:
        """Get user with their fingerprints"""
        user = self._user_repo.get_by_id(user_id)
        if user:
            fingerprints = self._fp_repo.get_by_user_id(user_id)
            return {
                'user': user,
                'fingerprints': fingerprints
            }
        return None

    def delete_all_data(self) -> bool:
        """Delete all users and fingerprints"""
        try:
            users = self._user_repo.get_all()
            for user in users:
                self._user_repo.delete(user.id)
            return True
        except Exception:
            return False
