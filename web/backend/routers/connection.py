"""Connection-related API endpoints."""

from fastapi import APIRouter

from models.connection import (
    USBCheckResponse,
    PingRequest,
    PingResponse,
    SSHTestRequest,
    SSHTestResponse,
)
from services.usb_service import USBService
from services.ssh_service import SSHService


router = APIRouter(prefix="/connection", tags=["connection"])


@router.get("/usb/check", response_model=USBCheckResponse)
async def check_usb_connection() -> USBCheckResponse:
    """
    Check USB connections to Jetson Nano.

    Checks for:
    - USB-Ethernet (L4T USB Device Mode at 192.168.55.1)
    - USB Serial devices (ttyUSB, ttyACM, etc.)
    """
    return await USBService.check_all()


@router.post("/ping", response_model=PingResponse)
async def ping_host(request: PingRequest) -> PingResponse:
    """
    Ping a host to check if it's reachable.

    Returns success status, latency in milliseconds, and any error message.
    """
    success, latency, error = await USBService.ping_host(
        request.host,
        request.timeout,
    )

    return PingResponse(
        success=success,
        host=request.host,
        latency_ms=latency,
        error=error,
    )


@router.post("/ssh/test", response_model=SSHTestResponse)
async def test_ssh_connection(request: SSHTestRequest) -> SSHTestResponse:
    """
    Test SSH connection with provided credentials.

    Returns success status and system info if connection is successful.
    """
    return await SSHService.test_connection(request)
