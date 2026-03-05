"""Pydantic models for connection-related API endpoints."""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class ConnectionType(str, Enum):
    """Type of connection to Jetson Nano."""
    USB_ETHERNET = "usb_ethernet"
    USB_SERIAL = "usb_serial"
    SSH = "ssh"


class USBStatus(BaseModel):
    """Status of a USB connection type."""
    connected: bool
    device: Optional[str] = None
    ip_address: Optional[str] = None
    details: Optional[str] = None


class USBCheckResponse(BaseModel):
    """Response for USB check endpoint."""
    usb_ethernet: USBStatus
    usb_serial: USBStatus
    any_connected: bool


class PingRequest(BaseModel):
    """Request to ping a host."""
    host: str = Field(..., description="IP address or hostname to ping")
    timeout: float = Field(default=5.0, description="Timeout in seconds")


class PingResponse(BaseModel):
    """Response from ping endpoint."""
    success: bool
    host: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class SSHCredentials(BaseModel):
    """SSH connection credentials."""
    host: str = Field(..., description="IP address or hostname")
    port: int = Field(default=22, description="SSH port")
    username: str = Field(..., description="SSH username")
    password: Optional[str] = Field(default=None, description="SSH password")
    key_path: Optional[str] = Field(default=None, description="Path to SSH private key")


class SSHTestRequest(SSHCredentials):
    """Request to test SSH connection."""
    pass


class SSHTestResponse(BaseModel):
    """Response from SSH test endpoint."""
    success: bool
    host: str
    username: str
    error: Optional[str] = None
    system_info: Optional[str] = None


class TerminalSize(BaseModel):
    """Terminal dimensions."""
    rows: int = Field(default=24, ge=1, le=5000)
    cols: int = Field(default=80, ge=1, le=5000)


class TerminalConnectRequest(BaseModel):
    """Request to connect terminal via WebSocket."""
    credentials: SSHCredentials
    size: TerminalSize = Field(default_factory=TerminalSize)
