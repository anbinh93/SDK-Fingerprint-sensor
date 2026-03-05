"""Terminal service for managing SSH PTY sessions."""

import asyncio
import logging
from typing import Callable, Optional

import asyncssh

from models.connection import SSHCredentials, TerminalSize


logger = logging.getLogger(__name__)


class TerminalSession:
    """Manages a single SSH terminal session."""

    def __init__(
        self,
        credentials: SSHCredentials,
        size: TerminalSize,
        on_data: Callable[[bytes], None],
        on_close: Callable[[], None],
    ):
        self.credentials = credentials
        self.size = size
        self.on_data = on_data
        self.on_close = on_close

        self._conn: Optional[asyncssh.SSHClientConnection] = None
        self._process: Optional[asyncssh.SSHClientProcess] = None
        self._running = False
        self._read_task: Optional[asyncio.Task] = None

    async def start(self) -> Optional[str]:
        """
        Start the terminal session.

        Returns error message if failed, None if successful.
        """
        try:
            conn_options = {
                "host": self.credentials.host,
                "port": self.credentials.port,
                "username": self.credentials.username,
                "known_hosts": None,
            }

            if self.credentials.password:
                conn_options["password"] = self.credentials.password
            if self.credentials.key_path:
                conn_options["client_keys"] = [self.credentials.key_path]

            self._conn = await asyncssh.connect(**conn_options)

            # Start interactive shell with PTY
            self._process = await self._conn.create_process(
                term_type="xterm-256color",
                term_size=(self.size.cols, self.size.rows),
                encoding=None,  # Binary mode for raw PTY data
            )

            self._running = True
            self._read_task = asyncio.create_task(self._read_loop())

            return None

        except asyncssh.PermissionDenied:
            return "Permission denied - check credentials"
        except OSError as e:
            return f"Connection failed: {str(e)}"
        except Exception as e:
            logger.exception("Failed to start terminal session")
            return f"Error: {str(e)}"

    async def _read_loop(self) -> None:
        """Read data from SSH and send to WebSocket."""
        try:
            while self._running and self._process:
                data = await self._process.stdout.read(4096)
                if not data:
                    break
                self.on_data(data)
        except asyncssh.BreakReceived:
            pass
        except Exception as e:
            logger.debug(f"Read loop ended: {e}")
        finally:
            self._running = False
            self.on_close()

    async def write(self, data: bytes) -> None:
        """Write data to the terminal."""
        if self._process and self._running:
            try:
                self._process.stdin.write(data)
            except Exception as e:
                logger.error(f"Write error: {e}")

    async def resize(self, size: TerminalSize) -> None:
        """Resize the terminal."""
        self.size = size
        if self._process and self._running:
            try:
                self._process.change_terminal_size(size.cols, size.rows)
            except Exception as e:
                logger.error(f"Resize error: {e}")

    async def close(self) -> None:
        """Close the terminal session with proper cleanup and timeouts."""
        self._running = False
        cleanup_errors = []

        # Cancel read task
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                cleanup_errors.append(f"Read task cleanup error: {e}")

        # Close process with timeout
        if self._process:
            try:
                self._process.close()
                await asyncio.wait_for(self._process.wait_closed(), timeout=5.0)
            except asyncio.TimeoutError:
                cleanup_errors.append("Process close timed out")
                logger.warning("Process close timed out for session")
            except Exception as e:
                cleanup_errors.append(f"Process close error: {e}")
                logger.error(f"Failed to close process: {e}")

        # Close connection with timeout
        if self._conn:
            try:
                self._conn.close()
                await asyncio.wait_for(self._conn.wait_closed(), timeout=5.0)
            except asyncio.TimeoutError:
                cleanup_errors.append("Connection close timed out")
                logger.warning("Connection close timed out for session")
            except Exception as e:
                cleanup_errors.append(f"Connection close error: {e}")
                logger.error(f"Failed to close connection: {e}")

        if cleanup_errors:
            logger.warning(f"Terminal session cleanup had errors: {'; '.join(cleanup_errors)}")


class TerminalService:
    """Service for managing terminal sessions."""

    def __init__(self):
        self._sessions: dict[str, TerminalSession] = {}

    async def create_session(
        self,
        session_id: str,
        credentials: SSHCredentials,
        size: TerminalSize,
        on_data: Callable[[bytes], None],
        on_close: Callable[[], None],
    ) -> Optional[str]:
        """
        Create a new terminal session.

        Returns error message if failed, None if successful.
        """
        session = TerminalSession(credentials, size, on_data, on_close)
        error = await session.start()

        if error:
            return error

        self._sessions[session_id] = session
        return None

    def get_session(self, session_id: str) -> Optional[TerminalSession]:
        """Get a terminal session by ID."""
        return self._sessions.get(session_id)

    async def close_session(self, session_id: str) -> None:
        """Close and remove a terminal session."""
        session = self._sessions.pop(session_id, None)
        if session:
            await session.close()

    async def close_all(self) -> None:
        """Close all terminal sessions."""
        for session_id in list(self._sessions.keys()):
            await self.close_session(session_id)


# Global terminal service instance
terminal_service = TerminalService()
