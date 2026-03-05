#!/usr/bin/env python3
"""
USB Capacitive Fingerprint Reader SDK & CLI
============================================
Cross-platform Python SDK for USB Fingerprint Reader (VID=0x0483, PID=0x5720)

Usage:
    sudo python3 fingerprint.py capture [output.png]
    sudo python3 fingerprint.py led <on|off|red|green|blue|white>
    sudo python3 fingerprint.py info
    sudo python3 fingerprint.py add
    sudo python3 fingerprint.py match
    sudo python3 fingerprint.py delete <user_id|all>

Author: Reverse engineered from D5ScannerS78.dll
"""

import usb.core
import usb.util
import usb.backend.libusb1
import struct
import time
import sys
import platform
import argparse
from typing import Optional, Tuple
from enum import IntEnum


# ==================== Constants ====================

class AckCode(IntEnum):
    SUCCESS = 0x00
    FAIL = 0x01
    FULL = 0x04
    NO_USER = 0x05
    TIMEOUT = 0x08
    GO_OUT = 0x0F


class Command(IntEnum):
    ADD_1 = 0x01
    ADD_2 = 0x02
    ADD_3 = 0x03
    DEL = 0x04
    DEL_ALL = 0x05
    USER_CNT = 0x09
    MATCH = 0x0C
    CHECK_FINGER = 0x21
    GET_IMAGE = 0x24
    COMPARE_LEVEL = 0x28
    LP_MODE = 0x2C
    TIMEOUT = 0x2E
    BEEP = 0x36
    LED = 0x5E


class LED(IntEnum):
    OFF = 0x00
    RED = 0x01
    GREEN = 0x02
    BLUE = 0x04
    WHITE = 0x07


# ==================== SDK Class ====================

