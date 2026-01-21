"""
User Repository - Data access for users
"""
from typing import Optional, List
from datetime import datetime

from core.models import User
from data.database import db


class UserRepository:
    """Repository for User CRUD operations"""

    def create(self, username: str, device_user_id: int) -> User:
        """Create a new user"""
        with db.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (username, device_user_id, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (username, device_user_id, datetime.now(), datetime.now())
            )
            user_id = cursor.lastrowid

        return User(
            id=user_id,
            device_user_id=device_user_id,
            username=username,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        with db.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,)
            )
            row = cursor.fetchone()

        if row:
            return self._row_to_user(row)
        return None

    def get_by_device_id(self, device_user_id: int) -> Optional[User]:
        """Get user by device user ID"""
        with db.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE device_user_id = ?",
                (device_user_id,)
            )
            row = cursor.fetchone()

        if row:
            return self._row_to_user(row)
        return None

    def get_all(self) -> List[User]:
        """Get all users"""
        with db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM users ORDER BY id")
            rows = cursor.fetchall()

        return [self._row_to_user(row) for row in rows]

    def update(self, user: User) -> bool:
        """Update user"""
        with db.get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET username = ?, device_user_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (user.username, user.device_user_id, datetime.now(), user.id)
            )
            return cursor.rowcount > 0

    def delete(self, user_id: int) -> bool:
        """Delete user by ID"""
        with db.get_cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            return cursor.rowcount > 0

    def delete_by_device_id(self, device_user_id: int) -> bool:
        """Delete user by device user ID"""
        with db.get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM users WHERE device_user_id = ?",
                (device_user_id,)
            )
            return cursor.rowcount > 0

    def count(self) -> int:
        """Get total user count"""
        with db.get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0]

    def get_next_device_id(self) -> int:
        """Get next available device user ID"""
        with db.get_cursor() as cursor:
            cursor.execute("SELECT MAX(device_user_id) FROM users")
            result = cursor.fetchone()[0]
            return (result or 0) + 1

    def _row_to_user(self, row) -> User:
        """Convert database row to User object"""
        return User(
            id=row['id'],
            device_user_id=row['device_user_id'],
            username=row['username'],
            created_at=datetime.fromisoformat(row['created_at'])
                       if isinstance(row['created_at'], str)
                       else row['created_at'],
            updated_at=datetime.fromisoformat(row['updated_at'])
                       if isinstance(row['updated_at'], str)
                       else row['updated_at']
        )
