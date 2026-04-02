# ==============================================================
# Pantheon Morte Map Tool
# Version: 2.0
# Created By: NeroMorte (AKA: Morte)
# Description: Python tool for map overlay with calibration and pins
# Build Instructions:
#   1 Open terminal and go to project folder:
#      cd /d C:\Users\qarbo\Desktop\Pantheon Morte Map
#   2 Run PyInstaller:
#      python build_exe.py
# ==============================================================

import sys
import time
import threading
import json
import os
import pyperclip
import numpy as np

def resource_path(relative_path):
    """Get the absolute path for files when running as EXE or script."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel,
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QListWidget, QComboBox, QSizePolicy
)
from PyQt5.QtGui import (
    QPixmap, QPainter, QColor, QFont, QPen,
    QPainterPath, QFontMetrics, QIcon
)
from PyQt5.QtCore import Qt, QPoint, QTimer, pyqtSignal, QObject, QRectF, QPointF

# ==============================================================
# SETTINGS — All tunable values live here
# ==============================================================

# --- Dot / Pin Sizes ---
DOT_SIZE         = 14        # Player dot radius (px)
CALIB_DOT_SIZE   = 12        # Calibration marker diameter (px)
PIN_W, PIN_H     = 22, 30    # Drop-pin teardrop dimensions (px)

# --- Zoom ---
MIN_ZOOM         = 0.5
MAX_ZOOM         = 18.0
ZOOM_STEP        = 0.12      # Fraction of current zoom per scroll tick

# --- Calibration ---
UPDATE_THRESHOLD = 50        # Pixel radius: double-click this close to existing calib pt → updates it instead of adding

# --- UI ---
TOP_BAR_HEIGHT   = 38        # Height of the top toolbar (px)
PANEL_WIDTH      = 340       # Width of the side panels (px)
FLASH_DURATION   = 4000      # How long flash messages stay visible (ms)
DEFAULT_OPACITY  = 0.85      # Starting window opacity (0.0 – 1.0)

# --- App identity ---
APP_NAME         = "Pantheon Morte Map"
APP_AUTHOR       = "NeroMorte (AKA Morte)"
APP_DESCRIPTION  = "Pantheon Morte Map Viewer"
APP_VERSION      = "2.0.0.0"
APP_COPYRIGHT    = "© 2026 NeroMorte"
APP_FILENAME     = "Pantheon_Morte_Map.exe"

# --- File paths ---
SETTINGS_DIR     = resource_path("Settings")
MAPS_DIR         = resource_path("Maps")
WINDOW_ICON_PATH = resource_path("Pantheon_Morte_Map.ico")

# --- Map definitions: display name → image filename (in Maps/) ---
# Each map gets its own calibration and pins JSON in Settings/
MAP_DEFINITIONS = {
    "Main Map":          "main_map.png",
    "Halnir Cave":       "halnir_cave.png",
    "Goblin Cave":       "goblin_cave.png",
    "Black Rose Keep":   "black_rose_keep.png",
    "Wildmound Cradle":  "wildmound_cradle.png",
    "Nightfall Crypt":   "nightfall_crypt.png",
}

# ==============================================================
# END SETTINGS
# ==============================================================


def _safe_key(map_name: str) -> str:
    """Convert a map display name to a filesystem-safe key."""
    return map_name.lower().replace(" ", "_")


def _calib_file(map_name: str) -> str:
    return os.path.join(SETTINGS_DIR, f"calibration_{_safe_key(map_name)}.json")


def _pins_file(map_name: str) -> str:
    return os.path.join(SETTINGS_DIR, f"pins_{_safe_key(map_name)}.json")


def _map_image_path(map_name: str) -> str:
    return os.path.join(MAPS_DIR, MAP_DEFINITIONS[map_name])


# --------------------------------------------------------------
def compute_affine_transform(pts):
    if len(pts) < 3:
        return np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])
    A, Bx, Bz = [], [], []
    for px, pz, wx, wz in pts:
        A.append([wx, wz, 1])
        Bx.append(px)
        Bz.append(pz)
    A  = np.array(A,  dtype=float)
    Bx = np.array(Bx, dtype=float)
    Bz = np.array(Bz, dtype=float)
    xc, _, _, _ = np.linalg.lstsq(A, Bx, rcond=None)
    zc, _, _, _ = np.linalg.lstsq(A, Bz, rcond=None)
    return xc, zc


def world_to_pixel(wx, wz, xc, zc):
    return (xc[0]*wx + xc[1]*wz + xc[2],
            zc[0]*wx + zc[1]*wz + zc[2])


# ==============================================================
class Signals(QObject):
    repaint_needed = pyqtSignal()


# ==============================================================
class Panel(QWidget):
    """Dark semi-transparent floating panel."""
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(12, 14, 20, 225))
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 8, 8)


# ==============================================================
class MapCanvas(QWidget):
    """Handles all map drawing and mouse interaction."""
    def __init__(self, overlay):
        super().__init__(overlay)
        self.ov = overlay
        self.setMouseTracking(True)

    # ---- paint -----------------------------------------------
    def paintEvent(self, event):
        ov = self.ov
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setRenderHint(QPainter.Antialiasing)

        # Map image
        if not ov.map_pix.isNull():
            mw = ov.map_pix.width()  * ov.zoom
            mh = ov.map_pix.height() * ov.zoom
            p.drawPixmap(int(ov.offset_x), int(ov.offset_y),
                         int(mw), int(mh), ov.map_pix)

        # Calibration points
        p.setFont(QFont("Consolas", 12, QFont.Bold))
        for idx, (cpx, cpz, wx, wz) in enumerate(ov.calibration_points):
            sx = cpx * ov.zoom + ov.offset_x
            sy = cpz * ov.zoom + ov.offset_y
            p.setPen(QPen(QColor(0, 0, 0), 2))
            p.setBrush(QColor(255, 255, 255, 220))
            p.drawEllipse(int(sx) - CALIB_DOT_SIZE//2,
                          int(sy) - CALIB_DOT_SIZE//2,
                          CALIB_DOT_SIZE, CALIB_DOT_SIZE)
            lx, ly = int(sx) + CALIB_DOT_SIZE//2 + 3, int(sy) + 5
            p.setPen(QColor(0, 0, 0))
            p.drawText(lx+1, ly+1, str(idx+1))
            p.setPen(QColor(255, 255, 180))
            p.drawText(lx, ly, str(idx+1))

        # Last-click crosshair
        if ov.last_click_px:
            cpx, cpy = ov.last_click_px
            sx = cpx * ov.zoom + ov.offset_x
            sy = cpy * ov.zoom + ov.offset_y
            p.setPen(QPen(QColor(255, 180, 0), 2))
            p.setBrush(Qt.NoBrush)
            r = 10
            p.drawLine(int(sx)-r, int(sy), int(sx)+r, int(sy))
            p.drawLine(int(sx), int(sy)-r, int(sx), int(sy)+r)
            p.drawEllipse(int(sx)-r, int(sy)-r, r*2, r*2)

        # Drop pins
        for pin in ov.drop_pins:
            self._draw_pin(p, pin["px"], pin["py"], pin["name"])

        # Player dot
        if ov.current_loc is not None:
            ppx, ppz = world_to_pixel(
                ov.current_loc[0], ov.current_loc[1], ov.xc, ov.zc)
            sx = ppx * ov.zoom + ov.offset_x
            sy = ppz * ov.zoom + ov.offset_y
            p.setPen(QPen(QColor(255, 80, 80, 130), 3))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(int(sx)-DOT_SIZE, int(sy)-DOT_SIZE,
                          DOT_SIZE*2, DOT_SIZE*2)
            p.setPen(QPen(QColor(180, 0, 0), 1))
            p.setBrush(QColor(255, 50, 50))
            p.drawEllipse(int(sx)-DOT_SIZE//2, int(sy)-DOT_SIZE//2,
                          DOT_SIZE, DOT_SIZE)

        # Calib-mode banner
        if ov.calib_mode:
            p.fillRect(0, TOP_BAR_HEIGHT, self.width(), 28, QColor(180, 90, 0, 190))
            p.setPen(QColor(255, 240, 180))
            p.setFont(QFont("Consolas", 10, QFont.Bold))
            p.drawText(10, TOP_BAR_HEIGHT + 19,
                "● CAL MODE — copy /jumploc in-game, then double-click that spot on the map")

        # Pin-drop mode banner
        if ov.pin_drop_mode:
            p.fillRect(0, TOP_BAR_HEIGHT, self.width(), 28, QColor(20, 90, 170, 190))
            p.setPen(QColor(180, 220, 255))
            p.setFont(QFont("Consolas", 10, QFont.Bold))
            name_preview = ov.pending_pin_name or "Pin"
            p.drawText(10, TOP_BAR_HEIGHT + 19,
                f"● PIN MODE — double-click to place  \"{name_preview}\"")

    def _draw_pin(self, p, img_px, img_py, name):
        ov = self.ov
        sx = img_px * ov.zoom + ov.offset_x
        sy = img_py * ov.zoom + ov.offset_y

        pw, ph = PIN_W, PIN_H
        cx     = sx
        cy_c   = sy - ph * 0.45
        r      = pw / 2.0

        path = QPainterPath()
        path.addEllipse(QRectF(cx - r, cy_c - r, r*2, r*2))
        tip = QPainterPath()
        tip.moveTo(QPointF(sx, sy))
        tip.lineTo(QPointF(cx - r*0.65, cy_c + r*0.5))
        tip.lineTo(QPointF(cx + r*0.65, cy_c + r*0.5))
        tip.closeSubpath()
        path = path.united(tip)

        p.setPen(QPen(QColor(100, 0, 0), 1.5))
        p.setBrush(QColor(210, 30, 30))
        p.drawPath(path)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 160, 160, 180))
        p.drawEllipse(QRectF(cx - r*0.38, cy_c - r*0.62, r*0.55, r*0.55))

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
        p.drawRoundedRect(lx - pad, ly - th + 3, tw + pad*2, th + 3, 4, 4)
        p.setPen(QColor(0, 0, 0))
        p.drawText(lx+1, ly+1, name)
        p.setPen(QColor(255, 220, 80))
        p.drawText(lx, ly, name)

    # ---- mouse -----------------------------------------------
    def wheelEvent(self, event):
        ov = self.ov
        old = ov.zoom
        factor = (1 + ZOOM_STEP) if event.angleDelta().y() > 0 else (1 - ZOOM_STEP)
        ov.zoom = max(MIN_ZOOM, min(MAX_ZOOM, ov.zoom * factor))
        mx, my = event.x(), event.y()
        ov.offset_x = mx - (mx - ov.offset_x) * (ov.zoom / old)
        ov.offset_y = my - (my - ov.offset_y) * (ov.zoom / old)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.ov.panning = True
            self.ov.last_mouse = event.pos()

    def mouseMoveEvent(self, event):
        ov = self.ov
        if ov.panning:
            delta = event.pos() - ov.last_mouse
            ov.offset_x += delta.x()
            ov.offset_y += delta.y()
            ov.last_mouse = event.pos()
            self.update()
        ix = (event.x() - ov.offset_x) / ov.zoom
        iy = (event.y() - ov.offset_y) / ov.zoom
        txt = f"Px({int(ix)}, {int(iy)})"
        if ov.current_loc:
            txt += f"   Player({ov.current_loc[0]:.1f}, {ov.current_loc[1]:.1f})"
        ov.coord_lbl.setText(txt)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.ov.panning = False

    def mouseDoubleClickEvent(self, event):
        ov = self.ov
        img_x = (event.x() - ov.offset_x) / ov.zoom
        img_y = (event.y() - ov.offset_y) / ov.zoom
        ov.handle_double_click(img_x, img_y)


# ==============================================================
class MapOverlay(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setMinimumSize(300, 250)

        # Ensure settings dir exists
        os.makedirs(SETTINGS_DIR, exist_ok=True)

        # --- state ---
        self.current_map_name  = list(MAP_DEFINITIONS.keys())[0]
        self.map_pix           = QPixmap()
        self.current_loc       = None
        self.zoom              = 1.0
        self.offset_x          = 0.0
        self.offset_y          = 0.0
        self.panning           = False
        self.last_mouse        = QPoint(0, 0)
        self.last_click_px     = None
        self.opacity           = DEFAULT_OPACITY
        self.setWindowOpacity(self.opacity)

        # Mode flags
        self.calib_mode        = False   # waiting for /jumploc + double-click
        self.pin_drop_mode     = False   # waiting for double-click to place pin
        self.pending_pin_name  = ""      # name staged in the pin panel input

        # Per-map data (loaded when map changes)
        self.calibration_points = []
        self.xc = np.array([1.0, 0.0, 0.0])
        self.zc = np.array([0.0, 1.0, 0.0])
        self.drop_pins          = []

        self.sig = Signals()
        self.sig.repaint_needed.connect(self._on_repaint_needed)

        self._build_ui()
        self._load_map(self.current_map_name)

        self.running = True
        threading.Thread(target=self._watch_clipboard, daemon=True).start()

    # ===========================================================
    # Load / Save
    # ===========================================================

    def _load_map(self, map_name):
        """Switch to a different map: load image + its calibration + pins."""
        self.current_map_name = map_name

        path = _map_image_path(map_name)
        self.map_pix = QPixmap(path)
        if self.map_pix.isNull():
            print(f"WARNING: map image not found: {path}")

        self.calibration_points = self._load_calib(map_name)
        self.xc, self.zc        = compute_affine_transform(self.calibration_points)
        self.drop_pins          = self._load_pins(map_name)

        # Reset view
        self.zoom     = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.last_click_px = None

        # Update combo without triggering the signal again
        idx = list(MAP_DEFINITIONS.keys()).index(map_name)
        self.map_combo.blockSignals(True)
        self.map_combo.setCurrentIndex(idx)
        self.map_combo.blockSignals(False)

        # Resize window to map (capped to reasonable size)
        if not self.map_pix.isNull():
            w = min(self.map_pix.width(),  1400)
            h = min(self.map_pix.height(), 900)
            self.resize(w, h)

        # Refresh visible panels
        if self.calib_panel.isVisible():
            self._refresh_calib_list()
        if self.pin_panel.isVisible():
            self._refresh_pin_list()

        self._flash(f"Map: {map_name}")
        self.canvas.update()

    def _load_calib(self, map_name):
        f = _calib_file(map_name)
        if os.path.exists(f):
            try:
                pts = [tuple(p) for p in json.load(open(f))]
                print(f"[{map_name}] Loaded {len(pts)} calib pts")
                return pts
            except Exception as e:
                print(f"Calib load error ({map_name}): {e}")
        return []

    def _save_calib(self):
        f = _calib_file(self.current_map_name)
        try:
            json.dump(self.calibration_points, open(f, "w"), indent=2)
            self._flash(f"Saved {len(self.calibration_points)} calibration points.")
            self._refresh_calib_list()
        except Exception as e:
            self._flash(f"Save error: {e}")

    def _load_pins(self, map_name):
        f = _pins_file(map_name)
        if os.path.exists(f):
            try:
                return json.load(open(f))
            except:
                pass
        return []

    def _save_pins(self):
        f = _pins_file(self.current_map_name)
        try:
            json.dump(self.drop_pins, open(f, "w"), indent=2)
        except Exception as e:
            print(f"Pin save error: {e}")

    # ===========================================================
    # Build UI
    # ===========================================================

    def _build_ui(self):
        self.setWindowIcon(QIcon(WINDOW_ICON_PATH))

        root = QWidget(self)
        self.setCentralWidget(root)
        root.setStyleSheet("background: transparent;")

        # Canvas fills root
        self.canvas = MapCanvas(self)
        self.canvas.setParent(root)
        self.canvas.setGeometry(0, 0, self.width(), self.height())

        # ---- TOP BAR ----
        self.top_bar = Panel(root)
        self.top_bar.setFixedHeight(TOP_BAR_HEIGHT)
        tl = QHBoxLayout(self.top_bar)
        tl.setContentsMargins(6, 4, 6, 4)
        tl.setSpacing(5)

        def mk(text, bg, tip="", w=42):
            b = QPushButton(text)
            b.setFixedSize(w, 26)
            b.setToolTip(tip)
            b.setStyleSheet(
                f"QPushButton{{background:{bg};color:white;border:none;"
                f"font-weight:bold;font-size:12px;border-radius:4px;}}"
                f"QPushButton:hover{{background:#fff;color:#111;}}"
            )
            return b

        # Map selector combo
        self.map_combo = QComboBox()
        self.map_combo.addItems(list(MAP_DEFINITIONS.keys()))
        self.map_combo.setFixedHeight(26)
        self.map_combo.setMinimumWidth(150)
        self.map_combo.setStyleSheet(
            "QComboBox{background:#1a2030;color:#c8d8f0;border:1px solid rgba(255,255,255,40);"
            "border-radius:4px;font-size:12px;font-weight:bold;padding:0 8px;}"
            "QComboBox:hover{background:#243050;border-color:rgba(255,255,255,80);}"
            "QComboBox::drop-down{border:none;width:20px;}"
            "QComboBox::down-arrow{image:none;}"
            "QComboBox QAbstractItemView{background:#1a2030;color:#c8d8f0;"
            "border:1px solid rgba(255,255,255,40);selection-background-color:#2a4080;}"
        )
        self.map_combo.currentTextChanged.connect(self._on_map_changed)
        tl.addWidget(self.map_combo)

        # Separator look
        sep = QLabel("|")
        sep.setStyleSheet("color:rgba(255,255,255,30);background:transparent;")
        tl.addWidget(sep)

        self.btn_zoom_in  = mk("+",    "#555",    "Zoom in",  30)
        self.btn_zoom_out = mk("−",    "#555",    "Zoom out", 30)
        self.btn_center   = mk("⊙",    "#2471a3", "Center on player", 30)
        self.btn_cal_list = mk("CAL",  "#c0782a", "Show/hide calibration panel", 46)
        self.btn_pin_list = mk("PINS", "#c0392b", "Show/hide pins panel",       46)
        self.btn_opacity  = mk(f"{int(DEFAULT_OPACITY*100)}%", "#444", "Cycle opacity", 44)

        for b, fn in [
            (self.btn_zoom_in,  self._zoom_in),
            (self.btn_zoom_out, self._zoom_out),
            (self.btn_center,   self._center_on_player),
            (self.btn_cal_list, self._toggle_calib_panel),
            (self.btn_pin_list, self._toggle_pin_panel),
            (self.btn_opacity,  self._cycle_opacity),
        ]:
            b.clicked.connect(fn)
            tl.addWidget(b)

        tl.addStretch()

        self.coord_lbl = QLabel("")
        self.coord_lbl.setStyleSheet(
            "color:rgba(255,255,255,180);font-size:11px;font-family:Consolas,monospace;"
            "background:transparent;border:none;"
        )
        tl.addWidget(self.coord_lbl)

        # ---- FLASH LABEL ----
        self.flash_lbl = QLabel("", root)
        self.flash_lbl.setStyleSheet(
            "background:rgba(0,0,0,215);color:#f0c040;padding:7px 16px;"
            "border-radius:7px;font-size:13px;font-weight:bold;font-family:Consolas,monospace;"
        )
        self.flash_lbl.setAlignment(Qt.AlignCenter)
        self.flash_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.flash_lbl.hide()
        self.flash_timer = QTimer(self)
        self.flash_timer.setSingleShot(True)
        self.flash_timer.timeout.connect(self.flash_lbl.hide)

        # ---- PANELS ----
        self.calib_panel = self._make_calib_panel(root)
        self.calib_panel.hide()

        self.pin_panel = self._make_pin_panel(root)
        self.pin_panel.hide()

        self._relayout()

    # ----------------------------------------------------------
    # Calibration Panel
    # ----------------------------------------------------------
    def _make_calib_panel(self, parent):
        p = Panel(parent)
        v = QVBoxLayout(p)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        # Title
        lbl = QLabel(f"Calibration  —  {self.current_map_name}")
        lbl.setObjectName("calib_title")
        lbl.setStyleSheet(
            "color:#f0c040;font-size:14px;font-weight:bold;background:transparent;border:none;"
        )
        v.addWidget(lbl)
        self._calib_title_lbl = lbl

        # How-to blurb
        hint = QLabel(
            "① Enable CAL mode below\n"
            "② Copy /jumploc in-game\n"
            "③ Double-click that spot on the map\n"
            "④ Repeat ≥3 times, then Save"
        )
        hint.setStyleSheet(
            "color:rgba(200,200,180,180);font-size:11px;font-family:Consolas,monospace;"
            "background:rgba(0,0,0,80);border-radius:4px;padding:6px;"
            "border:none;"
        )
        hint.setWordWrap(True)
        v.addWidget(hint)

        # CAL toggle inside panel
        self.btn_calib_toggle = QPushButton("▶  Enable Calibration Mode")
        self.btn_calib_toggle.setStyleSheet(
            "QPushButton{background:#c0782a;color:white;border:none;"
            "font-weight:bold;font-size:12px;border-radius:4px;padding:5px;}"
            "QPushButton:hover{background:#fff;color:#111;}"
        )
        self.btn_calib_toggle.setCheckable(True)
        self.btn_calib_toggle.clicked.connect(self._toggle_calib_mode)
        v.addWidget(self.btn_calib_toggle)

        # List
        self.calib_list = QListWidget()
        self.calib_list.setStyleSheet(
            "QListWidget{background:rgba(0,0,0,170);color:white;"
            "border:1px solid rgba(255,255,255,30);border-radius:4px;"
            "font-size:12px;font-family:Consolas,monospace;}"
            "QListWidget::item{padding:3px 5px;}"
            "QListWidget::item:selected{background:rgba(100,100,220,190);}"
            "QListWidget::item:hover{background:rgba(255,255,255,18);}"
        )
        self.calib_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        v.addWidget(self.calib_list)

        # Buttons row
        row = QHBoxLayout()
        row.setSpacing(6)
        for text, bg, fn in [
            ("Delete Selected", "#8B2020", self._delete_selected_calib),
            ("Clear All",       "#5a1010", self._clear_all_calib),
            ("Save",            "#1e6e3a", self._save_calib),
        ]:
            b = QPushButton(text)
            b.setStyleSheet(
                f"QPushButton{{background:{bg};color:white;border:none;"
                f"font-size:11px;font-weight:bold;border-radius:4px;padding:5px 8px;}}"
                f"QPushButton:hover{{background:#fff;color:#111;}}"
            )
            b.clicked.connect(fn)
            row.addWidget(b)
        v.addLayout(row)

        return p

    # ----------------------------------------------------------
    # Pin Panel
    # ----------------------------------------------------------
    def _make_pin_panel(self, parent):
        p = Panel(parent)
        v = QVBoxLayout(p)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        # Title
        lbl = QLabel("Drop Pins")
        lbl.setStyleSheet(
            "color:#ff6060;font-size:14px;font-weight:bold;background:transparent;border:none;"
        )
        v.addWidget(lbl)

        # ---- Create new pin section ----
        create_box = QWidget()
        create_box.setStyleSheet(
            "background:rgba(180,30,30,30);border:1px solid rgba(200,80,80,60);"
            "border-radius:5px;"
        )
        cv = QVBoxLayout(create_box)
        cv.setContentsMargins(8, 6, 8, 8)
        cv.setSpacing(5)

        create_lbl = QLabel("Create New Pin")
        create_lbl.setStyleSheet(
            "color:#ff9090;font-size:12px;font-weight:bold;background:transparent;border:none;"
        )
        cv.addWidget(create_lbl)

        name_row = QHBoxLayout()
        name_row.setSpacing(5)

        self.pin_name_edit = QLineEdit()
        self.pin_name_edit.setPlaceholderText("Pin name…")
        self.pin_name_edit.setStyleSheet(
            "QLineEdit{background:rgba(0,0,0,190);color:white;"
            "border:1px solid rgba(255,255,255,50);border-radius:4px;"
            "font-size:12px;padding:4px 7px;}"
            "QLineEdit:focus{border:1px solid rgba(255,100,100,180);}"
        )
        self.pin_name_edit.textChanged.connect(self._on_pin_name_changed)
        name_row.addWidget(self.pin_name_edit)
        cv.addLayout(name_row)

        hint2 = QLabel("Enter a name, then double-click the map to place it.")
        hint2.setStyleSheet(
            "color:rgba(180,180,160,180);font-size:10px;background:transparent;border:none;"
        )
        hint2.setWordWrap(True)
        cv.addWidget(hint2)

        self.btn_pin_mode = QPushButton("▶  Activate Pin-Drop Mode")
        self.btn_pin_mode.setStyleSheet(
            "QPushButton{background:#c0392b;color:white;border:none;"
            "font-weight:bold;font-size:12px;border-radius:4px;padding:5px;}"
            "QPushButton:hover{background:#fff;color:#111;}"
        )
        self.btn_pin_mode.setCheckable(True)
        self.btn_pin_mode.clicked.connect(self._toggle_pin_drop_mode)
        cv.addWidget(self.btn_pin_mode)

        v.addWidget(create_box)

        # ---- Existing pins list ----
        sep_lbl = QLabel("Placed Pins")
        sep_lbl.setStyleSheet(
            "color:rgba(200,180,180,200);font-size:12px;font-weight:bold;"
            "background:transparent;border:none;margin-top:4px;"
        )
        v.addWidget(sep_lbl)

        self.pin_list = QListWidget()
        self.pin_list.setStyleSheet(
            "QListWidget{background:rgba(0,0,0,170);color:white;"
            "border:1px solid rgba(255,255,255,30);border-radius:4px;"
            "font-size:12px;font-family:Consolas,monospace;}"
            "QListWidget::item{padding:3px 5px;}"
            "QListWidget::item:selected{background:rgba(200,50,50,190);}"
            "QListWidget::item:hover{background:rgba(255,255,255,18);}"
        )
        self.pin_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        v.addWidget(self.pin_list)

        # Rename row
        rrow = QHBoxLayout()
        rrow.setSpacing(5)
        self.pin_rename_edit = QLineEdit()
        self.pin_rename_edit.setPlaceholderText("New name for selected pin…")
        self.pin_rename_edit.setStyleSheet(
            "QLineEdit{background:rgba(0,0,0,190);color:white;"
            "border:1px solid rgba(255,255,255,50);border-radius:4px;"
            "font-size:12px;padding:4px 7px;}"
            "QLineEdit:focus{border:1px solid rgba(255,100,100,180);}"
        )
        self.pin_rename_edit.returnPressed.connect(self._rename_selected_pin)
        btn_rename = QPushButton("Rename")
        btn_rename.setStyleSheet(
            "QPushButton{background:#2471a3;color:white;border:none;"
            "font-size:12px;font-weight:bold;border-radius:4px;padding:4px 9px;}"
            "QPushButton:hover{background:#fff;color:#111;}"
        )
        btn_rename.clicked.connect(self._rename_selected_pin)
        rrow.addWidget(self.pin_rename_edit)
        rrow.addWidget(btn_rename)
        v.addLayout(rrow)

        # Action row
        row = QHBoxLayout()
        row.setSpacing(6)
        for text, bg, fn in [
            ("Delete Selected", "#8B2020", self._delete_selected_pin),
            ("Clear All",       "#5a1010", self._clear_all_pins),
            ("Save Pins",       "#1e6e3a", self._save_pins_flash),
        ]:
            b = QPushButton(text)
            b.setStyleSheet(
                f"QPushButton{{background:{bg};color:white;border:none;"
                f"font-size:11px;font-weight:bold;border-radius:4px;padding:5px 8px;}}"
                f"QPushButton:hover{{background:#fff;color:#111;}}"
            )
            b.clicked.connect(fn)
            row.addWidget(b)
        v.addLayout(row)

        return p

    # ===========================================================
    # Layout
    # ===========================================================

    def _relayout(self):
        w, h = self.width(), self.height()
        self.canvas.setGeometry(0, 0, w, h)
        self.top_bar.setGeometry(0, 0, w, TOP_BAR_HEIGHT)
        pw  = PANEL_WIDTH
        ph  = min(h - TOP_BAR_HEIGHT - 8, 600)
        py  = TOP_BAR_HEIGHT + 4
        self.calib_panel.setGeometry(w - pw - 6, py, pw, ph)
        self.pin_panel.setGeometry(w - pw - 6, py, pw, ph)
        if not self.flash_lbl.isHidden():
            self.flash_lbl.adjustSize()
            self.flash_lbl.move(
                (w - self.flash_lbl.width()) // 2,
                h // 2 - 60
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    # ===========================================================
    # Map switching
    # ===========================================================

    def _on_map_changed(self, map_name):
        if map_name and map_name != self.current_map_name:
            self._load_map(map_name)

    # ===========================================================
    # Zoom / Center
    # ===========================================================

    def _zoom_in(self):
        old = self.zoom
        self.zoom = min(self.zoom * (1 + ZOOM_STEP), MAX_ZOOM)
        cx, cy = self.canvas.width()/2, self.canvas.height()/2
        self.offset_x = cx - (cx - self.offset_x) * (self.zoom / old)
        self.offset_y = cy - (cy - self.offset_y) * (self.zoom / old)
        self.canvas.update()

    def _zoom_out(self):
        old = self.zoom
        self.zoom = max(self.zoom * (1 - ZOOM_STEP), MIN_ZOOM)
        cx, cy = self.canvas.width()/2, self.canvas.height()/2
        self.offset_x = cx - (cx - self.offset_x) * (self.zoom / old)
        self.offset_y = cy - (cy - self.offset_y) * (self.zoom / old)
        self.canvas.update()

    def _center_on_player(self):
        if self.current_loc is None:
            return
        px, pz = world_to_pixel(
            self.current_loc[0], self.current_loc[1], self.xc, self.zc)
        self.offset_x = self.canvas.width()/2  - px * self.zoom
        self.offset_y = self.canvas.height()/2 - pz * self.zoom
        self.canvas.update()

    # ===========================================================
    # Opacity cycle
    # ===========================================================

    _opacity_cycle = [0.25, 0.5, 0.75, 0.85, 1.0]

    def _cycle_opacity(self):
        try:
            idx = self._opacity_cycle.index(self.opacity)
        except ValueError:
            idx = 0
        self.opacity = self._opacity_cycle[(idx + 1) % len(self._opacity_cycle)]
        self.setWindowOpacity(self.opacity)
        self.btn_opacity.setText(f"{int(self.opacity*100)}%")

    # ===========================================================
    # Panel toggles
    # ===========================================================

    def _toggle_calib_panel(self):
        vis = not self.calib_panel.isVisible()
        self.calib_panel.setVisible(vis)
        if vis:
            self._calib_title_lbl.setText(f"Calibration  —  {self.current_map_name}")
            self._refresh_calib_list()
            self.pin_panel.hide()
            self._set_pin_drop_mode(False)

    def _toggle_pin_panel(self):
        vis = not self.pin_panel.isVisible()
        self.pin_panel.setVisible(vis)
        if vis:
            self._refresh_pin_list()
            self.calib_panel.hide()
            self._set_calib_mode(False)

    # ===========================================================
    # Calibration mode
    # ===========================================================

    def _toggle_calib_mode(self):
        self._set_calib_mode(not self.calib_mode)

    def _set_calib_mode(self, enabled: bool):
        self.calib_mode = enabled
        # Turn off pin-drop mode if enabling calib
        if enabled:
            self._set_pin_drop_mode(False)
        label = "■  Disable Calibration Mode" if enabled else "▶  Enable Calibration Mode"
        self.btn_calib_toggle.setText(label)
        self.btn_calib_toggle.setChecked(enabled)
        self.btn_calib_toggle.setStyleSheet(
            "QPushButton{background:%s;color:white;border:%s;"
            "font-weight:bold;font-size:12px;border-radius:4px;padding:5px;}"
            "QPushButton:hover{background:#fff;color:#111;}" % (
                "#e07020" if enabled else "#c0782a",
                "2px solid #f0c040" if enabled else "none"
            )
        )
        self.canvas.update()

    # ===========================================================
    # Pin-drop mode
    # ===========================================================

    def _on_pin_name_changed(self, text):
        self.pending_pin_name = text.strip()
        self.canvas.update()

    def _toggle_pin_drop_mode(self):
        self._set_pin_drop_mode(not self.pin_drop_mode)

    def _set_pin_drop_mode(self, enabled: bool):
        self.pin_drop_mode = enabled
        if enabled:
            self._set_calib_mode(False)
            # Make sure pin panel is visible
            if not self.pin_panel.isVisible():
                self.pin_panel.show()
                self._refresh_pin_list()
        label = "■  Cancel Pin-Drop Mode" if enabled else "▶  Activate Pin-Drop Mode"
        self.btn_pin_mode.setText(label)
        self.btn_pin_mode.setChecked(enabled)
        self.btn_pin_mode.setStyleSheet(
            "QPushButton{background:%s;color:white;border:%s;"
            "font-weight:bold;font-size:12px;border-radius:4px;padding:5px;}"
            "QPushButton:hover{background:#fff;color:#111;}" % (
                "#e03030" if enabled else "#c0392b",
                "2px solid #ff8080" if enabled else "none"
            )
        )
        self.canvas.update()

    # ===========================================================
    # List helpers
    # ===========================================================

    def _refresh_calib_list(self):
        self.calib_list.clear()
        for i, (px, pz, wx, wz) in enumerate(self.calibration_points):
            self.calib_list.addItem(
                f"#{i+1}  Px({int(px)},{int(pz)})  W({wx:.1f},{wz:.1f})"
            )

    def _refresh_pin_list(self):
        self.pin_list.clear()
        for pin in self.drop_pins:
            self.pin_list.addItem(
                f"📍 {pin['name']}  Px({int(pin['px'])},{int(pin['py'])})"
            )

    def _delete_selected_calib(self):
        row = self.calib_list.currentRow()
        if 0 <= row < len(self.calibration_points):
            self.calibration_points.pop(row)
            self.xc, self.zc = compute_affine_transform(self.calibration_points)
            self._refresh_calib_list()
            self.canvas.update()
            self._flash("Calibration point deleted.")

    def _clear_all_calib(self):
        if not self.calibration_points:
            return
        self.calibration_points.clear()
        self.xc, self.zc = compute_affine_transform(self.calibration_points)
        self._refresh_calib_list()
        self.canvas.update()
        self._flash("All calibration points cleared.")

    def _delete_selected_pin(self):
        row = self.pin_list.currentRow()
        if 0 <= row < len(self.drop_pins):
            name = self.drop_pins[row]["name"]
            self.drop_pins.pop(row)
            self._refresh_pin_list()
            self.canvas.update()
            self._save_pins()
            self._flash(f"Pin '{name}' deleted.")

    def _clear_all_pins(self):
        if not self.drop_pins:
            return
        self.drop_pins.clear()
        self._refresh_pin_list()
        self.canvas.update()
        self._save_pins()
        self._flash("All pins cleared.")

    def _rename_selected_pin(self):
        row = self.pin_list.currentRow()
        new_name = self.pin_rename_edit.text().strip()
        if 0 <= row < len(self.drop_pins) and new_name:
            self.drop_pins[row]["name"] = new_name
            self._refresh_pin_list()
            self.canvas.update()
            self._save_pins()
            self.pin_rename_edit.clear()
            self._flash(f"Pin renamed to '{new_name}'.")

    def _save_pins_flash(self):
        self._save_pins()
        self._flash(f"Saved {len(self.drop_pins)} pins.")

    # ===========================================================
    # Double-click handler (called from canvas)
    # ===========================================================

    def handle_double_click(self, img_x, img_y):
        x_click = int(round(img_x))
        z_click = int(round(img_y))
        self.last_click_px = (x_click, z_click)

        if self.calib_mode:
            # --- calibration ---
            text = pyperclip.paste().strip()
            if not text.startswith("/jumploc"):
                self._flash("CAL mode: copy /jumploc in-game first, then double-click.")
                self.canvas.update()
                return
            parts = text.split()
            try:
                xw = float(parts[1])
                zw = float(parts[3])
                if self.calibration_points:
                    dists = [(np.hypot(p[0]-x_click, p[1]-z_click), i)
                             for i, p in enumerate(self.calibration_points)]
                    min_d, ni = min(dists)
                    if min_d <= UPDATE_THRESHOLD:
                        self.calibration_points[ni] = (x_click, z_click, xw, zw)
                        msg = f"Updated pt #{ni+1}: Px({x_click},{z_click}) W({xw:.1f},{zw:.1f})"
                    else:
                        self.calibration_points.append((x_click, z_click, xw, zw))
                        msg = f"Added pt #{len(self.calibration_points)}: Px({x_click},{z_click}) W({xw:.1f},{zw:.1f})"
                else:
                    self.calibration_points.append((x_click, z_click, xw, zw))
                    msg = f"Added pt #1: Px({x_click},{z_click}) W({xw:.1f},{zw:.1f})"
                self.xc, self.zc = compute_affine_transform(self.calibration_points)
                self._refresh_calib_list()
                self._flash(msg)
            except Exception as e:
                self._flash(f"Error reading /jumploc: {e}")

        elif self.pin_drop_mode:
            # --- pin drop ---
            name = self.pending_pin_name or f"Pin {len(self.drop_pins)+1}"
            self.drop_pins.append({"name": name, "px": x_click, "py": z_click})
            self._refresh_pin_list()
            self._save_pins()
            self._flash(f"📍 '{name}' placed at Px({x_click},{z_click})")
            # Auto-clear the name field and turn off mode so next placement is intentional
            self.pin_name_edit.clear()
            self.pending_pin_name = ""
            self._set_pin_drop_mode(False)

        self.canvas.update()

    # ===========================================================
    # Flash
    # ===========================================================

    def _flash(self, text):
        self.flash_lbl.setText(text)
        self.flash_lbl.adjustSize()
        self.flash_lbl.move(
            (self.width()  - self.flash_lbl.width())  // 2,
            (self.height() - self.flash_lbl.height()) // 2 - 40
        )
        self.flash_lbl.show()
        self.flash_lbl.raise_()
        self.flash_timer.start(FLASH_DURATION)

    # ===========================================================
    # Clipboard watcher (background thread)
    # ===========================================================

    def _watch_clipboard(self):
        last = ""
        while self.running:
            try:
                text = pyperclip.paste().strip()
                if text != last and text.startswith("/jumploc"):
                    last = text
                    parts = text.split()
                    x = float(parts[1])
                    z = float(parts[3])
                    self.current_loc = (x, z)
                    self.sig.repaint_needed.emit()
            except:
                pass
            time.sleep(0.1)

    def _on_repaint_needed(self):
        self.canvas.update()

    def closeEvent(self, event):
        self.running = False
        QApplication.quit()


# ==============================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MapOverlay()
    win.show()
    sys.exit(app.exec_())