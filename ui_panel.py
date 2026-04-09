from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QWidget


class Panel(QWidget):
    """Custom QWidget representing a semi-transparent, rounded panel with a border."""
    
    def paintEvent(self, event):
        """Handle the paint event to draw the panel background and border.

        The panel is drawn with a dark semi-transparent fill and a light semi-transparent outline,
        using anti-aliasing for smooth edges.
        """
        
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(12, 14, 20, 225))
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 8, 8)