class FingerprintReader:
    """USB Capacitive Fingerprint Reader SDK"""
    
    VID = 0x0483
    PID = 0x5720
    IMAGE_WIDTH = 192
    IMAGE_HEIGHT = 192
    
    def __init__(self, libusb_path: str = None, verbose: bool = False):
        self.dev = None
        self.tag = 1
        self.ep_out = 0x01
        self.ep_in = 0x81
        self.timeout = 2000
        self.verbose = verbose
        
        if libusb_path:
            self.backend = usb.backend.libusb1.get_backend(
                find_library=lambda x: libusb_path
            )
        else:
            self.backend = None
    
    def _log(self, msg: str):
        """Print debug message if verbose mode is enabled"""
        if self.verbose:
            print(f"[DEBUG] {msg}")
    
    def open(self) -> bool:
        """Open and initialize the fingerprint reader"""
        self._log(f"Searching for device VID={hex(self.VID)} PID={hex(self.PID)}")
        
        self.dev = usb.core.find(
            idVendor=self.VID, 
            idProduct=self.PID, 
            backend=self.backend
        )
        
        if not self.dev:
            self._log("Device not found by PyUSB")
            return False
        
        self._log(f"Device found: {self.dev.manufacturer} {self.dev.product}")
        
        try:
            if self.dev.is_kernel_driver_active(0):
                self._log("Kernel driver active, detaching...")
                self.dev.detach_kernel_driver(0)
                self._log("Kernel driver detached")
        except Exception as e:
            self._log(f"Kernel driver detach: {e}")
        
        try:
            self._log("Setting configuration...")
            self.dev.set_configuration()
            self._log("Configuration set")
        except Exception as e:
            self._log(f"Set configuration failed: {e}")
            return False
        
        try:
            self._log("Sending reset command...")
            self.dev.ctrl_transfer(0x21, 0xFF, 0, 0, None, timeout=1000)
            self._log("Reset command sent")
        except Exception as e:
            self._log(f"Reset command: {e}")
        
        time.sleep(0.2)
        
        try:
            self._log("Clearing endpoints...")
            self.dev.ctrl_transfer(0x02, 0x01, 0, self.ep_out, None, timeout=500)
            self.dev.ctrl_transfer(0x02, 0x01, 0, self.ep_in, None, timeout=500)
            self._log("Endpoints cleared")
        except Exception as e:
            self._log(f"Clear endpoints: {e}")
        
        # Flush any pending data
        self._log("Flushing pending data...")
        flush_count = 0
        while True:
            try:
                self.dev.read(self.ep_in, 64, timeout=100)
                flush_count += 1
            except:
                break
        self._log(f"Flushed {flush_count} packets")
        
        self._log("Device opened successfully")
        return True
    
    def close(self):
        """Close the fingerprint reader"""
        if self.dev:
            try:
                usb.util.release_interface(self.dev, 0)
            except:
                pass
            usb.util.dispose_resources(self.dev)
            self.dev = None
    
    def _scsi_write(self, data: bytes) -> bool:
        """SCSI vendor WRITE (opcode 0x86)"""
        length = len(data)
        cdb = bytes([0x86, 0x00, 0x00, 0x00, 0x00, length, 0x00, 0x02, 0x00, 0x00])
        
        cbw = bytearray(31)
        cbw[0:4] = b'USBC'
        cbw[4:8] = struct.pack('<I', self.tag)
        cbw[8:12] = struct.pack('<I', length)
        cbw[12] = 0x00
        cbw[14] = 10
        cbw[15:25] = cdb
        self.tag += 1
        
        try:
            self._log(f"SCSI WRITE: {data.hex()}")
            self.dev.write(self.ep_out, bytes(cbw), timeout=self.timeout)
            self.dev.write(self.ep_out, data, timeout=self.timeout)
            csw = self.dev.read(self.ep_in, 13, timeout=self.timeout)
            return len(csw) >= 13 and csw[12] == 0
        except:
            return False
    
    def _scsi_read(self, length: int) -> Optional[bytes]:
        """SCSI vendor READ (opcode 0x85)"""
        cdb = bytes([
            0x85, 0x00,
            (length >> 24) & 0xFF,
            (length >> 16) & 0xFF,
            (length >> 8) & 0xFF,
            length & 0xFF,
            0x00, 0x02, 0x00, 0x00
        ])
        
        cbw = bytearray(31)
        cbw[0:4] = b'USBC'
        cbw[4:8] = struct.pack('<I', self.tag)
        cbw[8:12] = struct.pack('<I', length)
        cbw[12] = 0x80
        cbw[14] = 10
        cbw[15:25] = cdb
        self.tag += 1
        
        try:
            self.dev.write(self.ep_out, bytes(cbw), timeout=5000)
            
            data = bytearray()
            remaining = length
            
            while remaining > 0:
                try:
                    chunk = self.dev.read(self.ep_in, min(remaining, 512), timeout=5000)
                    if len(chunk) == 13 and chunk[0:4] == b'USBS':
                        break
                    data.extend(chunk)
                    remaining -= len(chunk)
                except:
                    break
            
            if len(data) > 0:
                try:
                    self.dev.read(self.ep_in, 13, timeout=1000)
                except:
                    pass
            
            return bytes(data)
        except:
            return None
    
    def _build_packet(self, cmd: int, p1: int = 0, p2: int = 0, 
                      p3: int = 0, p4: int = 0) -> bytes:
        """Build fingerprint command packet"""
        checksum = (cmd + p1 + p2 + p3 + p4) & 0xFF
        return bytes([0xF6, p1, cmd, p2, p3, p4, checksum, 0xF6])
    
    def _send_command(self, cmd: int, p1: int = 0, p2: int = 0,
                      p3: int = 0, p4: int = 0, read_len: int = 8) -> Optional[bytes]:
        """Send command and receive response"""
        self._log(f"CMD: {hex(cmd)} p1={p1} p2={p2} p3={p3} p4={p4}")
        packet = self._build_packet(cmd, p1, p2, p3, p4)
        if not self._scsi_write(packet):
            self._log("SCSI write failed")
            return None
        time.sleep(0.05)
        response = self._scsi_read(read_len)
        if response:
            self._log(f"RESPONSE: {response.hex()}")
        else:
            self._log("No response")
        return response
    
    def _parse_response(self, data: bytes) -> Tuple[int, int, int, int, int]:
        """Parse response: returns (cmd, p1, p2, p3, p4)"""
        if data and len(data) >= 8 and data[0] == 0xF6 and data[7] == 0xF6:
            return data[2], data[1], data[3], data[4], data[5]
        return 0, 0, 0, 0, 0
    
    # ==================== Public API ====================
    
    def get_user_count(self) -> int:
        """Get number of registered fingerprints"""
        response = self._send_command(Command.USER_CNT)
        if response:
            cmd, p1, p2, p3, p4 = self._parse_response(response)
            if cmd == Command.USER_CNT:
                return p3
        return -1
    
    def get_compare_level(self) -> int:
        """Get comparison level (0-9)"""
        response = self._send_command(Command.COMPARE_LEVEL, p3=1)
        if response:
            cmd, p1, p2, p3, p4 = self._parse_response(response)
            if p4 == AckCode.SUCCESS:
                return p2
        return -1
    
    def set_compare_level(self, level: int) -> bool:
        """Set comparison level (0-9, higher is stricter)"""
        if not 0 <= level <= 9:
            return False
        response = self._send_command(Command.COMPARE_LEVEL, p2=level)
        if response:
            _, _, _, _, p4 = self._parse_response(response)
            return p4 == AckCode.SUCCESS
        return False
    
    def led_on(self, color: int = LED.WHITE) -> bool:
        """Turn on LED"""
        response = self._send_command(Command.LED, p2=color)
        return response is not None
    
    def led_off(self) -> bool:
        """Turn off LED"""
        return self.led_on(LED.OFF)
    
    def beep(self, duration_ms: int = 100) -> bool:
        """Make beep sound"""
        high = (duration_ms >> 8) & 0xFF
        low = duration_ms & 0xFF
        response = self._send_command(Command.BEEP, p2=high, p3=low)
        return response is not None
    
    def check_finger(self) -> bool:
        """Check if finger is on sensor by analyzing image variance"""
        image = self.capture_image()
        if not image or len(image) < 1000:
            return False
        
        # Calculate variance - fingerprint has high variation, empty has low
        avg = sum(image) / len(image)
        variance = sum((x - avg) ** 2 for x in image) / len(image)
        std_dev = variance ** 0.5
        
        # Threshold: empty sensor has StdDev ~1-2, fingerprint has ~30+
        return std_dev > 10.0
    
    def _has_fingerprint(self, image: bytes) -> bool:
        """Check if image contains a valid fingerprint"""
        if not image or len(image) < 1000:
            return False
        
        avg = sum(image) / len(image)
        variance = sum((x - avg) ** 2 for x in image) / len(image)
        std_dev = variance ** 0.5
        
        return std_dev > 10.0
    
    def capture_image(self) -> Optional[bytes]:
        """Capture fingerprint image (192x192 grayscale)"""
        # Send GetImage command
        packet = self._build_packet(Command.GET_IMAGE)
        if not self._scsi_write(packet):
            return None
        
        time.sleep(0.05)
        
        # Read header (8 bytes response)
        header = self._scsi_read(8)
        if not header or len(header) < 8 or header[0] != 0xF6:
            return None
        
        # Check if GetImage was successful
        p4 = header[5]  # ACK code
        if p4 != AckCode.SUCCESS:
            return None
        
        # Parse size: 2 * (P3 + (P2 << 8))
        p2, p3 = header[3], header[4]
        image_size = 2 * (p3 + (p2 << 8))
        
        if image_size == 0:
            image_size = self.IMAGE_WIDTH * self.IMAGE_HEIGHT
        
        # Read image in 2 parts (like DLL does)
        # DLL: sub_10001F30(*v3, (v5 >> 1) + 1, &unk_100251E0)
        # DLL: sub_10001F30(*v3, (v5 >> 1) + 2, &unk_100251E1 + (v5 >> 1))
        # DLL then copies from unk_100251E1 (skips first byte!)
        
        half = image_size // 2
        
        # Read part1: half+1 bytes, skip first byte
        part1_raw = self._scsi_read(half + 1)
        if not part1_raw or len(part1_raw) < half + 1:
            return None
        part1 = part1_raw[1:]  # Skip first byte
        
        # Read part2: half+2 bytes, skip first byte
        part2_raw = self._scsi_read(half + 2)
        if not part2_raw or len(part2_raw) < half + 2:
            return None
        part2 = part2_raw[1:]  # Skip first byte
        
        # Combine
        image_data = part1 + part2
        return image_data[:image_size] if len(image_data) >= image_size else None
    
    def add_user(self, user_id: int = None) -> Tuple[bool, int]:
        """Add new fingerprint. Returns (success, user_id)"""
        if user_id is None:
            count = self.get_user_count()
            if count < 0:
                return False, 0
            user_id = count + 1
        
        if not 1 <= user_id <= 1000:
            return False, 0
        
        high = (user_id >> 8) & 0xFF
        low = user_id & 0xFF
        
        # Step 1
        response = self._send_command(Command.ADD_1, p1=high, p2=low, p3=3)
        if not response:
            return False, 0
        _, _, _, _, p4 = self._parse_response(response)
        if p4 != AckCode.SUCCESS:
            return False, 0
        
        time.sleep(0.5)
        
        # Step 3 (finalize)
        response = self._send_command(Command.ADD_3, p1=high, p2=low, p3=3)
        if response:
            _, _, _, _, p4 = self._parse_response(response)
            return p4 == AckCode.SUCCESS, user_id
        
        return False, 0
    
    def match_fingerprint(self, timeout_sec: float = 5.0) -> Tuple[bool, int]:
        """Match fingerprint. Returns (matched, user_id)"""
        start = time.time()
        
        while time.time() - start < timeout_sec:
            response = self._send_command(Command.MATCH)
            if response:
                _, _, _, p3, p4 = self._parse_response(response)
                if p4 == AckCode.SUCCESS:
                    return True, p3
                elif p4 == AckCode.NO_USER:
                    return False, 0
            time.sleep(0.1)
        
        return False, 0
    
    def delete_user(self, user_id: int) -> bool:
        """Delete a fingerprint"""
        high = (user_id >> 8) & 0xFF
        low = user_id & 0xFF
        response = self._send_command(Command.DEL, p1=high, p2=low)
        if response:
            _, _, _, _, p4 = self._parse_response(response)
            return p4 == AckCode.SUCCESS
        return False
    
    def delete_all(self) -> bool:
        """Delete all fingerprints"""
        response = self._send_command(Command.DEL_ALL)
        if response:
            _, _, _, _, p4 = self._parse_response(response)
            return p4 == AckCode.SUCCESS
        return False


