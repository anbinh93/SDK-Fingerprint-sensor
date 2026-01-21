"""
Application Configuration
"""
import os
from pathlib import Path

# Application Info
APP_NAME = "Fingerprint Framework"
APP_VERSION = "1.0.0"

# Paths
APP_DIR = Path(__file__).parent.parent
DATA_DIR = APP_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
DATABASE_PATH = DATA_DIR / "fingerprint.db"

# Ensure directories exist
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Sensor Configuration
SENSOR_VID = 0x0483
SENSOR_PID = 0x5720
IMAGE_WIDTH = 192
IMAGE_HEIGHT = 192
IMAGE_SIZE = IMAGE_WIDTH * IMAGE_HEIGHT

# Live Streaming
DEFAULT_FPS = 5
MIN_FPS = 1
MAX_FPS = 15

# Quality Detection
QUALITY_THRESHOLD = 10.0  # StdDev threshold for finger detection

# Matching
DEFAULT_COMPARE_LEVEL = 5  # 0-9, higher is stricter
MATCH_TIMEOUT_SEC = 10.0

# Database
MAX_USERS = 1000

# FEA Format
FEA_VERSION = "1.0"
