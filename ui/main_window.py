"""
Main Window - Application shell
"""
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QMessageBox, QStatusBar,
    QMenuBar, QMenu
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from core.services.fingerprint_service import FingerprintService
from ui.widgets import (
    LiveViewTab, EnrollmentTab, MatchingTab, DatabaseTab, AITab
)
from app.config import APP_NAME, APP_VERSION


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self, service: FingerprintService):
        super().__init__()
        self._service = service

        self._setup_ui()
        self._setup_menu()
        self._setup_status_bar()

    def _setup_ui(self):
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(600, 700)
        self.resize(700, 800)

        # Tab widget
        self._tabs = QTabWidget()

        # Create tabs
        self._live_view_tab = LiveViewTab(self._service)
        self._enrollment_tab = EnrollmentTab(self._service)
        self._matching_tab = MatchingTab(self._service)
        self._database_tab = DatabaseTab(self._service)
        self._ai_tab = AITab(self._service)

        # Add tabs
        self._tabs.addTab(self._live_view_tab, "Live View")
        self._tabs.addTab(self._enrollment_tab, "Enrollment")
        self._tabs.addTab(self._matching_tab, "Matching")
        self._tabs.addTab(self._database_tab, "Database")
        self._tabs.addTab(self._ai_tab, "AI")

        self.setCentralWidget(self._tabs)

    def _setup_menu(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        export_action = QAction("Export Database...", self)
        export_action.triggered.connect(self._export_database)
        file_menu.addAction(export_action)

        import_action = QAction("Import FEA...", self)
        import_action.triggered.connect(self._import_fea)
        file_menu.addAction(import_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Device menu
        device_menu = menubar.addMenu("Device")

        info_action = QAction("Device Info", self)
        info_action.triggered.connect(self._show_device_info)
        device_menu.addAction(info_action)

        device_menu.addSeparator()

        led_menu = device_menu.addMenu("LED Control")
        for color, code in [("Off", 0), ("Red", 1), ("Green", 2), ("Blue", 4), ("White", 7)]:
            action = QAction(color, self)
            action.triggered.connect(lambda checked, c=code: self._set_led(c))
            led_menu.addAction(action)

        beep_action = QAction("Beep", self)
        beep_action.triggered.connect(lambda: self._service.beep(100))
        device_menu.addAction(beep_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_status_bar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        # Show device status
        user_count = self._service.get_device_user_count()
        self._status_bar.showMessage(
            f"Device connected | Users: {user_count}"
        )

    def _export_database(self):
        # Switch to database tab
        self._tabs.setCurrentWidget(self._database_tab)
        self._database_tab._export_fea()

    def _import_fea(self):
        # Switch to database tab
        self._tabs.setCurrentWidget(self._database_tab)
        self._database_tab._import_fea()

    def _show_device_info(self):
        try:
            user_count = self._service.get_device_user_count()
            db_count = self._service.database.get_user_count()

            QMessageBox.information(
                self, "Device Information",
                f"<b>USB Fingerprint Reader</b><br>"
                f"VID: 0x0483<br>"
                f"PID: 0x5720<br>"
                f"<br>"
                f"<b>Statistics:</b><br>"
                f"Device Users: {user_count}<br>"
                f"Database Users: {db_count}<br>"
                f"<br>"
                f"<b>Matching Engine:</b><br>"
                f"{self._service.matching_engine.name}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _set_led(self, color_code: int):
        if color_code == 0:
            self._service.led_off()
        else:
            self._service.led_on(color_code)

    def _show_about(self):
        QMessageBox.about(
            self, "About",
            f"<h3>{APP_NAME}</h3>"
            f"<p>Version {APP_VERSION}</p>"
            f"<p>A framework for fingerprint enrollment, matching, "
            f"and AI-based recognition.</p>"
            f"<p>Features:</p>"
            f"<ul>"
            f"<li>Live fingerprint streaming</li>"
            f"<li>User enrollment with BMP export</li>"
            f"<li>Device and AI-based matching</li>"
            f"<li>FEA file import/export</li>"
            f"</ul>"
        )

    def closeEvent(self, event):
        """Handle window close"""
        # Stop any running workers with proper cleanup
        try:
            if hasattr(self._live_view_tab, '_worker') and self._live_view_tab._worker:
                self._live_view_tab._worker.stop()
                self._live_view_tab._worker = None
        except:
            pass

        try:
            if hasattr(self._enrollment_tab, '_worker') and self._enrollment_tab._worker:
                self._enrollment_tab._worker.stop()
                self._enrollment_tab._worker = None
        except:
            pass

        try:
            if hasattr(self._matching_tab, '_worker') and self._matching_tab._worker:
                self._matching_tab._worker.stop()
                self._matching_tab._worker = None
        except:
            pass

        # Turn off LED
        try:
            self._service.led_off()
        except:
            pass

        event.accept()
