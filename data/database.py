"""
SQLite Database Management
"""
import sqlite3
import threading
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from app.config import DATABASE_PATH


class Database:
    """Thread-safe SQLite database manager"""

    _instance: Optional['Database'] = None
    _lock = threading.Lock()

    def __new__(cls, db_path: Path = DATABASE_PATH):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: Path = DATABASE_PATH):
        if self._initialized:
            return

        self.db_path = db_path
        self._thread_local = threading.local()
        self._initialized = True

        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize schema
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local connection"""
        if not hasattr(self._thread_local, 'connection') or self._thread_local.connection is None:
            self._thread_local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False
            )
            self._thread_local.connection.row_factory = sqlite3.Row
            # Enable foreign keys
            self._thread_local.connection.execute("PRAGMA foreign_keys = ON")
        return self._thread_local.connection

    @contextmanager
    def get_cursor(self):
        """Context manager for database cursor with auto-commit"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def _init_schema(self):
        """Initialize database schema"""
        schema = """
        -- Users table
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_user_id INTEGER NOT NULL UNIQUE,
            username TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Fingerprints table
        CREATE TABLE IF NOT EXISTS fingerprints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            image_path TEXT,
            quality_score REAL NOT NULL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_users_device_id ON users(device_user_id);
        CREATE INDEX IF NOT EXISTS idx_fingerprints_user_id ON fingerprints(user_id);
        """

        # Trigger for updated_at (SQLite doesn't support triggers in IF NOT EXISTS)
        trigger_check = """
        SELECT name FROM sqlite_master
        WHERE type='trigger' AND name='update_users_timestamp'
        """

        trigger_create = """
        CREATE TRIGGER update_users_timestamp
        AFTER UPDATE ON users
        BEGIN
            UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
        """

        with self.get_cursor() as cursor:
            cursor.executescript(schema)

            # Check and create trigger
            cursor.execute(trigger_check)
            if cursor.fetchone() is None:
                cursor.execute(trigger_create)

    def close(self):
        """Close thread-local connection"""
        if hasattr(self._thread_local, 'connection') and self._thread_local.connection:
            self._thread_local.connection.close()
            self._thread_local.connection = None


# Singleton instance
db = Database()
