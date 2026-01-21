# 📖 Capacitive Fingerprint Reader - Cross-Platform SDK

Python SDK cho USB Capacitive Fingerprint Reader (VID=0x0483, PID=0x5720), hoạt động trên macOS/Linux.

## 📋 Mục lục
- [Quick Start](#-quick-start)
- [Python SDK](#-python-sdk)
- [Giao thức USB](#-giao-thức-usb)
- [Giao thức UART](#-giao-thức-uart)
- [Tham khảo](#-tham-khảo)

---

## 🚀 Quick Start

### Yêu cầu
- Python 3.6+
- libusb
- pyusb, Pillow

### Cài đặt (macOS)
```bash
brew install libusb
pip install pyusb Pillow
```

### Sử dụng CLI
```bash
# Xem thông tin device
sudo python3 fingerprint.py info

# Capture ảnh vân tay (chờ đến khi có ngón tay)
sudo python3 fingerprint.py capture fingerprint.png

# Điều khiển LED
sudo python3 fingerprint.py led red
sudo python3 fingerprint.py led green
sudo python3 fingerprint.py led off

# Thêm vân tay mới
sudo python3 fingerprint.py add

# Nhận dạng vân tay
sudo python3 fingerprint.py match

# Xóa vân tay
sudo python3 fingerprint.py delete 1      # Xóa user ID 1
sudo python3 fingerprint.py delete all    # Xóa tất cả
```

---

## 🐍 Python SDK

### Thông tin thiết bị
| Thuộc tính | Giá trị |
|------------|---------|
| VID | 0x0483 (STMicroelectronics) |
| PID | 0x5720 |
| Giao thức | SCSI Vendor Commands over USB Mass Storage |
| Ảnh | 192x192 grayscale (36,864 bytes) |
| Max users | 1000 |

### API Class

```python
from fingerprint import FingerprintReader, LED

# Khởi tạo (macOS)
fp = FingerprintReader(libusb_path='/opt/homebrew/lib/libusb-1.0.dylib')
fp.open()

# LED control
fp.led_on(LED.GREEN)
fp.led_on(LED.RED)
fp.led_on(LED.BLUE)
fp.led_on(LED.WHITE)
fp.led_off()

# Capture ảnh vân tay
image = fp.capture_image()  # bytes 192x192

# Kiểm tra có ngón tay không (phân tích variance)
if fp.check_finger():
    print("Có ngón tay trên sensor")

# Thông tin
print(f"Users: {fp.get_user_count()}")
print(f"Level: {fp.get_compare_level()}")

# Thêm vân tay mới
success, user_id = fp.add_user()

# Nhận dạng vân tay
matched, user_id = fp.match_fingerprint(timeout_sec=5.0)

# Xóa vân tay
fp.delete_user(user_id)
fp.delete_all()

# Đóng kết nối
fp.close()
```

### Finger Detection
SDK sử dụng phân tích **variance** của image data để phát hiện ngón tay:
- **StdDev > 10:** Có ngón tay (ảnh có nhiều variation)
- **StdDev < 10:** Sensor trống (ảnh đồng nhất ~132)

```python
# Internal logic
avg = sum(image) / len(image)
variance = sum((x - avg) ** 2 for x in image) / len(image)
std_dev = variance ** 0.5
has_finger = std_dev > 10.0
```

---

## 🔌 Giao thức USB

### SCSI Vendor Commands
Device giả lập USB Mass Storage nhưng sử dụng vendor SCSI commands:

| Opcode | Chức năng | Direction |
|--------|-----------|-----------|
| `0x85` | READ data | Device → Host |
| `0x86` | WRITE data | Host → Device |

### CDB Format (10 bytes)
```
[opcode] 00 [len3] [len2] [len1] [len0] 00 02 00 00
```
- `len3-len0`: Data length (big-endian)

### Fingerprint Packet Format
```
| HEAD | P1 | CMD | P2 | P3 | P4 | CheckSum | TAIL |
| 0xF6 | 1B | 1B  | 1B | 1B | 1B | SUM      | 0xF6 |
```
- **HEAD/TAIL:** 0xF6 (USB) hoặc 0xF5 (UART)
- **CheckSum:** (CMD + P1 + P2 + P3 + P4) & 0xFF

### Commands

| Mã | Tên | Mô tả |
|----|-----|-------|
| `0x01` | ADD_1 | Đăng ký bước 1 |
| `0x02` | ADD_2 | Đăng ký bước 2 |
| `0x03` | ADD_3 | Đăng ký bước 3 |
| `0x04` | DEL | Xóa 1 user |
| `0x05` | DEL_ALL | Xóa tất cả |
| `0x09` | USER_CNT | Đếm users |
| `0x0C` | MATCH | So khớp |
| `0x21` | CHECK_FINGER | Kiểm tra ngón tay |
| `0x24` | GET_IMAGE | Lấy ảnh 192x192 |
| `0x28` | COMPARE_LEVEL | Mức so sánh (0-9) |
| `0x5E` | LED | Điều khiển LED |

### LED Colors

| Giá trị | Màu |
|---------|-----|
| `0x00` | OFF |
| `0x01` | RED |
| `0x02` | GREEN |
| `0x04` | BLUE |
| `0x07` | WHITE |

### Image Capture Flow
1. Send `GET_IMAGE` (0x24) command
2. Read 8-byte response header
3. Read first half: `(size/2 + 1)` bytes, skip first byte
4. Read second half: `(size/2 + 2)` bytes, skip first byte
5. Combine → 36,864 bytes (192x192 grayscale)

### Response Codes

| Mã | Tên | Ý nghĩa |
|----|-----|---------|
| `0x00` | SUCCESS | Thành công |
| `0x01` | FAIL | Thất bại |
| `0x04` | FULL | Đầy (max 1000) |
| `0x05` | NO_USER | Không tìm thấy |
| `0x08` | TIMEOUT | Hết thời gian |

---

## 📨 Giao thức UART

Cho embedded platforms (Arduino, Raspberry Pi, STM32):

### Frame Format
```
| HEAD | CMD | P1 | P2 | P3 | P4 | CheckSum | TAIL |
| 0xF5 | 1B  | 1B | 1B | 1B | 1B | XOR      | 0xF5 |
```

**CheckSum** = XOR của CMD + P1 + P2 + P3 + P4

**Baud rate:** 19200

---

## 📁 Cấu trúc dự án

| Thư mục | Mô tả |
|---------|-------|
| `fingerprint.py` | **Cross-platform Python SDK** |
| `Capacitive-Fingerprint-Reader (USB)/` | Windows Demo App (MFC) |
| `Capacitive-Fingerprint-Reader-Code/` | Embedded demo code (Arduino, RPi, STM32) |

---

## 🔗 Tham khảo

- [Waveshare Wiki](https://www.waveshare.com/wiki/Capacitive_Fingerprint_Reader)
- Windows SDK: `Capacitive-Fingerprint-Reader (USB)/D5ScannerS78.h`
- Protocol reverse-engineered from `D5ScannerS78.dll`

---

*Cập nhật: Tháng 1, 2026*
