#!/bin/bash
# Setup script for Fingerprint Sensor on Jetson Nano/Linux
# Run with: sudo bash setup_jetson.sh

set -e

echo "========================================"
echo "Fingerprint Sensor Setup for Jetson Nano"
echo "========================================"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo bash setup_jetson.sh"
    exit 1
fi

# 1. Install dependencies
echo ""
echo "[1/5] Installing Python dependencies..."
apt-get update -qq
apt-get install -y python3-pip libusb-1.0-0 > /dev/null
pip3 install pyusb Pillow --quiet

# 2. Create udev rule
echo "[2/5] Creating udev rules..."
cat > /etc/udev/rules.d/99-fingerprint.rules << 'EOF'
# Fingerprint Sensor (VID=0483, PID=5720)
# Allow non-root access and prevent usb-storage from claiming it

# Basic permission rule
SUBSYSTEM=="usb", ATTR{idVendor}=="0483", ATTR{idProduct}=="5720", MODE="0666", GROUP="plugdev"

# Tell udisks to ignore this device (not a storage device)
SUBSYSTEM=="usb", ATTR{idVendor}=="0483", ATTR{idProduct}=="5720", ENV{UDISKS_IGNORE}="1"

# Unbind from usb-storage when plugged in
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="0483", ATTR{idProduct}=="5720", RUN+="/bin/sh -c 'for i in /sys/bus/usb/drivers/usb-storage/*:*; do [ -d \"$i\" ] && echo $(basename $i) > /sys/bus/usb/drivers/usb-storage/unbind 2>/dev/null || true; done'"
EOF

echo "  Created /etc/udev/rules.d/99-fingerprint.rules"

# 3. Blacklist usb-storage for this device
echo "[3/5] Creating modprobe blacklist..."
mkdir -p /etc/modprobe.d
cat > /etc/modprobe.d/fingerprint-sensor.conf << 'EOF'
# Fingerprint sensor appears as mass storage but isn't
# This helps prevent usb-storage from grabbing it first
# Note: This doesn't fully prevent it, udev rules do the unbind
EOF

echo "  Created /etc/modprobe.d/fingerprint-sensor.conf"

# 4. Reload udev
echo "[4/5] Reloading udev rules..."
udevadm control --reload-rules
udevadm trigger

# 5. Unbind any currently bound devices
echo "[5/5] Unbinding usb-storage from fingerprint sensor..."
for dev in /sys/bus/usb/drivers/usb-storage/*/; do
    if [ -d "$dev" ]; then
        devname=$(basename "$dev")
        if [[ "$devname" == *:* ]]; then
            echo "  Unbinding: $devname"
            echo "$devname" > /sys/bus/usb/drivers/usb-storage/unbind 2>/dev/null || true
        fi
    fi
done

# Add user to plugdev group
REAL_USER=${SUDO_USER:-$USER}
if [ "$REAL_USER" != "root" ]; then
    usermod -aG plugdev "$REAL_USER" 2>/dev/null || true
    echo "  Added $REAL_USER to plugdev group"
fi

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Unplug and replug the fingerprint sensor"
echo "2. Log out and log back in (for group changes)"
echo "3. Test with: python3 fingerprint.py info"
echo ""
echo "If still not working, try: sudo python3 debug_sensor.py"
