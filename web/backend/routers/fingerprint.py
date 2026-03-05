"""Fingerprint sensor API endpoints."""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from models.connection import SSHCredentials
from services.fingerprint_service import fingerprint_service, SensorStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fingerprint", tags=["fingerprint"])


# ==================== Models ====================

class ConnectRequest(BaseModel):
    """Request to connect to Jetson for fingerprint operations."""
    credentials: SSHCredentials


class ConnectResponse(BaseModel):
    """Response from connect endpoint."""
    success: bool
    error: Optional[str] = None


class StatusResponse(BaseModel):
    """Sensor status response."""
    connected: bool
    jetson_connected: bool
    user_count: int = 0
    compare_level: int = 5
    error: Optional[str] = None


class CaptureResponse(BaseModel):
    """Fingerprint capture response."""
    success: bool
    image_base64: Optional[str] = None
    width: int = 192
    height: int = 192
    quality: float = 0.0
    has_finger: bool = False
    error: Optional[str] = None


class LEDRequest(BaseModel):
    """LED control request."""
    color: int  # 0=off, 1=red, 2=green, 4=blue, 7=white


class MatchResponse(BaseModel):
    """Match fingerprint response."""
    matched: bool
    user_id: int = 0
    error: Optional[str] = None


class AddResponse(BaseModel):
    """Add fingerprint response."""
    success: bool
    user_id: int = 0
    error: Optional[str] = None


class DeleteRequest(BaseModel):
    """Delete fingerprint request."""
    user_id: int  # 0 = delete all


# ==================== REST Endpoints ====================

@router.post("/connect", response_model=ConnectResponse)
async def connect_to_jetson(request: ConnectRequest) -> ConnectResponse:
    """Connect to Jetson Nano for fingerprint operations."""
    logger.info(f"[API] Fingerprint connect request to {request.credentials.host}")
    success, error = await fingerprint_service.connect(request.credentials)
    logger.info(f"[API] Fingerprint connect result: success={success}, error={error}")
    return ConnectResponse(success=success, error=error)


@router.post("/disconnect")
async def disconnect_from_jetson():
    """Disconnect from Jetson Nano."""
    await fingerprint_service.disconnect()
    return {"success": True}


@router.get("/diagnostic")
async def run_diagnostic():
    """Run diagnostic script to check USB, pyusb, and sensor on Jetson."""
    logger.info("[API] Running diagnostic...")
    if not fingerprint_service.is_connected():
        return {"success": False, "error": "Not connected to Jetson", "output": ""}

    output = await fingerprint_service.run_diagnostic()
    return {
        "success": not output.startswith("ERROR"),
        "output": output
    }


@router.get("/status", response_model=StatusResponse)
async def get_sensor_status() -> StatusResponse:
    """Get fingerprint sensor status."""
    logger.info("[API] Get sensor status request")
    jetson_connected = fingerprint_service.is_connected()
    logger.info(f"[API] Jetson connected: {jetson_connected}")

    if not jetson_connected:
        return StatusResponse(
            connected=False,
            jetson_connected=False,
            error="Not connected to Jetson"
        )

    status = await fingerprint_service.get_status()
    logger.info(f"[API] Sensor status: connected={status.connected}, users={status.user_count}, error={status.error}")
    return StatusResponse(
        connected=status.connected,
        jetson_connected=True,
        user_count=status.user_count,
        compare_level=status.compare_level,
        error=status.error,
    )


@router.post("/capture", response_model=CaptureResponse)
async def capture_fingerprint() -> CaptureResponse:
    """Capture a single fingerprint image."""
    if not fingerprint_service.is_connected():
        return CaptureResponse(success=False, error="Not connected to Jetson")

    image = await fingerprint_service.capture_image()
    if not image:
        return CaptureResponse(success=False, error="Capture failed")

    return CaptureResponse(
        success=True,
        image_base64=image.to_base64(),
        width=image.width,
        height=image.height,
        quality=image.quality,
        has_finger=image.has_finger,
    )