# ==================== CLI ====================

def get_libusb_path():
    """Get libusb path based on platform"""
    system = platform.system()
    if system == "Darwin":
        return '/opt/homebrew/lib/libusb-1.0.dylib'
    return None


def cmd_info(fp: FingerprintReader):
    """Show device info"""
    print("Device Information:")
    print(f"  Registered users: {fp.get_user_count()}")
    print(f"  Compare level: {fp.get_compare_level()}")


def cmd_led(fp: FingerprintReader, state: str):
    """Control LED"""
    colors = {
        'on': LED.WHITE, 'white': LED.WHITE,
        'off': LED.OFF,
        'red': LED.RED,
        'green': LED.GREEN,
        'blue': LED.BLUE,
    }
    
    if state.lower() not in colors:
        print(f"Unknown LED state: {state}")
        print("Valid: on, off, red, green, blue, white")
        return
    
    fp.led_on(colors[state.lower()])
    print(f"LED: {state}")


def cmd_capture(fp: FingerprintReader, output: str):
    """Capture fingerprint image"""
    print("Place your finger on the sensor...")
    fp.led_on(LED.WHITE)
    
    # Wait for valid fingerprint (not just any image)
    print("Waiting for finger...", end='', flush=True)
    image = None
    for i in range(50):  # 5 seconds timeout
        temp_image = fp.capture_image()
        if temp_image and fp._has_fingerprint(temp_image):
            image = temp_image
            break
        print(".", end='', flush=True)
        time.sleep(0.1)
    print()
    
    if not image:
        print("No finger detected (empty sensor)")
        fp.led_off()
        return
    
    print("Fingerprint captured!")
    fp.beep(50)
    fp.led_off()
    
    print(f"Image size: {len(image)} bytes")
    
    # Calculate quality metrics
    avg = sum(image) / len(image)
    variance = sum((x - avg) ** 2 for x in image) / len(image)
    std_dev = variance ** 0.5
    print(f"Image quality: StdDev={std_dev:.1f} (higher is better)")
    
    # Save raw
    raw_file = output.rsplit('.', 1)[0] + '.raw'
    with open(raw_file, 'wb') as f:
        f.write(image)
    print(f"Saved raw: {raw_file}")
    
    # Save PNG
    try:
        from PIL import Image
        import numpy as np
        
        img_array = np.frombuffer(image[:192*192], dtype=np.uint8)
        img_array = img_array.reshape((192, 192))
        img = Image.fromarray(img_array, mode='L')
        img.save(output)
        print(f"Saved image: {output}")
    except ImportError:
        print("PIL not installed, skipping PNG save")
        print("Install with: pip install Pillow")


