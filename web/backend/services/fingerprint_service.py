"""Fingerprint sensor service - executes commands on Jetson Nano via SSH."""

import asyncio
import base64
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

import asyncssh

from models.connection import SSHCredentials

logger = logging.getLogger(__name__)


@dataclass
class FingerprintImage:
    """Fingerprint image data."""
    data: bytes  # Raw 192x192 grayscale
    width: int = 192
    height: int = 192
    quality: float = 0.0  # StdDev metric
    has_finger: bool = False

    def to_base64(self) -> str:
        """Convert image to base64 for web transmission."""
        return base64.b64encode(self.data).decode('ascii')

    @staticmethod
    def calculate_quality(data: bytes) -> Tuple[float, bool]:
        """Calculate quality score and finger presence."""
        if not data or len(data) < 1000:
            return 0.0, False
        avg = sum(data) / len(data)
        variance = sum((x - avg) ** 2 for x in data) / len(data)
        std_dev = variance ** 0.5
        has_finger = std_dev > 10.0
        return std_dev, has_finger


@dataclass
class SensorStatus:
    """Fingerprint sensor status."""
    connected: bool
    user_count: int = 0
    compare_level: int = 5
    error: Optional[str] = None


class PersistentStreamProcess:
    """Manages a persistent streaming process on Jetson."""
    
    STREAM_SERVER_SCRIPT = '''
import sys
import base64
import time
import threading
import queue

sys.path.insert(0, '{sdk_path}')

try:
    from fingerprint import FingerprintReader, LED
except ImportError:
    print("ERROR:Cannot import fingerprint module", flush=True)
    sys.exit(1)

class StreamingServer:
    def __init__(self):
        self.fp = FingerprintReader()
        self.streaming = False
        self.fps = 10
        self.running = True
        self.cmd_queue = queue.Queue()
        
    def run(self):
        if not self.fp.open():
            print("ERROR:Device not found", flush=True)
            return
        print("OK:Device opened", flush=True)
        cmd_thread = threading.Thread(target=self._read_commands, daemon=True)
        cmd_thread.start()
        try:
            self._main_loop()
        finally:
            self.fp.close()
            
    def _read_commands(self):
        while self.running:
            try:
                line = sys.stdin.readline()
                if not line:
                    self.running = False
                    break
                self.cmd_queue.put(line.strip())
            except:
                self.running = False
                break
                
    def _main_loop(self):
        last_capture = 0
        while self.running:
            try:
                while True:
                    cmd = self.cmd_queue.get_nowait()
                    self._handle_command(cmd)
            except queue.Empty:
                pass
            if self.streaming:
                now = time.time()
                interval = 1.0 / self.fps
                if now - last_capture >= interval:
                    self._capture_and_send()
                    last_capture = now
                else:
                    time.sleep(0.005)
            else:
                time.sleep(0.01)
                
    def _handle_command(self, cmd):
        parts = cmd.upper().split()
        if not parts:
            return
        action = parts[0]
        if action == "QUIT":
            self.running = False
            print("OK:Quitting", flush=True)
        elif action == "CAPTURE":
            self._capture_and_send()
        elif action == "START":
            if len(parts) > 1:
                try:
                    self.fps = max(1, min(30, int(parts[1])))
                except:
                    self.fps = 10
            self.streaming = True
            print(f"OK:Streaming at {{self.fps}} FPS", flush=True)
        elif action == "STOP":
            self.streaming = False
            print("OK:Stopped", flush=True)
        elif action == "LED":
            color = 0
            if len(parts) > 1:
                try:
                    color = int(parts[1])
                except:
                    pass
            if color == 0:
                self.fp.led_off()
            else:
                self.fp.led_on(color)
            print(f"OK:LED {{color}}", flush=True)
        elif action == "INFO":
            count = self.fp.get_user_count()
            level = self.fp.get_compare_level()
            print(f"INFO:{{count}}:{{level}}", flush=True)
        else:
            print(f"ERROR:Unknown command: {{action}}", flush=True)
            
    def _capture_and_send(self):
        try:
            image = self.fp.capture_image()
            if image:
                b64 = base64.b64encode(image).decode('ascii')
                print(f"IMAGE:{{b64}}", flush=True)
            else:
                print("ERROR:Capture returned None", flush=True)
        except Exception as e:
            print(f"ERROR:Capture exception: {{e}}", flush=True)

if __name__ == "__main__":
    server = StreamingServer()
    server.run()
'''

    def __init__(self, sdk_path: str):
        self.sdk_path = sdk_path
        self._process: Optional[asyncssh.SSHClientProcess] = None
        self._response_queue: asyncio.Queue = asyncio.Queue()
        self._reader_task: Optional[asyncio.Task] = None
        self._started = False
        
    async def start(self, conn: asyncssh.SSHClientConnection) -> Tuple[bool, str]:
        """Start the persistent streaming process."""
        if self._started:
            return True, "Already running"
            
        try:
            script = self.STREAM_SERVER_SCRIPT.format(sdk_path=self.sdk_path)
            script_b64 = base64.b64encode(script.encode()).decode()
            cmd = f'python3 -c "import base64; exec(base64.b64decode(\'{script_b64}\').decode())"'
            
            self._process = await conn.create_process(cmd)
            
            # Start reader task
            self._reader_task = asyncio.create_task(self._read_output())
            
            # Wait for initialization
            try:
                response = await asyncio.wait_for(self._response_queue.get(), timeout=5.0)
                if response.startswith("OK:"):
                    self._started = True
                    logger.info(f"[FP-Stream] Process started: {response}")
                    return True, response
                else:
                    logger.error(f"[FP-Stream] Start failed: {response}")
                    await self.stop()
                    return False, response
            except asyncio.TimeoutError:
                logger.error("[FP-Stream] Timeout waiting for process start")
                await self.stop()
                return False, "Timeout"
                
        except Exception as e:
            logger.error(f"[FP-Stream] Failed to start: {e}")
            return False, str(e)
            
    async def stop(self):
        """Stop the streaming process."""
        self._started = False
        
        if self._process:
            try:
                self._process.stdin.write("QUIT\n")
                await asyncio.sleep(0.1)
            except:
                pass
            try:
                self._process.terminate()
            except:
                pass
            self._process = None
            
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
            
        # Clear queue
        while not self._response_queue.empty():
            try:
                self._response_queue.get_nowait()
            except:
                pass
                
    async def _read_output(self):
        """Background task to read process output."""
        try:
            while self._process and self._started:
                line = await self._process.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if line:
                    await self._response_queue.put(line)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[FP-Stream] Reader error: {e}")
            
    async def send_command(self, cmd: str, timeout: float = 2.0) -> Optional[str]:
        """Send command and wait for response."""
        if not self._started or not self._process:
            return None
            
        try:
            # Clear queue first
            while not self._response_queue.empty():
                try:
                    self._response_queue.get_nowait()
                except:
                    pass
                    
            self._process.stdin.write(f"{cmd}\n")
            await self._process.stdin.drain()
            
            response = await asyncio.wait_for(self._response_queue.get(), timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.warning(f"[FP-Stream] Command timeout: {cmd}")
            return None
        except Exception as e:
            logger.error(f"[FP-Stream] Command error: {e}")
            return None
            
    async def capture_fast(self) -> Optional[str]:
        """Fast capture - returns base64 image data or None."""
        response = await self.send_command("CAPTURE", timeout=1.0)
        if response and response.startswith("IMAGE:"):
            return response[6:]
        return None
        
    @property
    def is_running(self) -> bool:
        return self._started and self._process is not None


class FingerprintService:
    """Service for fingerprint sensor operations via SSH."""

    # Path to fingerprint SDK on Jetson
    SDK_PATH = "/home/binhan3/SDK-Fingerprint-sensor"

    # Python script to run on Jetson for various operations
    CAPTURE_SCRIPT = '''
import sys
sys.path.insert(0, '{sdk_path}')
from fingerprint import FingerprintReader
import base64

fp = FingerprintReader()
if not fp.open():
    print("ERROR:Device not found")
    sys.exit(1)

try:
    image = fp.capture_image()
    if image:
        print("IMAGE:" + base64.b64encode(image).decode())
    else:
        print("ERROR:Capture failed")
finally:
    fp.close()
'''

    INFO_SCRIPT = '''
import sys
sys.path.insert(0, '{sdk_path}')
from fingerprint import FingerprintReader

fp = FingerprintReader()
if not fp.open():
    print("ERROR:Device not found")
    sys.exit(1)

try:
    count = fp.get_user_count()
    level = fp.get_compare_level()
    print(f"OK:{count}:{level}")
finally:
    fp.close()
'''

    LED_SCRIPT = '''
import sys
sys.path.insert(0, '{sdk_path}')
from fingerprint import FingerprintReader, LED

fp = FingerprintReader()
if not fp.open():
    print("ERROR:Device not found")
    sys.exit(1)

try:
    color = {color}
    if color == 0:
        fp.led_off()
    else:
        fp.led_on(color)
    print("OK")
finally:
    fp.close()
'''

    MATCH_SCRIPT = '''
import sys
sys.path.insert(0, '{sdk_path}')
from fingerprint import FingerprintReader

fp = FingerprintReader()
if not fp.open():
    print("ERROR:Device not found")
    sys.exit(1)

try:
    matched, user_id = fp.match_fingerprint(timeout_sec=5)
    if matched:
        print(f"MATCH:{user_id}")
    else:
        print("NOMATCH")
finally:
    fp.close()
'''

    ADD_SCRIPT = '''
import sys
sys.path.insert(0, '{sdk_path}')
from fingerprint import FingerprintReader

fp = FingerprintReader()
if not fp.open():
    print("ERROR:Device not found")
    sys.exit(1)

try:
    success, user_id = fp.add_user()
    if success:
        print(f"OK:{user_id}")
    else:
        print("ERROR:Add failed")
finally:
    fp.close()
'''

    DELETE_SCRIPT = '''
import sys
sys.path.insert(0, '{sdk_path}')
from fingerprint import FingerprintReader

fp = FingerprintReader()
if not fp.open():
    print("ERROR:Device not found")
    sys.exit(1)

try:
    user_id = {user_id}
    if user_id == 0:
        success = fp.delete_all()
    else:
        success = fp.delete_user(user_id)
    if success:
        print("OK")
    else:
        print("ERROR:Delete failed")
finally:
    fp.close()
'''

    def __init__(self):
        self._credentials: Optional[SSHCredentials] = None
        self._conn: Optional[asyncssh.SSHClientConnection] = None
        self._stream_process: Optional[PersistentStreamProcess] = None

    async def connect(self, credentials: SSHCredentials) -> Tuple[bool, Optional[str]]:
        """Connect to Jetson Nano via SSH."""
        logger.info(f"[FP] Connecting to Jetson at {credentials.host}:{credentials.port} as {credentials.username}")
        try:
            conn_options = {
                "host": credentials.host,
                "port": credentials.port,
                "username": credentials.username,
                "known_hosts": None,
            }
            if credentials.password:
                conn_options["password"] = credentials.password

            self._conn = await asyncssh.connect(**conn_options)
            self._credentials = credentials
            logger.info(f"[FP] Successfully connected to Jetson")
            return True, None
        except asyncssh.PermissionDenied:
            logger.error(f"[FP] Permission denied for {credentials.username}@{credentials.host}")
            return False, "Permission denied"
        except OSError as e:
            logger.error(f"[FP] Connection failed: {e}")
            return False, f"Connection failed: {e}"
        except Exception as e:
            logger.error(f"[FP] Unexpected error: {e}")
            return False, str(e)

    async def disconnect(self):
        """Disconnect from Jetson."""
        # Stop stream process first
        if self._stream_process:
            await self._stream_process.stop()
            self._stream_process = None
            
        if self._conn:
            self._conn.close()
            await self._conn.wait_closed()
            self._conn = None
        self._credentials = None

    def is_connected(self) -> bool:
        """Check if connected to Jetson."""
        return self._conn is not None
        
    async def _ensure_stream_process(self) -> bool:
        """Ensure persistent stream process is running."""
        if self._stream_process and self._stream_process.is_running:
            return True
            
        if not self._conn:
            return False
            
        self._stream_process = PersistentStreamProcess(self.SDK_PATH)
        success, msg = await self._stream_process.start(self._conn)
        
        if not success:
            logger.warning(f"[FP] Could not start stream process: {msg}")
            self._stream_process = None
            return False
            
        logger.info("[FP] Persistent stream process started")
        return True

    async def _run_script(self, script: str, script_name: str = "unknown") -> Tuple[bool, str]:
        """Run Python script on Jetson and return output."""
        if not self._conn:
            logger.warning(f"[FP] Cannot run script '{script_name}': Not connected")
            return False, "Not connected"

        logger.debug(f"[FP] Running script: {script_name}")

        try:
            # Format script with SDK path
            formatted_script = script.format(sdk_path=self.SDK_PATH)

            # Encode script as base64 to avoid shell escaping issues
            script_b64 = base64.b64encode(formatted_script.encode()).decode()
            cmd = f'python3 -c "import base64; exec(base64.b64decode(\'{script_b64}\').decode())"'

            logger.debug(f"[FP] Executing command on Jetson...")

            result = await self._conn.run(
                cmd,
                check=False,
                timeout=10,
            )

            stdout = result.stdout.strip() if result.stdout else ""
            stderr = result.stderr.strip() if result.stderr else ""

            logger.debug(f"[FP] Script '{script_name}' result:")
            logger.debug(f"[FP]   Return code: {result.returncode}")
            logger.debug(f"[FP]   Stdout: {stdout[:200]}..." if len(stdout) > 200 else f"[FP]   Stdout: {stdout}")
            if stderr:
                logger.debug(f"[FP]   Stderr: {stderr[:500]}")

            if result.returncode != 0:
                error = stderr if stderr else "Unknown error"
                logger.error(f"[FP] Script '{script_name}' failed: {error}")
                return False, error
            return True, stdout
        except asyncio.TimeoutError:
            logger.error(f"[FP] Script '{script_name}' timed out")
            return False, "Timeout"
        except Exception as e:
            logger.error(f"[FP] Script '{script_name}' exception: {e}")
            return False, str(e)

    async def get_status(self) -> SensorStatus:
        """Get sensor status."""
        logger.info("[FP] Getting sensor status...")
        if not self._conn:
            logger.warning("[FP] Cannot get status: Not connected to Jetson")
            return SensorStatus(connected=False, error="Not connected to Jetson")

        success, output = await self._run_script(self.INFO_SCRIPT, "INFO_SCRIPT")
        if not success:
            logger.error(f"[FP] Status check failed: {output}")
            return SensorStatus(connected=False, error=output)

        if output.startswith("ERROR:"):
            error_msg = output[6:]
            logger.error(f"[FP] Sensor error: {error_msg}")
            return SensorStatus(connected=False, error=error_msg)

        if output.startswith("OK:"):
            parts = output[3:].split(":")
            if len(parts) >= 2:
                status = SensorStatus(
                    connected=True,
                    user_count=int(parts[0]),
                    compare_level=int(parts[1]),
                )
                logger.info(f"[FP] Sensor connected! Users: {status.user_count}, Level: {status.compare_level}")
                return status

        logger.error(f"[FP] Invalid response: {output}")
        return SensorStatus(connected=False, error="Invalid response")

    async def capture_image(self, use_fast_mode: bool = True) -> Optional[FingerprintImage]:
        """Capture fingerprint image.
        
        Args:
            use_fast_mode: If True, use persistent stream process for faster capture (~50ms vs ~500ms)
        """
        if not self._conn:
            logger.warning("[FP] Cannot capture: Not connected")
            return None

        # Try fast mode with persistent process first
        if use_fast_mode:
            if await self._ensure_stream_process():
                b64_data = await self._stream_process.capture_fast()
                if b64_data:
                    try:
                        data = base64.b64decode(b64_data)
                        quality, has_finger = FingerprintImage.calculate_quality(data)
                        logger.debug(f"[FP-Fast] Captured: {len(data)} bytes, quality={quality:.1f}")
                        return FingerprintImage(
                            data=data,
                            quality=quality,
                            has_finger=has_finger,
                        )
                    except Exception as e:
                        logger.error(f"[FP-Fast] Failed to decode: {e}")
                else:
                    logger.warning("[FP-Fast] Capture returned None, falling back to script")

        # Fallback to script mode (slower but more reliable)
        success, output = await self._run_script(self.CAPTURE_SCRIPT, "CAPTURE_SCRIPT")
        if not success:
            logger.error(f"[FP] Capture failed: {output}")
            return None

        if output.startswith("ERROR:"):
            logger.error(f"[FP] Capture error: {output[6:]}")
            return None

        if output.startswith("IMAGE:"):
            try:
                data = base64.b64decode(output[6:])
                quality, has_finger = FingerprintImage.calculate_quality(data)
                logger.debug(f"[FP] Captured image: {len(data)} bytes, quality={quality:.1f}, has_finger={has_finger}")
                return FingerprintImage(
                    data=data,
                    quality=quality,
                    has_finger=has_finger,
                )
            except Exception as e:
                logger.error(f"[FP] Failed to decode image: {e}")
                return None

        logger.warning(f"[FP] Unexpected capture output: {output[:100]}")
        return None
    
    async def capture_image_fast(self) -> Optional[FingerprintImage]:
        """Fast capture using persistent stream - optimized for streaming."""
        return await self.capture_image(use_fast_mode=True)

    async def led_control(self, color: int) -> bool:
        """Control LED. Colors: 0=off, 1=red, 2=green, 4=blue, 7=white."""
        logger.debug(f"[FP] LED control: color={color}")
        if not self._conn:
            logger.warning("[FP] Cannot control LED: Not connected")
            return False

        # Use fast mode via stream process if available
        if self._stream_process and self._stream_process.is_running:
            response = await self._stream_process.send_command(f"LED {color}")
            if response and response.startswith("OK:"):
                return True

        # Fallback to script mode
        script = self.LED_SCRIPT.replace("{color}", str(color))
        success, output = await self._run_script(script, "LED_SCRIPT")
        return success and output == "OK"

    async def match_fingerprint(self) -> Tuple[bool, int]:
        """Match fingerprint. Returns (matched, user_id)."""
        logger.info("[FP] Starting fingerprint match...")
        if not self._conn:
            logger.warning("[FP] Cannot match: Not connected")
            return False, 0

        success, output = await self._run_script(self.MATCH_SCRIPT, "MATCH_SCRIPT")
        if not success:
            logger.error(f"[FP] Match failed: {output}")
            return False, 0

        if output.startswith("MATCH:"):
            user_id = int(output[6:])
            logger.info(f"[FP] Match found! User ID: {user_id}")
            return True, user_id
        logger.info("[FP] No match found")
        return False, 0

    async def add_user(self) -> Tuple[bool, int]:
        """Add new fingerprint. Returns (success, user_id)."""
        logger.info("[FP] Adding new fingerprint...")
        if not self._conn:
            logger.warning("[FP] Cannot add: Not connected")
            return False, 0

        success, output = await self._run_script(self.ADD_SCRIPT, "ADD_SCRIPT")
        if not success:
            logger.error(f"[FP] Add failed: {output}")
            return False, 0

        if output.startswith("OK:"):
            user_id = int(output[3:])
            logger.info(f"[FP] Successfully added user ID: {user_id}")
            return True, user_id
        logger.error(f"[FP] Add returned unexpected: {output}")
        return False, 0

    async def delete_user(self, user_id: int) -> bool:
        """Delete a fingerprint. Use user_id=0 to delete all."""
        logger.info(f"[FP] Deleting user: {user_id} (0=all)")
        if not self._conn:
            logger.warning("[FP] Cannot delete: Not connected")
            return False

        # Format user_id first, sdk_path will be formatted by _run_script
        script = self.DELETE_SCRIPT.replace("{user_id}", str(user_id))
        success, output = await self._run_script(script, "DELETE_SCRIPT")
        if success and output == "OK":
            logger.info(f"[FP] Successfully deleted user {user_id}")
            return True
        logger.error(f"[FP] Delete failed: {output}")
        return False


    # Diagnostic script to check USB and pyusb
    DIAGNOSTIC_SCRIPT = '''
import sys
import os

print("=== DIAGNOSTIC INFO ===")
print(f"Python: {sys.executable}")
print(f"Version: {sys.version}")
print(f"User: {os.getenv('USER', 'unknown')}")
print()

# Check pyusb
print("=== PYUSB CHECK ===")
try:
    import usb.core
    import usb.util
    print("pyusb: INSTALLED")

    # Find USB devices
    print()
    print("=== USB DEVICES ===")
    devices = list(usb.core.find(find_all=True))
    for dev in devices:
        vid = f"{dev.idVendor:04x}"
        pid = f"{dev.idProduct:04x}"
        try:
            mfr = usb.util.get_string(dev, dev.iManufacturer) if dev.iManufacturer else "N/A"
            prod = usb.util.get_string(dev, dev.iProduct) if dev.iProduct else "N/A"
        except:
            mfr = "N/A"
            prod = "N/A"
        print(f"  {vid}:{pid} - {mfr} / {prod}")

    # Check for fingerprint sensor specifically
    print()
    print("=== FINGERPRINT SENSOR (0483:5720) ===")
    fp_dev = usb.core.find(idVendor=0x0483, idProduct=0x5720)
    if fp_dev:
        print("FOUND!")
        print(f"  Bus: {fp_dev.bus}, Address: {fp_dev.address}")
    else:
        print("NOT FOUND")

except ImportError as e:
    print(f"pyusb: NOT INSTALLED - {e}")
except Exception as e:
    print(f"Error: {e}")

# Check SDK path
print()
print("=== SDK CHECK ===")
sdk_path = '{sdk_path}'
print(f"SDK Path: {sdk_path}")
print(f"Exists: {os.path.exists(sdk_path)}")
if os.path.exists(sdk_path):
    fp_file = os.path.join(sdk_path, 'fingerprint.py')
    print(f"fingerprint.py exists: {os.path.exists(fp_file)}")

print()
print("=== END DIAGNOSTIC ===")
'''

    async def run_diagnostic(self) -> str:
        """Run diagnostic script on Jetson to check USB and pyusb."""
        logger.info("[FP] Running diagnostic...")
        if not self._conn:
            return "ERROR: Not connected to Jetson"

        success, output = await self._run_script(self.DIAGNOSTIC_SCRIPT, "DIAGNOSTIC")
        if success:
            logger.info(f"[FP] Diagnostic output:\n{output}")
            return output
        else:
            logger.error(f"[FP] Diagnostic failed: {output}")
            return f"ERROR: {output}"


# Global fingerprint service instance
fingerprint_service = FingerprintService()
