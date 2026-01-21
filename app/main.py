#!/usr/bin/env python3
"""
Fingerprint Framework - Main Application Entry Point
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix libusb backend for macOS - set before importing usb
if sys.platform == 'darwin':
    homebrew_lib = '/opt/homebrew/lib'
    if os.path.exists(homebrew_lib):
        # For ctypes to find libusb
        os.environ.setdefault('DYLD_LIBRARY_PATH', homebrew_lib)
        # Also set the backend directly for pyusb
        import usb.backend.libusb1 as libusb1
        import ctypes
        try:
            libusb1._lib = ctypes.CDLL(os.path.join(homebrew_lib, 'libusb-1.0.dylib'))
        except:
            pass

# Disable color emoji to prevent CoreText crash on macOS
os.environ['QT_HARFBUZZ'] = 'old'

# Fix Qt plugin path for sudo on macOS
if sys.platform == 'darwin' and 'QT_QPA_PLATFORM_PLUGIN_PATH' not in os.environ:
    import importlib.util
    spec = importlib.util.find_spec('PyQt6')
    if spec and spec.origin:
        plugin_path = os.path.join(os.path.dirname(spec.origin), 'Qt6', 'plugins')
        if os.path.exists(plugin_path):
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path

from PyQt6.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtCore import Qt


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Set a safe system font to avoid emoji rendering crashes
    if sys.platform == 'darwin':
        font = QFont("Helvetica Neue", 13)
        font.setStyleStrategy(QFont.StyleStrategy.NoFontMerging)
        app.setFont(font)

    # Apply stylesheet
    app.setStyleSheet("""
        QMainWindow {
            background-color: #fafafa;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #ddd;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QPushButton {
            padding: 8px 16px;
            border-radius: 4px;
            border: 1px solid #ccc;
            background-color: #fff;
        }
        QPushButton:hover {
            background-color: #f0f0f0;
        }
        QPushButton:pressed {
            background-color: #e0e0e0;
        }
        QLineEdit {
            padding: 8px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }
        QComboBox {
            padding: 6px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }
        QTableWidget {
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        QTabWidget::pane {
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        QTabBar::tab {
            padding: 8px 16px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background-color: #fff;
            border-bottom: 2px solid #2196F3;
        }
    """)

    try:
        # Import after QApplication is created
        from fingerprint import FingerprintReader, LED
        from core.services.fingerprint_service import FingerprintService
        from ui.main_window import MainWindow
        from app.config import APP_NAME

        # Initialize sensor
        sensor = FingerprintReader()

        if not sensor.open():
            QMessageBox.critical(
                None, "Device Error",
                "Fingerprint sensor not found!\n\n"
                "Please check:\n"
                "1. Device is connected via USB\n"
                "2. You have permission (try running with sudo)\n"
                "3. libusb is installed"
            )
            return 1

        # Create service
        service = FingerprintService(sensor)

        # Create and show main window
        window = MainWindow(service)
        window.show()

        # Run application
        result = app.exec()

        # Force cleanup of any running workers
        app.processEvents()
        
        # Cleanup
        sensor.close()

        return result

    except ImportError as e:
        QMessageBox.critical(
            None, "Import Error",
            f"Failed to import required modules:\n{e}\n\n"
            "Please install dependencies:\n"
            "pip install PyQt6 pyusb"
        )
        return 1

    except Exception as e:
        QMessageBox.critical(
            None, "Error",
            f"An error occurred:\n{e}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
