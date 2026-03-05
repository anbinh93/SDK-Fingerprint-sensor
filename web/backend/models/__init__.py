"""Pydantic models for the API."""

from models.connection import (
    USBStatus,
    USBCheckResponse,
    PingRequest,
    PingResponse,
    SSHTestRequest,
    SSHTestResponse,
    SSHCredentials,
    TerminalSize,
)

__all__ = [
    "USBStatus",
    "USBCheckResponse",
    "PingRequest",
    "PingResponse",
    "SSHTestRequest",
    "SSHTestResponse",
    "SSHCredentials",
    "TerminalSize",
]
