import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QWidget

from app_functions import pixel_to_world, world_to_pixel
from app_settings import (
    CALIB_DOT_SIZE,
    CAL_SNAP_ZOOM,
    DOT_SIZE,
    LOCK_ZOOM_CAL,
    LOWER_LAYER_OPACITY,
    MAX_ZOOM,
    MIN_ZOOM,
    PIN_H,
    PIN_W,
    PULSE_EXTENT,
    PULSE_RINGS,
    PULSE_SPEED,
    TOP_BAR_HEIGHT,
    ZOOM_STEP,
    theme_q,
)


class MapCanvas(QWidget):
    """Canvas widget for rendering the map, including layers, calibration points, markers, pins, and the player location."""

    def __init__(self, overlay):
        """Initialize the MapCanvas with a reference to the overlay object."""
        super().__init__(overlay)
        self.ov = overlay
        self.setMouseTracking(True)

    def paintEvent(self, event):
        """Handle the paint event to render all map components including layers, calibration points, markers, pins, and mode bar."""
        ov = self.ov
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setRenderHint(QPainter.Antialiasing)

        layers = ov.map_layers
        visible = ov.layer_visible
        top_idx = -1
        for i in range(len(layers) - 1, -1, -1):
            if visible[i] and not layers[i].isNull():
                top_idx = i
                break

        for i, pix in enumerate(layers):
            if not visible[i] or pix.isNull():
                continue
            opacity = 1.0 if i == top_idx else LOWER_LAYER_OPACITY
            p.setOpacity(opacity)
            mw = pix.width() * ov.zoom
            mh = pix.height() * ov.zoom
            p.drawPixmap(int(ov.offset_x), int(ov.offset_y), int(mw), int(mh), pix)

        p.setOpacity(1.0)
        p.setFont(QFont("Consolas", 12, QFont.Bold))
        cal_stroke = theme_q("cal_stroke", QColor(0, 0, 0))
        cal_fill = theme_q("cal_fill", QColor(255, 255, 255, 220))
        cal_label = theme_q("cal_label", QColor(255, 255, 180))
        cal_edit_s = theme_q("cal_edit_stroke", QColor(255, 220, 0))
        cal_edit_f = theme_q("cal_edit_fill", QColor(255, 240, 100, 220))
        lbl_shadow = QColor(0, 0, 0)

        if ov.show_cal_points:
            for idx, (img_x, img_y, map_x, map_y) in enumerate(ov.calibration_points):
                sx = img_x * ov.zoom + ov.offset_x
                sy = img_y * ov.zoom + ov.offset_y
                if ov.edit_mode and ov.edit_type == "cal" and ov.edit_index == idx:
                    p.setPen(QPen(cal_edit_s, 3))
                    p.setBrush(cal_edit_f)
                else:
                    p.setPen(QPen(cal_stroke, 2))
                    p.setBrush(cal_fill)
                p.drawEllipse(int(sx) - CALIB_DOT_SIZE // 2, int(sy) - CALIB_DOT_SIZE // 2, CALIB_DOT_SIZE, CALIB_DOT_SIZE)
                lx, ly = int(sx) + CALIB_DOT_SIZE // 2 + 3, int(sy) + 5
                p.setPen(lbl_shadow)
                p.drawText(lx + 1, ly + 1, str(idx + 1))
                p.setPen(cal_label)
                p.drawText(lx, ly, str(idx + 1))

        if ov.last_click_px:
            cpx, cpy = ov.last_click_px
            sx = cpx * ov.zoom + ov.offset_x
            sy = cpy * ov.zoom + ov.offset_y
            ping_c = theme_q("ping_cross", QColor(255, 180, 0))
            ping_o = theme_q("ping_circle", QColor(255, 180, 0))
            p.setPen(QPen(ping_c, 2))
            p.setBrush(Qt.NoBrush)
            r = 10
            p.drawLine(int(sx) - r, int(sy), int(sx) + r, int(sy))
            p.drawLine(int(sx), int(sy) - r, int(sx), int(sy) + r)
            p.setPen(QPen(ping_o, 2))
            p.drawEllipse(int(sx) - r, int(sy) - r, r * 2, r * 2)

        mf = theme_q("marker_fill", QColor(46, 232, 200, 200))
        mr = theme_q("marker_ring", QColor(0, 168, 140))
        mlab = theme_q("marker_label", QColor(176, 255, 240))
        ms = max(8, DOT_SIZE - 2)
        if ov.show_markers:
            for m in ov.named_markers:
                try:
                    map_y = float(m["wy"])
                    ipx, ipy = world_to_pixel(float(m["wx"]), map_y, ov.xc, ov.yc)
                    if not (math.isfinite(ipx) and math.isfinite(ipy)):
                        continue
                except (KeyError, ValueError):
                    continue
                sx = ipx * ov.zoom + ov.offset_x
                sy = ipy * ov.zoom + ov.offset_y
                p.setPen(QPen(mr, 2))
                p.setBrush(mf)
                p.drawEllipse(int(sx) - ms, int(sy) - ms, ms * 2, ms * 2)
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(int(sx) - ms - 3, int(sy) - ms - 3, ms * 2 + 6, ms * 2 + 6)
                nm = m.get("name") or "Marker"
                p.setPen(lbl_shadow)
                p.drawText(int(sx) - 40, int(sy) - ms - 5, f"{nm}")
                p.setPen(mlab)
                p.drawText(int(sx) - 40, int(sy) - ms - 6, f"{nm}")

        if ov.show_pins:
            for i, pin in enumerate(ov.drop_pins):
                highlight = ov.edit_mode and ov.edit_type == "pin" and ov.edit_index == i
                self._draw_pin(p, pin["px"], pin["py"], pin["name"], highlight=highlight)

        if ov.current_loc is not None:
            ipx, ipy = world_to_pixel(ov.current_loc[0], ov.current_loc[1], ov.xc, ov.yc)
            if math.isfinite(ipx) and math.isfinite(ipy):
                sx = ipx * ov.zoom + ov.offset_x
                sy = ipy * ov.zoom + ov.offset_y
                pl_outer = theme_q("player_outer_ring", QColor(255, 80, 80, 130))
                pl_ring = theme_q("player_ring", QColor(180, 0, 0))
                pl_fill = theme_q("player_fill", QColor(255, 50, 50))
                p.setPen(QPen(pl_outer, 3))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(int(sx) - DOT_SIZE, int(sy) - DOT_SIZE, DOT_SIZE * 2, DOT_SIZE * 2)
                ph = getattr(ov, "pulse_phase", 0.0)
                for k in range(max(0, PULSE_RINGS)):
                    t = ph + k * (math.pi / 2.2)
                    wave = 0.5 * (1.0 + math.sin(t * PULSE_SPEED))
                    rad = DOT_SIZE + 6 + k * 10 + wave * DOT_SIZE * PULSE_EXTENT
                    ring_c = QColor(pl_outer)
                    ring_c.setAlpha(int(30 + 120 * (1.0 - wave)))
                    p.setPen(QPen(ring_c, 2))
                    p.drawEllipse(int(sx - rad), int(sy - rad), int(rad * 2), int(rad * 2))
                p.setPen(QPen(pl_ring, 1))
                p.setBrush(pl_fill)
                p.drawEllipse(int(sx) - DOT_SIZE // 2, int(sy) - DOT_SIZE // 2, DOT_SIZE, DOT_SIZE)

        if ov.edit_mode:
            p.fillRect(0, TOP_BAR_HEIGHT, self.width(), 28, QColor(20, 120, 80, 210))
            p.setPen(QColor(160, 255, 200))
            p.setFont(QFont("Consolas", 10, QFont.Bold))
            kind = "calibration point" if ov.edit_type == "cal" else "pin"
            idx_label = f"#{ov.edit_index + 1}" if ov.edit_index >= 0 else ""
            p.drawText(10, TOP_BAR_HEIGHT + 19, f"● EDIT MODE — double-click the new location for {kind} {idx_label}")
        elif ov.calib_mode:
            p.fillRect(0, TOP_BAR_HEIGHT, self.width(), 28, QColor(180, 90, 0, 190))
            p.setPen(QColor(255, 240, 180))
            p.setFont(QFont("Consolas", 10, QFont.Bold))
            p.drawText(10, TOP_BAR_HEIGHT + 19, "● CAL MODE — copy /jumploc in-game, then double-click that spot on the map")
        elif ov.pin_drop_mode:
            p.fillRect(0, TOP_BAR_HEIGHT, self.width(), 28, QColor(20, 90, 170, 190))
            p.setPen(QColor(180, 220, 255))
            p.setFont(QFont("Consolas", 10, QFont.Bold))
            name_preview = ov.pending_pin_name or "Pin"
            p.drawText(10, TOP_BAR_HEIGHT + 19, f"● PIN MODE — double-click to place  \"{name_preview}\"")

    def _draw_pin(self, p, img_px, img_py, name, highlight=False):
        """Draw a pin at the given pixel coordinates.
        
        Args:
            p (QPainter): The QPainter object used for drawing.
            img_px (float): X-coordinate in image pixels.
            img_py (float): Y-coordinate in image pixels.
            name (str): Name label for the pin.
            highlight (bool): Whether the pin should be drawn in highlight mode.
        """
        ov = self.ov
        sx = img_px * ov.zoom + ov.offset_x
        sy = img_py * ov.zoom + ov.offset_y
        pw, ph = PIN_W, PIN_H
        cx = sx
        cy_c = sy - ph * 0.45
        r = pw / 2.0
        path = QPainterPath()
        path.addEllipse(QRectF(cx - r, cy_c - r, r * 2, r * 2))
        tip = QPainterPath()
        tip.moveTo(QPointF(sx, sy))
        tip.lineTo(QPointF(cx - r * 0.65, cy_c + r * 0.5))
        tip.lineTo(QPointF(cx + r * 0.65, cy_c + r * 0.5))
        tip.closeSubpath()
        path = path.united(tip)
        if highlight:
            p.setPen(QPen(theme_q("pin_highlight_stroke", QColor(255, 220, 0)), 2.5))
            p.setBrush(theme_q("pin_highlight_fill", QColor(255, 200, 0)))
        else:
            p.setPen(QPen(theme_q("pin_stroke", QColor(100, 0, 0)), 1.5))
            p.setBrush(theme_q("pin_fill", QColor(210, 30, 30)))
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 160, 160, 180))
        p.drawEllipse(QRectF(cx - r * 0.38, cy_c - r * 0.62, r * 0.55, r * 0.55))
        font = QFont("Consolas", 13, QFont.Bold)
        p.setFont(font)
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(name)
        th = fm.height()
        lx = int(sx - tw / 2)
        ly = int(sy - ph - 6)
        pad = 5
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 185))
        p.drawRoundedRect(lx - pad, ly - th + 3, tw + pad * 2, th + 3, 4, 4)
        sh = theme_q("pin_label_shadow", QColor(0, 0, 0))
        plab = theme_q("pin_label", QColor(255, 220, 80))
        if highlight:
            plab = theme_q("pin_highlight_stroke", QColor(255, 220, 0))
        p.setPen(sh)
        p.drawText(lx + 1, ly + 1, name)
        p.setPen(plab)
        p.drawText(lx, ly, name)

    def wheelEvent(self, event):
        """Handle mouse wheel events for zooming in and out.
        
        Zoom is adjusted based on the cursor position, and respects calibration lock settings.
        """
        ov = self.ov
        if ov.calib_mode and LOCK_ZOOM_CAL and CAL_SNAP_ZOOM > 0:
            ov.zoom = CAL_SNAP_ZOOM
            self.update()
            return
        old = ov.zoom
        factor = (1 + ZOOM_STEP) if event.angleDelta().y() > 0 else (1 - ZOOM_STEP)
        ov.zoom = max(MIN_ZOOM, min(MAX_ZOOM, ov.zoom * factor))
        mx, my = event.x(), event.y()
        ov.offset_x = mx - (mx - ov.offset_x) * (ov.zoom / old)
        ov.offset_y = my - (my - ov.offset_y) * (ov.zoom / old)
        self.update()

    def mousePressEvent(self, event):
        """Handle mouse press events to start panning the map."""
        if event.button() == Qt.LeftButton:
            self.ov.panning = True
            self.ov.last_mouse = event.pos()

    def mouseMoveEvent(self, event):
        """Handle mouse move events to update map panning and coordinate labels."""
        ov = self.ov
        if ov.panning:
            delta = event.pos() - ov.last_mouse
            ov.offset_x += delta.x()
            ov.offset_y += delta.y()
            ov.last_mouse = event.pos()
            self.update()
        ix = (event.x() - ov.offset_x) / ov.zoom
        iy = (event.y() - ov.offset_y) / ov.zoom
        mx, my = pixel_to_world(ix, iy, ov.xc, ov.yc)
        ov.coord_labels["Px"].setText(f"Px={int(ix)}")
        ov.coord_labels["Py"].setText(f"Py={int(iy)}")
        if math.isfinite(mx) and math.isfinite(my):
            ov.coord_labels["Wx"].setText(f"Wx={mx:.1f}")
            ov.coord_labels["Wy"].setText(f"Wy={my:.1f}")
        else:
            ov.coord_labels["Wx"].setText("Wx=?")
            ov.coord_labels["Wy"].setText("Wy=?")
        ov.coord_labels["PlayerX"].setText(f"PlayerX={ov.current_loc[0]:.1f}" if ov.current_loc else "PlayerX=0")
        ov.coord_labels["PlayerY"].setText(f"PlayerY={ov.current_loc[1]:.1f}" if ov.current_loc else "PlayerY=0")
        ov.coord_labels["Zoom"].setText(f"Zoom={ov.zoom:.3f}")

    def mouseReleaseEvent(self, event):
        """Handle mouse release events to stop map panning."""
        if event.button() == Qt.LeftButton:
            self.ov.panning = False

    def mouseDoubleClickEvent(self, event):
        """Handle double-click events to place or edit pins and calibration points."""
        ov = self.ov
        img_x = (event.x() - ov.offset_x) / ov.zoom
        img_y = (event.y() - ov.offset_y) / ov.zoom
        ov.handle_double_click(img_x, img_y)
