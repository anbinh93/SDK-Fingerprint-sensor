"""
AI Tab - AI matching engine configuration
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QComboBox, QGroupBox, QSlider,
    QMessageBox, QFileDialog, QTextEdit
)
from PyQt6.QtCore import Qt

from core.services.fingerprint_service import FingerprintService
from core.services.matching_engine import EngineType, MatchingEngineFactory


class AITab(QWidget):
    """Tab for AI matching engine configuration"""

    def __init__(self, service: FingerprintService, parent=None):
        super().__init__(parent)
        self._service = service

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Engine selection group
        engine_group = QGroupBox("Matching Engine")
        engine_layout = QVBoxLayout(engine_group)

        # Current engine
        current_layout = QHBoxLayout()
        current_layout.addWidget(QLabel("Current Engine:"))
        self._current_engine_label = QLabel(self._service.matching_engine.name)
        self._current_engine_label.setStyleSheet("font-weight: bold;")
        current_layout.addWidget(self._current_engine_label)
        current_layout.addStretch()
        engine_layout.addLayout(current_layout)

        # Engine selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Select Engine:"))
        self._engine_combo = QComboBox()
        self._engine_combo.addItems(["Device Hardware", "ONNX Runtime"])
        selector_layout.addWidget(self._engine_combo)

        self._apply_engine_btn = QPushButton("Apply")
        self._apply_engine_btn.clicked.connect(self._apply_engine)
        selector_layout.addWidget(self._apply_engine_btn)

        engine_layout.addLayout(selector_layout)
        layout.addWidget(engine_group)

        # ONNX Settings group
        onnx_group = QGroupBox("ONNX Runtime Settings")
        onnx_layout = QVBoxLayout(onnx_group)

        # Model path
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model Path:"))
        self._model_path_input = QLineEdit()
        self._model_path_input.setPlaceholderText("Select ONNX model file...")
        model_layout.addWidget(self._model_path_input)
        self._browse_btn = QPushButton("Browse")
        self._browse_btn.clicked.connect(self._browse_model)
        model_layout.addWidget(self._browse_btn)
        onnx_layout.addLayout(model_layout)

        # Confidence threshold
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("Confidence Threshold:"))
        self._threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self._threshold_slider.setRange(50, 95)
        self._threshold_slider.setValue(70)
        self._threshold_slider.valueChanged.connect(self._on_threshold_changed)
        threshold_layout.addWidget(self._threshold_slider)
        self._threshold_label = QLabel("0.70")
        threshold_layout.addWidget(self._threshold_label)
        onnx_layout.addLayout(threshold_layout)

        # Load model button
        self._load_model_btn = QPushButton("Load Model")
        self._load_model_btn.clicked.connect(self._load_model)
        onnx_layout.addWidget(self._load_model_btn)

        layout.addWidget(onnx_group)

        # Info group
        info_group = QGroupBox("Information")
        info_layout = QVBoxLayout(info_group)

        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(150)
        info_text.setHtml("""
        <h4>Matching Engines</h4>
        <p><b>Device Hardware:</b> Uses the sensor's built-in matching algorithm.
        Fast and reliable, works offline.</p>
        <p><b>ONNX Runtime:</b> Uses a custom AI model for matching.
        Requires a trained ONNX model file. More flexible but requires setup.</p>

        <h4>ONNX Model Requirements</h4>
        <ul>
        <li>Input: 192x192 grayscale image (normalized to 0-1)</li>
        <li>Output: Feature embedding vector</li>
        <li>Format: ONNX opset 11+</li>
        </ul>
        """)
        info_layout.addWidget(info_text)

        layout.addWidget(info_group)
        layout.addStretch()

    def _apply_engine(self):
        """Apply selected matching engine"""
        engine_name = self._engine_combo.currentText()

        try:
            if engine_name == "Device Hardware":
                engine = MatchingEngineFactory.create(
                    EngineType.DEVICE,
                    sensor=self._service.sensor.sensor
                )
            else:
                model_path = self._model_path_input.text().strip() or None
                engine = MatchingEngineFactory.create(
                    EngineType.ONNX,
                    model_path=model_path
                )

            self._service.set_matching_engine(engine)
            self._current_engine_label.setText(engine.name)

            QMessageBox.information(
                self, "Success",
                f"Switched to {engine.name}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _browse_model(self):
        """Browse for ONNX model file"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select ONNX Model",
            "",
            "ONNX Models (*.onnx)"
        )
        if filepath:
            self._model_path_input.setText(filepath)

    def _load_model(self):
        """Load ONNX model"""
        model_path = self._model_path_input.text().strip()
        if not model_path:
            QMessageBox.warning(self, "Warning", "Please select a model file")
            return

        try:
            engine = MatchingEngineFactory.create(
                EngineType.ONNX,
                model_path=model_path
            )

            if engine.is_available():
                self._service.set_matching_engine(engine)
                self._current_engine_label.setText(engine.name)
                QMessageBox.information(self, "Success", "Model loaded successfully")
            else:
                QMessageBox.critical(self, "Error", "Failed to load model")

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_threshold_changed(self, value: int):
        """Update threshold label"""
        self._threshold_label.setText(f"{value / 100:.2f}")
