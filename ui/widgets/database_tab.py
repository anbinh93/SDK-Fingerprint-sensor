"""
Database Tab - User management
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QHeaderView,
    QMessageBox, QFileDialog, QInputDialog
)
from PyQt6.QtCore import Qt

from core.services.fingerprint_service import FingerprintService
from core.models import User


class DatabaseTab(QWidget):
    """Tab for database management"""

    def __init__(self, service: FingerprintService, parent=None):
        super().__init__(parent)
        self._service = service

        self._setup_ui()
        self._load_users()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Stats group
        stats_group = QGroupBox("Statistics")
        stats_layout = QHBoxLayout(stats_group)

        self._db_count_label = QPushButton("Database: 0 users")
        self._db_count_label.setFlat(True)

        self._device_count_label = QPushButton("Device: 0 users")
        self._device_count_label.setFlat(True)

        self._refresh_btn = QPushButton("↻ Refresh")
        self._refresh_btn.clicked.connect(self._load_users)

        stats_layout.addWidget(self._db_count_label)
        stats_layout.addWidget(self._device_count_label)
        stats_layout.addStretch()
        stats_layout.addWidget(self._refresh_btn)

        layout.addWidget(stats_group)

        # Table group
        table_group = QGroupBox("Registered Users")
        table_layout = QVBoxLayout(table_group)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            "ID", "Device ID", "Username", "Fingerprints", "Created"
        ])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        # Column widths
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 50)
        self._table.setColumnWidth(1, 80)
        self._table.setColumnWidth(3, 100)
        self._table.setColumnWidth(4, 150)

        table_layout.addWidget(self._table)
        layout.addWidget(table_group)

        # Buttons
        btn_layout = QHBoxLayout()

        self._add_btn = QPushButton("Add User (Manual)")
        self._add_btn.clicked.connect(self._add_user_manual)

        self._edit_btn = QPushButton("Edit")
        self._edit_btn.clicked.connect(self._edit_user)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setStyleSheet("background-color: #F44336; color: white;")
        self._delete_btn.clicked.connect(self._delete_user)

        self._export_btn = QPushButton("Export FEA")
        self._export_btn.clicked.connect(self._export_fea)

        self._import_btn = QPushButton("Import FEA")
        self._import_btn.clicked.connect(self._import_fea)

        self._delete_all_btn = QPushButton("Delete All")
        self._delete_all_btn.setStyleSheet("background-color: #B71C1C; color: white;")
        self._delete_all_btn.clicked.connect(self._delete_all)

        btn_layout.addWidget(self._add_btn)
        btn_layout.addWidget(self._edit_btn)
        btn_layout.addWidget(self._delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self._export_btn)
        btn_layout.addWidget(self._import_btn)
        btn_layout.addWidget(self._delete_all_btn)

        layout.addLayout(btn_layout)

    def _load_users(self):
        """Load users from database"""
        users = self._service.database.get_all_users()

        self._table.setRowCount(len(users))

        for row, user in enumerate(users):
            fp_count = self._service.database.get_fingerprint_count(user.id)

            self._table.setItem(row, 0, QTableWidgetItem(str(user.id)))
            self._table.setItem(row, 1, QTableWidgetItem(str(user.device_user_id)))
            self._table.setItem(row, 2, QTableWidgetItem(user.username))
            self._table.setItem(row, 3, QTableWidgetItem(str(fp_count)))
            self._table.setItem(row, 4, QTableWidgetItem(
                user.created_at.strftime("%Y-%m-%d %H:%M")
            ))

            # Store user object in first column
            self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, user)

        # Update stats
        db_count = len(users)
        device_count = self._service.get_device_user_count()

        self._db_count_label.setText(f"Database: {db_count} users")
        self._device_count_label.setText(f"Device: {device_count} users")

    def _get_selected_user(self) -> User:
        """Get selected user from table"""
        row = self._table.currentRow()
        if row < 0:
            return None

        item = self._table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _add_user_manual(self):
        """Add user without enrollment (database only)"""
        text, ok = QInputDialog.getText(
            self, "Add User", "Enter username:"
        )
        if ok and text:
            device_id = self._service.database.get_next_device_id()
            self._service.database.add_user(text.strip(), device_id)
            self._load_users()
            QMessageBox.information(
                self, "Success",
                f"User '{text}' added to database.\nNote: Fingerprint not enrolled on device."
            )

    def _edit_user(self):
        """Edit selected user"""
        user = self._get_selected_user()
        if not user:
            QMessageBox.warning(self, "Warning", "Please select a user")
            return

        text, ok = QInputDialog.getText(
            self, "Edit User", "Enter new username:",
            text=user.username
        )
        if ok and text:
            user.username = text.strip()
            self._service.database.update_user(user)
            self._load_users()

    def _delete_user(self):
        """Delete selected user"""
        user = self._get_selected_user()
        if not user:
            QMessageBox.warning(self, "Warning", "Please select a user")
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete user '{user.username}'?\nThis will also delete from device.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            success, error = self._service.delete_user(user.id)
            if success:
                self._load_users()
            else:
                QMessageBox.critical(self, "Error", error)

    def _delete_all(self):
        """Delete all users"""
        reply = QMessageBox.question(
            self, "Confirm Delete All",
            "Delete ALL users from database and device?\nThis cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            success, error = self._service.delete_all_users()
            if success:
                self._load_users()
                QMessageBox.information(self, "Success", "All users deleted")
            else:
                QMessageBox.critical(self, "Error", error)

    def _export_fea(self):
        """Export selected user to FEA file"""
        user = self._get_selected_user()
        if not user:
            QMessageBox.warning(self, "Warning", "Please select a user")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export FEA",
            f"{user.username}.fea",
            "FEA Files (*.fea)"
        )

        if filepath:
            # Get fingerprint image if available
            fingerprints = self._service.database.get_fingerprints(user.id)
            image = b''
            quality = 0.0

            if fingerprints and fingerprints[0].image_path:
                # Read image from file
                try:
                    with open(fingerprints[0].image_path, 'rb') as f:
                        # Skip BMP header if present
                        data = f.read()
                        if data[:2] == b'BM':
                            image = data[1078:]  # Skip BMP header + palette
                        else:
                            image = data
                    quality = fingerprints[0].quality_score
                except Exception:
                    pass

            success = self._service.fea.export_to_fea(
                user, image, filepath, quality
            )

            if success:
                QMessageBox.information(self, "Success", f"Exported to {filepath}")
            else:
                QMessageBox.critical(self, "Error", "Failed to export")

    def _import_fea(self):
        """Import user from FEA file"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Import FEA",
            "",
            "FEA Files (*.fea)"
        )

        if filepath:
            fea = self._service.fea.import_from_fea(filepath)
            if fea:
                # Add user to database
                device_id = self._service.database.get_next_device_id()
                self._service.database.add_user(fea.username, device_id)
                self._load_users()
                QMessageBox.information(
                    self, "Success",
                    f"Imported user '{fea.username}'\nNote: Fingerprint not enrolled on device."
                )
            else:
                QMessageBox.critical(self, "Error", "Failed to import FEA file")