def cmd_add(fp: FingerprintReader):
    """Add new fingerprint"""
    print("Place your finger on the sensor...")
    fp.led_on(LED.GREEN)
    
    # Wait for valid fingerprint
    print("Waiting for finger...", end='', flush=True)
    for i in range(50):
        image = fp.capture_image()
        if image and fp._has_fingerprint(image):
            break
        print(".", end='', flush=True)
        time.sleep(0.1)
    else:
        print()
        print("No finger detected")
        fp.led_off()
        return
    print()
    
    print("Adding fingerprint...")
    success, user_id = fp.add_user()
    fp.led_off()
    
    if success:
        fp.beep(100)
        print(f"Added user #{user_id}")
    else:
        print("Failed to add fingerprint")


def cmd_match(fp: FingerprintReader):
    """Match fingerprint"""
    print("Place your finger on the sensor...")
    fp.led_on(LED.BLUE)
    
    matched, user_id = fp.match_fingerprint(timeout_sec=10)
    fp.led_off()
    
    if matched:
        fp.beep(100)
        print(f"Matched: User #{user_id}")
    else:
        print("No match found")


def cmd_delete(fp: FingerprintReader, target: str):
    """Delete fingerprint(s)"""
    if target.lower() == 'all':
        if fp.delete_all():
            print("Deleted all fingerprints")
        else:
            print("Delete failed")
    else:
        try:
            user_id = int(target)
            if fp.delete_user(user_id):
                print(f"Deleted user #{user_id}")
            else:
                print("Delete failed")
        except ValueError:
            print(f"Invalid user ID: {target}")


