"""USB detection service for Jetson Nano connections."""

import asyncio
import glob
import platform
import subprocess
from typing import Optional

from config import settings
from models.connection import USBStatus, USBCheckResponse


class USBService:
    """Service for detecting USB connections to Jetson Nano."""

    @staticmethod
    async def check_usb_ethernet() -> USBStatus:
        """Check if Jetson Nano is connected via USB-Ethernet (L4T USB Device Mode)."""
        ip = settings.usb_ethernet_ip

        try:
            # Try to ping the USB-Ethernet IP
            if platform.system() == "Darwin":  # macOS
                cmd = ["ping", "-c", "1", "-W", "1000", ip]
            else:  # Linux
                cmd = ["ping", "-c", "1", "-W", "1", ip]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=3.0)

            if process.returncode == 0:
                return USBStatus(
                    connected=True,
                    device="USB-Ethernet (L4T)",
                    ip_address=ip,
                    details="Jetson Nano USB Device Mode detected",
                )
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            return USBStatus(
                connected=False,
                details=f"Error checking USB-Ethernet: {str(e)}",
            )

        return USBStatus(
            connected=False,
            details="USB-Ethernet not detected",
        )

    @staticmethod
    async def check_usb_serial() -> USBStatus:
        """Check if Jetson Nano is connected via USB Serial."""
        detected_devices = []

        for pattern in settings.usb_serial_patterns:
            devices = glob.glob(pattern)
            detected_devices.extend(devices)

        if detected_devices:
            # Return the first detected device
            device = detected_devices[0]
            return USBStatus(
                connected=True,
                device=device,
                details=f"USB Serial device(s) found: {', '.join(detected_devices)}",
            )

        return USBStatus(
            connected=False,
            details="No USB Serial devices found",
        )

    @classmethod
    async def check_all(cls) -> USBCheckResponse:
        """Check all USB connection types."""
        # Run checks in parallel
        usb_ethernet, usb_serial = await asyncio.gather(
            cls.check_usb_ethernet(),
            cls.check_usb_serial(),
        )

        return USBCheckResponse(
            usb_ethernet=usb_ethernet,
            usb_serial=usb_serial,
            any_connected=usb_ethernet.connected or usb_serial.connected,
        )

    @staticmethod
    async def ping_host(host: str, timeout: float = 5.0) -> tuple[bool, Optional[float], Optional[str]]:
        """
        Ping a host and return success status, latency, and error message.

        Returns:
            Tuple of (success, latency_ms, error_message)
        """
        try:
            if platform.system() == "Darwin":  # macOS
                cmd = ["ping", "-c", "1", "-W", str(int(timeout * 1000)), host]
            else:  # Linux
                cmd = ["ping", "-c", "1", "-W", str(int(timeout)), host]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout + 1,
            )

            if process.returncode == 0:
                # Parse latency from output
                output = stdout.decode()
                latency = None

                # Try to extract time from ping output
                for line in output.split("\n"):
                    if "time=" in line:
                        try:
                            time_part = line.split("time=")[1].split()[0]
                            latency = float(time_part.replace("ms", ""))
                        except (IndexError, ValueError):
                            pass
                        break

                return True, latency, None
            else:
                return False, None, f"Host unreachable: {stderr.decode().strip()}"

        except asyncio.TimeoutError:
            return False, None, "Ping timeout"
        except Exception as e:
            return False, None, str(e)
