"""WebSocket terminal handler for SSH sessions."""

import asyncio
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from models.connection import SSHCredentials, TerminalSize
from services.terminal_service import terminal_service


logger = logging.getLogger(__name__)

router = APIRouter(tags=["terminal"])


class TerminalWebSocketHandler:
    """Handler for a single WebSocket terminal connection."""

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.session_id: Optional[str] = None
        self._closed = False

    async def handle(self) -> None:
        """Main handler for the WebSocket connection."""
        await self.websocket.accept()

        try:
            # Wait for connection message with credentials
            init_data = await self.websocket.receive_json()

            if init_data.get("type") != "connect":
                await self._send_error("First message must be 'connect' type")
                return

            # Parse credentials and size
            try:
                credentials = SSHCredentials(**init_data.get("credentials", {}))
                size_data = init_data.get("size", {})
                size = TerminalSize(
                    rows=size_data.get("rows", 24),
                    cols=size_data.get("cols", 80),
                )
            except Exception as e:
                await self._send_error(f"Invalid credentials: {str(e)}")
                return

            # Create terminal session
            self.session_id = str(uuid.uuid4())
            error = await terminal_service.create_session(
                session_id=self.session_id,
                credentials=credentials,
                size=size,
                on_data=self._on_terminal_data,
                on_close=self._on_terminal_close,
            )

            if error:
                await self._send_error(error)
                return

            await self._send_message({"type": "connected", "sessionId": self.session_id})

            # Handle incoming messages
            await self._message_loop()

        except WebSocketDisconnect:
            logger.debug("WebSocket disconnected")
        except Exception as e:
            logger.exception("WebSocket error")
            await self._send_error(str(e))
        finally:
            await self._cleanup()

    async def _message_loop(self) -> None:
        """Process incoming WebSocket messages."""
        while not self._closed:
            try:
                message = await self.websocket.receive()

                if message["type"] == "websocket.disconnect":
                    break

                # Handle binary data (terminal input)
                if "bytes" in message:
                    session = terminal_service.get_session(self.session_id)
                    if session:
                        await session.write(message["bytes"])
                    continue

                # Handle text messages (commands)
                if "text" in message:
                    data = json.loads(message["text"])
                    await self._handle_command(data)

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received")
            except Exception as e:
                logger.error(f"Message handling error: {e}")

    async def _handle_command(self, data: dict) -> None:
        """Handle control commands from the client."""
        cmd_type = data.get("type")
        session = terminal_service.get_session(self.session_id)

        if not session:
            return

        if cmd_type == "resize":
            size = TerminalSize(
                rows=data.get("rows", 24),
                cols=data.get("cols", 80),
            )
            await session.resize(size)

        elif cmd_type == "input":
            # Text input (alternative to binary)
            text = data.get("data", "")
            if text:
                await session.write(text.encode("utf-8"))

        elif cmd_type == "disconnect":
            self._closed = True

    def _on_terminal_data(self, data: bytes) -> None:
        """Callback when terminal produces output."""
        if not self._closed:
            asyncio.create_task(self._send_binary(data))

    def _on_terminal_close(self) -> None:
        """Callback when terminal session closes."""
        if not self._closed:
            self._closed = True
            asyncio.create_task(self._send_message({"type": "disconnected"}))

    async def _send_message(self, data: dict) -> None:
        """Send JSON message to client."""
        try:
            if not self._closed:
                await self.websocket.send_json(data)
        except Exception:
            pass

    async def _send_binary(self, data: bytes) -> None:
        """Send binary data to client."""
        try:
            if not self._closed:
                await self.websocket.send_bytes(data)
        except Exception:
            pass

    async def _send_error(self, message: str) -> None:
        """Send error message to client."""
        await self._send_message({"type": "error", "message": message})

    async def _cleanup(self) -> None:
        """Clean up resources."""
        self._closed = True
        if self.session_id:
            await terminal_service.close_session(self.session_id)


@router.websocket("/ws/terminal")
async def terminal_websocket(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for terminal sessions.

    Protocol:
    1. Client connects to WebSocket
    2. Client sends: {"type": "connect", "credentials": {...}, "size": {"rows": 24, "cols": 80}}
    3. Server responds: {"type": "connected", "sessionId": "..."} or {"type": "error", "message": "..."}
    4. Client sends terminal input as binary data or {"type": "input", "data": "..."}
    5. Server sends terminal output as binary data
    6. Client can send: {"type": "resize", "rows": N, "cols": M}
    7. Either side can close the connection
    """
    handler = TerminalWebSocketHandler(websocket)
    await handler.handle()