def main():
    parser = argparse.ArgumentParser(
        description='USB Fingerprint Reader CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  sudo python3 fingerprint.py info
  sudo python3 fingerprint.py capture fingerprint.png
  sudo python3 fingerprint.py led red
  sudo python3 fingerprint.py add
  sudo python3 fingerprint.py match
  sudo python3 fingerprint.py delete all
  sudo python3 fingerprint.py --verbose info  # Debug mode
'''
    )
    
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable debug output')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Info
    subparsers.add_parser('info', help='Show device information')
    
    # Capture
    p_capture = subparsers.add_parser('capture', help='Capture fingerprint image')
    p_capture.add_argument('output', nargs='?', default='fingerprint.png', help='Output file')
    
    # LED
    p_led = subparsers.add_parser('led', help='Control LED')
    p_led.add_argument('state', choices=['on', 'off', 'red', 'green', 'blue', 'white'])
    
    # Add
    subparsers.add_parser('add', help='Add new fingerprint')
    
    # Match
    subparsers.add_parser('match', help='Match fingerprint')
    
    # Delete
    p_delete = subparsers.add_parser('delete', help='Delete fingerprint(s)')
    p_delete.add_argument('target', help='User ID or "all"')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Open device
    fp = FingerprintReader(get_libusb_path(), verbose=args.verbose)
    
    if not fp.open():
        print("ERROR: Device not found")
        print("Make sure device is connected and you have permissions (sudo)")
        if not args.verbose:
            print("Run with --verbose for more details")
        return 1
    
    try:
        if args.command == 'info':
            cmd_info(fp)
        elif args.command == 'capture':
            cmd_capture(fp, args.output)
        elif args.command == 'led':
            cmd_led(fp, args.state)
        elif args.command == 'add':
            cmd_add(fp)
        elif args.command == 'match':
            cmd_match(fp)
        elif args.command == 'delete':
            cmd_delete(fp, args.target)
    finally:
        fp.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