@router.post("/led")
async def control_led(request: LEDRequest):
    """Control sensor LED."""
    if not fingerprint_service.is_connected():
        return {"success": False, "error": "Not connected to Jetson"}

    success = await fingerprint_service.led_control(request.color)
    return {"success": success}


@router.post("/match", response_model=MatchResponse)
async def match_fingerprint() -> MatchResponse:
    """Match fingerprint against database."""
    if not fingerprint_service.is_connected():
        return MatchResponse(matched=False, error="Not connected to Jetson")

    matched, user_id = await fingerprint_service.match_fingerprint()
    return MatchResponse(matched=matched, user_id=user_id)


@router.post("/add", response_model=AddResponse)
async def add_fingerprint() -> AddResponse:
    """Add new fingerprint to database."""
    if not fingerprint_service.is_connected():
        return AddResponse(success=False, error="Not connected to Jetson")

    success, user_id = await fingerprint_service.add_user()
    return AddResponse(success=success, user_id=user_id)


@router.post("/delete")
async def delete_fingerprint(request: DeleteRequest):
    """Delete fingerprint(s). Use user_id=0 to delete all."""
    if not fingerprint_service.is_connected():
        return {"success": False, "error": "Not connected to Jetson"}

    success = await fingerprint_service.delete_user(request.user_id)
    return {"success": success}


# ==================== WebSocket for Live Streaming ====================

@router.websocket("/ws/stream")
async def fingerprint_stream(websocket: WebSocket):
    """
    WebSocket endpoint for live fingerprint streaming.

    Protocol:
    1. Client connects
    2. Client sends: {"type": "start", "fps": 5}
    3. Server sends images: {"type": "image", "data": "base64...", "quality": 30.5, "has_finger": true}
    4. Client can send: {"type": "stop"} to pause
    5. Client can send: {"type": "led", "color": 7} to control LED
    """
    await websocket.accept()

    streaming = False
    fps = 5
    stream_task: Optional[asyncio.Task] = None

    async def stream_images():
        nonlocal streaming
        while streaming:
            try:
                image = await fingerprint_service.capture_image()
                if image:
                    await websocket.send_json({
                        "type": "image",
                        "data": image.to_base64(),
                        "width": image.width,
                        "height": image.height,
                        "quality": round(image.quality, 1),
                        "has_finger": image.has_finger,
                    })
                await asyncio.sleep(1.0 / fps)
            except Exception as e:
                logger.error(f"Stream error: {e}")
                streaming = False
                break

    try:
        # Check if connected to Jetson
        if not fingerprint_service.is_connected():
            await websocket.send_json({
                "type": "error",
                "message": "Not connected to Jetson. Connect via /api/fingerprint/connect first."
            })
            await websocket.close()
            return

        await websocket.send_json({"type": "connected"})

        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")

            if msg_type == "start":
                fps = min(max(message.get("fps", 5), 1), 15)  # Clamp 1-15 FPS
                streaming = True
                if stream_task is None or stream_task.done():
                    stream_task = asyncio.create_task(stream_images())
                await websocket.send_json({"type": "started", "fps": fps})

            elif msg_type == "stop":
                streaming = False
                if stream_task:
                    stream_task.cancel()
                    try:
                        await stream_task
                    except asyncio.CancelledError:
                        pass
                await websocket.send_json({"type": "stopped"})

            elif msg_type == "led":
                color = message.get("color", 0)
                await fingerprint_service.led_control(color)

            elif msg_type == "capture_once":
                image = await fingerprint_service.capture_image()
                if image:
                    await websocket.send_json({
                        "type": "image",
                        "data": image.to_base64(),
                        "width": image.width,
                        "height": image.height,
                        "quality": round(image.quality, 1),
                        "has_finger": image.has_finger,
                    })

    except WebSocketDisconnect:
        logger.debug("Fingerprint stream disconnected")
    except Exception as e:
        logger.error(f"Fingerprint WebSocket error: {e}")
    finally:
        streaming = False
        if stream_task:
            stream_task.cancel()
            try:
                await stream_task
            except asyncio.CancelledError:
                pass
