"""SSH connection service for Jetson Nano."""

import asyncio
from typing import Optional, Tuple

import asyncssh

from config import settings
from models.connection import SSHCredentials, SSHTestResponse


class SSHService:
    """Service for SSH connections to Jetson Nano."""

    @staticmethod
    async def test_connection(credentials: SSHCredentials) -> SSHTestResponse:
        """
        Test SSH connection with provided credentials.

        Returns SSHTestResponse with connection status and system info if successful.
        """
        try:
            # Build connection options
            conn_options = {
                "host": credentials.host,
                "port": credentials.port,
                "username": credentials.username,
                "known_hosts": None,  # Disable host key checking for ease of use
            }

            if credentials.password:
                conn_options["password"] = credentials.password
            if credentials.key_path:
                conn_options["client_keys"] = [credentials.key_path]

            async with asyncssh.connect(**conn_options) as conn:
                # Get system info to verify connection
                result = await conn.run("uname -a", check=True)
                system_info = result.stdout.strip() if result.stdout else None

                return SSHTestResponse(
                    success=True,
                    host=credentials.host,
                    username=credentials.username,
                    system_info=system_info,
                )

        except asyncssh.DisconnectError as e:
            return SSHTestResponse(
                success=False,
                host=credentials.host,
                username=credentials.username,
                error=f"Disconnected: {str(e)}",
            )
        except asyncssh.PermissionDenied:
            return SSHTestResponse(
                success=False,
                host=credentials.host,
                username=credentials.username,
                error="Permission denied - check username and password",
            )
        except asyncssh.HostKeyNotVerifiable:
            return SSHTestResponse(
                success=False,
                host=credentials.host,
                username=credentials.username,
                error="Host key verification failed",
            )
        except OSError as e:
            return SSHTestResponse(
                success=False,
                host=credentials.host,
                username=credentials.username,
                error=f"Connection failed: {str(e)}",
            )
        except Exception as e:
            return SSHTestResponse(
                success=False,
                host=credentials.host,
                username=credentials.username,
                error=f"Unexpected error: {str(e)}",
            )

    @staticmethod
    async def create_connection(
        credentials: SSHCredentials,
    ) -> Tuple[Optional[asyncssh.SSHClientConnection], Optional[str]]:
        """
        Create and return an SSH connection.

        Returns:
            Tuple of (connection, error_message)
        """
        try:
            conn_options = {
                "host": credentials.host,
                "port": credentials.port,
                "username": credentials.username,
                "known_hosts": None,
            }

            if credentials.password:
                conn_options["password"] = credentials.password
            if credentials.key_path:
                conn_options["client_keys"] = [credentials.key_path]

            conn = await asyncssh.connect(**conn_options)
            return conn, None

        except asyncssh.PermissionDenied:
            return None, "Permission denied - check credentials"
        except OSError as e:
            return None, f"Connection failed: {str(e)}"
        except Exception as e:
            return None, f"Error: {str(e)}"
