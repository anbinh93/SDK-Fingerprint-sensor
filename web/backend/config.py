"""Configuration settings for the Jetson Nano Remote Web App."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""

    # API settings
    api_prefix: str = "/api"
    debug: bool = True

    # Default Jetson Nano connection settings
    default_jetson_ip: str = "192.168.55.1"  # USB-Ethernet default
    default_ssh_port: int = 22
    default_username: str = "jetson"

    # USB detection settings
    usb_ethernet_ip: str = "192.168.55.1"
    usb_serial_patterns: list[str] = [
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
        "/dev/cu.usbserial*",
        "/dev/cu.usbmodem*",
    ]

    # WebSocket settings
    ws_heartbeat_interval: int = 30

    # SSH settings
    ssh_timeout: float = 10.0
    ssh_known_hosts: Optional[str] = None

    class Config:
        env_prefix = "JETSON_"


settings = Settings()
