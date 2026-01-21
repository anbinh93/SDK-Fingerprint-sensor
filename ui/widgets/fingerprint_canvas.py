"""
Fingerprint Canvas - Reusable image display widget
"""
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PyQt6.QtGui import QImage, QPixmap, QPainter, QFont, QColor
from PyQt6.QtCore import Qt

from app.config import IMAGE_WIDTH, IMAGE_HEIGHT, QUALITY_THRESHOLD


class FingerprintCanvas(QWidget):
    """Widget for displaying fingerprint images with quality overlay"""

    def __init__(self, parent=None, size: int = 250):
        super().__init__(parent)
        self._size = size
        self._image_data = None
        self._quality_score = 0.0
        self._show_quality = True
        self._has_finger = False

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._image_label = QLabel()
        self._image_label.setFixedSize(self._size, self._size)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setStyleSheet("""
            QLabel {
                border: 2px solid #ccc;
                border-radius: 8px;
                background-color: #f0f0f0;
            }
        """)

        layout.addWidget(self._image_label)

        # Set placeholder
        self._show_placeholder()

    def _show_placeholder(self):
        """Show placeholder when no image"""
        pixmap = QPixmap(self._size, self._size)
        pixmap.fill(QColor("#f0f0f0"))

        painter = QPainter(pixmap)
        painter.setPen(QColor("#999"))
        font = QFont()
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(
            pixmap.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "No Image"
        )
        painter.end()

        self._image_label.setPixmap(pixmap)

    def set_image(self, image_data: bytes, quality: float = 0.0, has_finger: bool = False):
        """
        Set fingerprint image.

        Args:
            image_data: Raw 192x192 grayscale bytes
            quality: Quality score (StdDev)
            has_finger: Whether finger is detected
        """
        self._image_data = image_data
        self._quality_score = quality
        self._has_finger = has_finger

        if not image_data or len(image_data) < IMAGE_WIDTH * IMAGE_HEIGHT:
            self._show_placeholder()
            return

        # Create QImage from raw bytes
        qimage = QImage(
            image_data[:IMAGE_WIDTH * IMAGE_HEIGHT],
            IMAGE_WIDTH,
            IMAGE_HEIGHT,
            IMAGE_WIDTH,
            QImage.Format.Format_Grayscale8
        )

        # Scale to display size
        pixmap = QPixmap.fromImage(qimage).scaled(
            self._size, self._size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # Draw quality overlay if enabled
        if self._show_quality:
            painter = QPainter(pixmap)

            # Quality indicator color
            if has_finger and quality > QUALITY_THRESHOLD:
                color = QColor("#4CAF50")  # Green
            elif has_finger:
                color = QColor("#FFC107")  # Yellow
            else:
                color = QColor("#F44336")  # Red

            # Draw quality bar background
            bar_width = int(pixmap.width() * 0.8)
            bar_height = 8
            bar_x = (pixmap.width() - bar_width) // 2
            bar_y = pixmap.height() - 20

            painter.fillRect(bar_x, bar_y, bar_width, bar_height, QColor("#ddd"))

            # Draw quality bar fill
            fill_width = int(bar_width * min(quality / 50.0, 1.0))  # Normalize to 50 max
            painter.fillRect(bar_x, bar_y, fill_width, bar_height, color)

            # Draw quality text
            painter.setPen(QColor("white"))
            font = QFont()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)

            # Draw text with shadow for visibility
            text = f"Q: {quality:.1f}"
            text_rect = pixmap.rect().adjusted(0, 0, 0, -30)

            # Shadow
            painter.setPen(QColor("black"))
            painter.drawText(text_rect.adjusted(1, 1, 1, 1),
                           Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                           text)
            # Text
            painter.setPen(QColor("white"))
            painter.drawText(text_rect,
                           Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                           text)

            painter.end()

        self._image_label.setPixmap(pixmap)

        # Update border color based on detection
        if has_finger:
            self._image_label.setStyleSheet("""
                QLabel {
                    border: 3px solid #4CAF50;
                    border-radius: 8px;
                    background-color: #f0f0f0;
                }
            """)
        else:
            self._image_label.setStyleSheet("""
                QLabel {
                    border: 2px solid #ccc;
                    border-radius: 8px;
                    background-color: #f0f0f0;
                }
            """)

    def clear(self):
        """Clear the canvas"""
        self._image_data = None
        self._quality_score = 0.0
        self._has_finger = False
        self._show_placeholder()

    def set_show_quality(self, show: bool):
        """Enable/disable quality overlay"""
        self._show_quality = show
        if self._image_data:
            self.set_image(self._image_data, self._quality_score, self._has_finger)

    @property
    def image_data(self) -> bytes:
        return self._image_data

    @property
    def quality_score(self) -> float:
        return self._quality_score

    @property
    def has_finger(self) -> bool:
        return self._has_finger
