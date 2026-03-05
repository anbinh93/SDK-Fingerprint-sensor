#!/usr/bin/env python3
"""
Debug script for Fingerprint Sensor on Jetson Nano
Run with: sudo python3 debug_sensor.py
"""

import sys
import subprocess
import os

def run_cmd(cmd, check=False):
    """Run shell command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), -1

def print_section(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)

def main():
    print("Fingerprint Sensor Debug Tool")
    print("="*60)
    
    # Check if running as root
    if os.geteuid() != 0:
        print("WARNING: Not running as root. USB access may fail.")
        print("Run with: sudo python3 debug_sensor.py\n")
    
    # 1. Check USB device
    print_section("1. USB Device Detection")
    out, err, code = run_cmd("lsusb | grep -i 0483")
    if out:
        print(f"✓ Device found: {out}")
    else:
        print("✗ Device NOT found! Check USB connection.")
        return 1
    
    # 2. Check USB tree
    print_section("2. USB Device Tree")
    out, err, code = run_cmd("lsusb -t")
    print(out)
    
    # 3. Check kernel drivers
    print_section("3. Kernel Drivers")
    out, err, code = run_cmd("ls -la /sys/bus/usb/drivers/usb-storage/ 2>/dev/null | grep ':'")
    if out:
        print(f"usb-storage is claiming devices:\n{out}")
        print("\n⚠ This is the problem! usb-storage driver is blocking access.")
        
        # Try to find the device binding
        out2, _, _ = run_cmd("ls /sys/bus/usb/drivers/usb-storage/ | grep -E '^[0-9]'")
        if out2:
            for dev in out2.split('\n'):
                dev = dev.strip()
                if dev:
                    print(f"\nAttempting to unbind: {dev}")
                    unbind_cmd = f"echo '{dev}' | sudo tee /sys/bus/usb/drivers/usb-storage/unbind"
                    run_cmd(unbind_cmd)
    else:
        print("✓ usb-storage not claiming any relevant devices")
    
    # 4. Check /dev/sd* devices  
    print_section("4. Block Devices (Mass Storage)")
    out, err, code = run_cmd("lsblk -o NAME,SIZE,TYPE,MOUNTPOINT 2>/dev/null | head -20")
    print(out if out else "No block devices")
    
    # 5. Check mounted filesystems
    print_section("5. Mounted USB Storage")
    out, err, code = run_cmd("mount | grep -E '/dev/sd[b-z]'")
    if out:
        print(f"Mounted devices:\n{out}")
        print("\n⚠ If fingerprint sensor is mounted, unmount it first!")
    else:
        print("✓ No extra USB storage mounted")
    
    # 6. Check USB permissions
    print_section("6. USB Permissions")
    out, err, code = run_cmd("ls -la /dev/bus/usb/*/*")
    # Find the device
    out2, err2, code2 = run_cmd("lsusb | grep 0483:5720")
    if out2:
        parts = out2.split()
        if len(parts) >= 4:
            bus = parts[1]
            dev = parts[3].rstrip(':')
            dev_path = f"/dev/bus/usb/{bus}/{dev}"
            out3, _, _ = run_cmd(f"ls -la {dev_path}")
            print(f"Device path: {dev_path}")
            print(f"Permissions: {out3}")
    
    # 7. Check udev rules
    print_section("7. Udev Rules")
    out, err, code = run_cmd("cat /etc/udev/rules.d/*fingerprint* 2>/dev/null")
    if out:
        print(f"Existing rules:\n{out}")
    else:
        print("No fingerprint udev rules found.")
        print("\nRecommended rule:")
        print('SUBSYSTEM=="usb", ATTR{idVendor}=="0483", ATTR{idProduct}=="5720", MODE="0666"')
    
    # 8. Try pyusb detection
    print_section("8. PyUSB Detection")
    try:
        import usb.core
        import usb.util
        
        # Find device
        dev = usb.core.find(idVendor=0x0483, idProduct=0x5720)
        if dev is None:
            print("✗ PyUSB cannot find device")
            print("  This usually means:")
            print("  - usb-storage driver is blocking")
            print("  - Permission denied")
            print("  - Device not connected")
        else:
            print(f"✓ PyUSB found device!")
            print(f"  Manufacturer: {dev.manufacturer}")
            print(f"  Product: {dev.product}")
            print(f"  Serial: {dev.serial_number}")
            
            # Try to claim
            print("\nAttempting to claim interface...")
            try:
                if dev.is_kernel_driver_active(0):
                    print("  Kernel driver is active, detaching...")
                    dev.detach_kernel_driver(0)
                    print("  ✓ Kernel driver detached")
                
                dev.set_configuration()
                print("  ✓ Configuration set")
                
                # Try a simple command
                print("\nSending test command...")
                import struct
                
                # Test SCSI command
                tag = 1
                cbw = bytearray(31)
                cbw[0:4] = b'USBC'
                cbw[4:8] = struct.pack('<I', tag)
                cbw[8:12] = struct.pack('<I', 8)
                cbw[12] = 0x80
                cbw[14] = 10
                cbw[15:25] = bytes([0x85, 0x00, 0x00, 0x00, 0x00, 0x08, 0x00, 0x02, 0x00, 0x00])
                
                try:
                    dev.write(0x01, bytes(cbw), timeout=2000)
                    data = dev.read(0x81, 8, timeout=2000)
                    print(f"  ✓ Received data: {data.tobytes().hex()}")
                except Exception as e:
                    print(f"  ✗ Communication failed: {e}")
                
                usb.util.release_interface(dev, 0)
                usb.util.dispose_resources(dev)
                
            except usb.core.USBError as e:
                print(f"  ✗ Failed: {e}")
                if "Resource busy" in str(e):
                    print("  → usb-storage driver is blocking!")
                elif "Access denied" in str(e) or "Permission" in str(e):
                    print("  → Need sudo or udev rule!")
            
    except ImportError:
        print("✗ PyUSB not installed. Run: pip install pyusb")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # 9. Recommendations
    print_section("9. Recommended Actions")
    print("""
To fix usb-storage blocking issue:

1. Create udev rule (one-time setup):
   sudo tee /etc/udev/rules.d/99-fingerprint.rules << 'EOF'
SUBSYSTEM=="usb", ATTR{idVendor}=="0483", ATTR{idProduct}=="5720", MODE="0666"
SUBSYSTEM=="usb", ATTR{idVendor}=="0483", ATTR{idProduct}=="5720", ENV{UDISKS_IGNORE}="1"
EOF

2. Blacklist usb-storage for this device:
   sudo tee -a /etc/modprobe.d/blacklist-fingerprint.conf << 'EOF'
# Prevent usb-storage from claiming fingerprint sensor
install usb-storage /bin/sh -c 'modprobe --ignore-install usb-storage; for d in /sys/bus/usb/devices/*/idVendor; do [ "$(cat $d 2>/dev/null)" = "0483" ] && echo $(dirname $d | xargs basename) > /sys/bus/usb/drivers/usb-storage/unbind 2>/dev/null; done; true'
EOF

3. Quick fix (temporary, run after each plug):
   # Find and unbind
   for dev in /sys/bus/usb/drivers/usb-storage/*/; do
     [ -d "$dev" ] && echo $(basename "$dev") | sudo tee /sys/bus/usb/drivers/usb-storage/unbind
   done

4. Reload udev and replug device:
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   # Unplug and replug the sensor

5. Test again:
   sudo python3 fingerprint.py info
""")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
