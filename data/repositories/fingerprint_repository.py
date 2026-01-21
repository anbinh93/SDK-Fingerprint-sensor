"""
Fingerprint Repository - Data access for fingerprints
"""
from typing import Optional, List
from datetime import datetime

from core.models import Fingerprint
from data.database import db


class FingerprintRepository:
    """Repository for Fingerprint CRUD operations"""

    def create(self, user_id: int, image_path: Optional[str] = None,
               quality_score: float = 0.0) -> Fingerprint:
        """Create a new fingerprint record"""
        with db.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO fingerprints (user_id, image_path, quality_score, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, image_path, quality_score, datetime.now())
            )
            fp_id = cursor.lastrowid

        return Fingerprint(
            id=fp_id,
            user_id=user_id,
            image_path=image_path,
            quality_score=quality_score,
            created_at=datetime.now()
        )

    def get_by_id(self, fp_id: int) -> Optional[Fingerprint]:
        """Get fingerprint by ID"""
        with db.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM fingerprints WHERE id = ?",
                (fp_id,)
            )
            row = cursor.fetchone()

        if row:
            return self._row_to_fingerprint(row)
        return None

    def get_by_user_id(self, user_id: int) -> List[Fingerprint]:
        """Get all fingerprints for a user"""
        with db.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM fingerprints WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            )
            rows = cursor.fetchall()

        return [self._row_to_fingerprint(row) for row in rows]

    def get_all(self) -> List[Fingerprint]:
        """Get all fingerprints"""
        with db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM fingerprints ORDER BY id")
            rows = cursor.fetchall()

        return [self._row_to_fingerprint(row) for row in rows]

    def update(self, fingerprint: Fingerprint) -> bool:
        """Update fingerprint record"""
        with db.get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE fingerprints
                SET image_path = ?, quality_score = ?
                WHERE id = ?
                """,
                (fingerprint.image_path, fingerprint.quality_score, fingerprint.id)
            )
            return cursor.rowcount > 0

    def delete(self, fp_id: int) -> bool:
        """Delete fingerprint by ID"""
        with db.get_cursor() as cursor:
            cursor.execute("DELETE FROM fingerprints WHERE id = ?", (fp_id,))
            return cursor.rowcount > 0

    def delete_by_user_id(self, user_id: int) -> int:
        """Delete all fingerprints for a user. Returns count deleted."""
        with db.get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM fingerprints WHERE user_id = ?",
                (user_id,)
            )
            return cursor.rowcount

    def count(self) -> int:
        """Get total fingerprint count"""
        with db.get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM fingerprints")
            return cursor.fetchone()[0]

    def count_by_user(self, user_id: int) -> int:
        """Get fingerprint count for a user"""
        with db.get_cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM fingerprints WHERE user_id = ?",
                (user_id,)
            )
            return cursor.fetchone()[0]

    def _row_to_fingerprint(self, row) -> Fingerprint:
        """Convert database row to Fingerprint object"""
        return Fingerprint(
            id=row['id'],
            user_id=row['user_id'],
            image_path=row['image_path'],
            quality_score=row['quality_score'],
            created_at=datetime.fromisoformat(row['created_at'])
                       if isinstance(row['created_at'], str)
                       else row['created_at']
        )
