# ==============================================================
# Pantheon Morte Map Tool
# Version: 4.1.1.0
# Created By: NeroMorte (AKA: Morte)
# Description: Python tool for map overlay with calibration, pins, layers
# Build Instructions:
#   1 Open terminal and go to project folder:
#      cd /d %USERPROFILE%\Desktop\Pantheon Morte Map
#   2 Run PyInstaller:
#      python build_exe.py
# ==============================================================
#
# What's new in v4.1.1.0
#   - /loc auto-centers map on player (Settings panel checkbox)
#   - /loc auto-zoom to 1.0 option   (Settings panel checkbox)
#   - Z value from /loc auto-selects correct layer per map
#     configured via [map_z_layers] in config.ini (range-based min,max)
#   - Shift+M is now a GLOBAL system-wide hotkey (works even when
#     the window is not focused) — properly minimizes / restores
#   - UPD button shows live per-file download progress in the flash
#     bar, with a full summary at the end
#   - Selecting a map now FILLS the viewport (crop-to-fill) and
#     centers the image — no more white space around the map
#   - New Settings panel (gear ⚙ button) with auto-center / auto-zoom
#     checkboxes for /loc behavior
#
import sys
import time
import threading
import json
import os
import math
import pyperclip
import numpy as np
import urllib.request
import urllib.error
from PyQt5.QtCore import QFileSystemWatcher

# ctypes is needed for Windows RegisterHotKey so Shift+M works globally
from PyQt5.QtWidgets import QGraphicsDropShadowEffect
from PyQt5.QtGui import QColor
    
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel,
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QListWidget, QComboBox, QSizePolicy, QCheckBox, QScrollArea,
    QShortcut, QMessageBox,
)
from PyQt5.QtGui import (
    QPixmap, QPainter, QColor, QFont, QPen,
    QPainterPath, QFontMetrics, QIcon, QImage, QKeySequence
)
from PyQt5.QtCore import Qt, QPoint, QTimer

from app_settings import (
    APP_NAME,
    APP_VERSION,
    AUTO_CENTER_ON_LOC,
    AUTO_ZOOM_ON_LOC,
    CALIB_DOT_SIZE,
    CAL_SNAP_ZOOM,
    DEFAULT_OPACITY,
    DOT_SIZE,
    FLASH_DURATION,
    KEEP_VIEW,
    LOCK_ZOOM_CAL,
    LOWER_LAYER_OPACITY,
    MAP_CACHE_RESOLUTION,
    MAP_DEFINITIONS,
    MAP_Z_LAYER_RANGES,
    MAX_ZOOM,
    MIN_ZOOM,
    PANEL_WIDTH,
    PERSIST_GEOMETRY,
    PIN_H,
    PIN_W,
    PULSE_EXTENT,
    PULSE_INTERVAL_MS,
    PULSE_RINGS,
    PULSE_SPEED,
    SETTINGS_DIR,
    TOP_BAR_HEIGHT,
    TOGGLE_MAP_KEYS,
    UPDATE_MANIFEST_URL,
    UPDATE_THRESHOLD,
    WIN_H,
    WIN_W,
    WINDOW_ICON_PATH,
    ZOOM_STEP,
    _CFG,
    _INI_PATH,
    _RESOLUTION_MAP,
    _safe_key,
    theme_q,
    _INI_DEFAULTS,
    _write_ini_with_comments,
    
)

from app_functions import (
    _calib_file,
    _jumploc_required_token_count,
    _map_layer_path,
    _markers_file,
    _pins_file,
    compute_affine_transform,
    jumploc_game_z,
    jumploc_map_xy,
    pixel_to_world,
    world_to_pixel,
)
from core_signals import Signals, _GlobalHotkeyThread
from ui_canvas import MapCanvas
from ui_panel import Panel
from overlay_editing import OverlayEditingMixin
from overlay_location_update import OverlayLocationUpdateMixin
from overlay_update_download import OverlayUpdateDownloadMixin
from overlay_ui_panels import OverlayUIPanelsMixin
from app_settings import WIN_X, WIN_Y, WIN_W, WIN_H

DEBUG = "--debug" in sys.argv

# ==============================================================
# MAP OVERLAY  (main window)
# ==============================================================
class MapOverlay(
    QMainWindow,
    OverlayEditingMixin,
    OverlayLocationUpdateMixin,
    OverlayUpdateDownloadMixin,
    OverlayUIPanelsMixin,
):
    """
    Main map overlay window. Combines multiple behaviors via mixins:
    - OverlayEditingMixin: handles calibration, pin, and marker editing
    - OverlayLocationUpdateMixin: updates overlay based on current in-game location
    - OverlayUpdateDownloadMixin: manages map and overlay updates
    - OverlayUIPanelsMixin: manages panel UI elements (calibration, pins, layers, markers)
    
    Responsible for loading map layers, displaying them in a stacked canvas, 
    handling zoom/pan, user interactions, pulse animations, hotkeys, and clipboard watching.
    """

    # ----------------------------------------------------------
    # Small visibility toggles called by panel buttons
    # ----------------------------------------------------------
    def _toggle_panel_visibility(self, container: QWidget, button: QPushButton):
        """
        Toggle a panel's visibility on/off when its associated button is pressed.
        Updates the button text to match the new state.
        """
        if container.isVisible():
            container.hide()
            button.setText("Show")
        else:
            container.show()
            button.setText("Hide")

    def _toggle_show_cal_points(self):
        """
        Toggle the display of calibration points on the map canvas.
        Updates the corresponding panel button text and triggers canvas repaint.
        """
        self.show_cal_points = not self.show_cal_points
        self.btn_calib_hide.setText(
            "Show Cal Points on Map" if not self.show_cal_points else "Hide Cal Points on Map"
        )
        self.canvas.update()

    def _toggle_show_pins(self):
        """
        Toggle the display of dropped pins on the map canvas.
        Updates the corresponding panel button text and triggers canvas repaint.
        """
        self.show_pins = not self.show_pins
        self.btn_pin_hide.setText(
            "Show Pins on Map" if not self.show_pins else "Hide Pins on Map"
        )
        self.canvas.update()

    def _toggle_show_markers(self):
        """
        Toggle the display of named markers on the map canvas.
        Updates the corresponding panel button text and triggers canvas repaint.
        """
        self.show_markers = not self.show_markers
        self.btn_markers_hide.setText(
            "Show Markers on Map" if not self.show_markers else "Hide Markers on Map"
        )
        self.canvas.update()
        
    def __init__(self):
        """
        Initialize the MapOverlay main window:
        - Set window flags and minimum size
        - Initialize runtime state variables (map, zoom, offsets, calibration/pins/markers)
        - Initialize signals for repaint, map loaded, location updates, flash messages, and hotkeys
        - Set up geometry debounce timer
        - Build the UI and restore window geometry
        - Load the initial map
        - Set up pulse animation timer if enabled
        - Initialize Qt shortcut and global hotkey thread
        - Start a clipboard watcher thread
        """
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setMinimumSize(300, 250)

        os.makedirs(SETTINGS_DIR, exist_ok=True)
        
        # ---- Runtime state ----
        self.current_map_name   = list(MAP_DEFINITIONS.keys())[0]
        self.map_layers         = []
        self.layer_visible      = []
        self.current_loc        = None   # (map_x, map_y) from last /jumploc
        self.current_game_z     = None   # game Z from last /jumploc (layer selection only)
        self.zoom               = 1.0
        self.offset_x           = 0.0
        self.offset_y           = 0.0
        self.panning            = False
        self.last_mouse         = QPoint(0, 0)
        self.last_click_px      = None
        self.opacity            = DEFAULT_OPACITY
        self.setWindowOpacity(self.opacity)

        self.calib_mode         = False
        self.pin_drop_mode      = False
        self.pending_pin_name   = ""

        self.edit_mode          = False
        self.edit_type          = None
        self.edit_index         = -1

        self.calibration_points = []
        self.xc = np.array([1.0, 0.0, 0.0])
        self.yc = np.array([0.0, 1.0, 0.0])
        self.drop_pins          = []
        self.named_markers      = []
        self.pulse_phase        = 0.0
        self._first_map_fit     = True

        # Location behavior -- toggled live via SET panel checkboxes
        self.auto_center = AUTO_CENTER_ON_LOC
        self.auto_zoom   = AUTO_ZOOM_ON_LOC
        
        # ---- Signals ----
        self.sig = Signals()
        self.sig.repaint_needed.connect(self._on_repaint_needed)
        self.sig.map_loaded.connect(self._on_map_loaded)
        self.sig.loc_updated.connect(self._on_loc_updated)   # auto-center/zoom/layer
        self.sig.flash_msg.connect(self._flash)              # safe cross-thread flash
        self.sig.hotkey_fired.connect(self._toggle_window_visibility)
        self.sig.update_notice.connect(self._on_update_notice)
        self.sig.update_finished.connect(self._on_update_finished)
        
        # Debounce timer for window geometry saves
        self._geom_save_timer = QTimer(self)
        self._geom_save_timer.setSingleShot(True)
        self._geom_save_timer.timeout.connect(self._save_window_geometry)
        
        # ---- Build UI ----
        self._build_ui()
        self._restore_window_geometry()
        self._refresh_title()
        self._load_map(self.current_map_name)
        
        # ---- Pulse animation timer ----
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(max(16, PULSE_INTERVAL_MS))
        self._pulse_timer.timeout.connect(self._tick_pulse)
        if PULSE_RINGS > 0:
            self._pulse_timer.start()

        # Fallback Qt shortcut (fires only when window is focused)
        sc = QShortcut(QKeySequence(TOGGLE_MAP_KEYS), self)
        sc.activated.connect(self._toggle_window_visibility)

        # Global hotkey thread -- fires even when the game has focus
        self._hotkey_thread = _GlobalHotkeyThread(self.sig, TOGGLE_MAP_KEYS)
        self._hotkey_thread.start()
        
        # ---- Clipboard watcher thread ----
        self.running = True
        threading.Thread(target=self._watch_clipboard, daemon=True).start()
        self._update_in_progress = False
        self._update_notice_started = False
        QTimer.singleShot(1500, self._start_update_notice_check)
        
        self.show_cal_points = True
        self.show_pins = True
        self.show_markers = True
        
        
    # ===========================================================
    # Load / Save
    # ===========================================================

    def _load_map(self, map_name):
        """
        Begin loading a map in the background thread.
        - Loads each map layer (from cache if available)
        - Resizes layers if larger than cache resolution
        - Emits map_loaded signal when complete for main-thread processing
        """
        self.current_map_name = map_name
        layer_defs = MAP_DEFINITIONS[map_name]
        self.map_layers    = []
        self.layer_visible = []

        self.map_combo.setEnabled(False)
        self._flash(f"Loading {map_name}...")

        def do_load():
            images = []
            res_px = _RESOLUTION_MAP.get(MAP_CACHE_RESOLUTION, 4096)
            for ld in layer_defs:
                path       = _map_layer_path(map_name, ld["file"])
                base, ext  = os.path.splitext(path)
                cache_path = f"{base}_{MAP_CACHE_RESOLUTION}{ext}"

                if os.path.exists(cache_path):
                    print(f"[{ld['name']}] Loading cached {MAP_CACHE_RESOLUTION} copy")
                    img = QImage(cache_path)
                    if img.isNull():
                        print(f"WARNING: cache failed to load: {cache_path}")
                        img = QImage(path)
                else:
                    img = QImage(path)
                    if img.isNull():
                        print(f"WARNING: layer image not found: {path}")
                    else:
                        if img.width() > res_px or img.height() > res_px:
                            print(f"[{ld['name']}] Scaling to {MAP_CACHE_RESOLUTION}...")
                            img = img.scaled(res_px, res_px,
                                             Qt.KeepAspectRatio,
                                             Qt.SmoothTransformation)
                            img.save(cache_path)
                            print(f"[{ld['name']}] Saved: {cache_path}")
                images.append(img)
            self.sig.map_loaded.emit(map_name, images)

        threading.Thread(target=do_load, daemon=True).start()

    def _on_map_loaded(self, map_name, images):
        """
        Main-thread callback after background map load finishes.
        - Converts near-black pixels to transparent for correct stacking
        - Loads calibration points, pins, and named markers
        - Fits or centers map in canvas
        - Resets modes (calibration, pin-drop, edit)
        - Updates map combo box and any visible panels
        """
        self.map_layers    = []
        self.layer_visible = []

        for img in images:
            if img.isNull():
                self.map_layers.append(QPixmap())
            else:
                # Convert black background to alpha so layers stack correctly
                img = img.convertToFormat(QImage.Format_ARGB32)
                ptr = img.bits()
                ptr.setsize(img.byteCount())
                arr = np.frombuffer(ptr, dtype=np.uint8).reshape(
                    (img.height(), img.width(), 4))
                # ARGB layout: arr[...,0]=B  arr[...,1]=G  arr[...,2]=R  arr[...,3]=A
                r = arr[..., 2].astype(np.uint16)
                g = arr[..., 1].astype(np.uint16)
                b = arr[..., 0].astype(np.uint16)
                near_black = (r < 30) & (g < 30) & (b < 30)
                arr[near_black, 3] = 0   # set alpha to 0 for near-black pixels
                self.map_layers.append(QPixmap.fromImage(img))
            self.layer_visible.append(True)

        self.calibration_points = self._load_calib(map_name)
        self.xc, self.yc        = compute_affine_transform(self.calibration_points)
        self.drop_pins          = self._load_pins(map_name)
        self.named_markers      = self._load_named_markers(map_name)

        self.last_click_px = None

        if self._first_map_fit or not KEEP_VIEW:
            # Fill-fit with crop-to-fill so no white space appears
            self._fit_map_to_window()
        else:
            # Even when KEEP_VIEW=true, center the image so you land somewhere sensible
            self._center_map_image()
        self._first_map_fit = False

        self._set_calib_mode(False)
        self._set_pin_drop_mode(False)
        self._exit_edit_mode()
        
        # Sync combo without triggering _on_map_changed recursively
        idx = list(MAP_DEFINITIONS.keys()).index(map_name)
        self.map_combo.blockSignals(True)
        self.map_combo.setCurrentIndex(idx)
        self.map_combo.blockSignals(False)
        self.map_combo.setEnabled(True)
        
        # Refresh whichever panels happen to be open right now
        if self.calib_panel.isVisible():
            self._refresh_calib_list()
        if self.pin_panel.isVisible():
            self._refresh_pin_list()
        if self.markers_panel.isVisible():
            self._refresh_named_marker_list()
        if self.layer_panel.isVisible():
            self._rebuild_layer_panel_content()

        self._flash(f"Map: {map_name}")
        self.canvas.update()

    def _load_calib(self, map_name):
        """
        Load calibration points from the map's calibration file.
        Returns a list of (x, y) tuples. Logs load errors if file is invalid.
        """
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
        """
        Save current calibration points to the map's calibration file.
        Flashes a message and refreshes calibration list on success.
        """
        f = _calib_file(self.current_map_name)
        try:
            json.dump(self.calibration_points, open(f, "w"), indent=2)
            self._flash(f"Saved {len(self.calibration_points)} calibration points.")
            self._refresh_calib_list()
        except Exception as e:
            self._flash(f"Save error: {e}")

    def _load_pins(self, map_name):
        """
        Load dropped pins from the map's pin file.
        Returns a list of pins or empty list if file missing/invalid.
        """
        f = _pins_file(map_name)
        if os.path.exists(f):
            try:
                return json.load(open(f))
            except:
                pass
        return []

    def _save_pins(self):
        """
        Save dropped pins to the map's pin file.
        Logs errors if saving fails.
        """
        f = _pins_file(self.current_map_name)
        try:
            json.dump(self.drop_pins, open(f, "w"), indent=2)
        except Exception as e:
            print(f"Pin save error: {e}")

    def _refresh_title(self):
        """
        Update the window title with the app name and version.
        """
        self.setWindowTitle(f"{APP_NAME}  v{APP_VERSION}")

    def _restore_window_geometry(self):
        """
        Restore window geometry from config if PERSIST_GEOMETRY is True.
        Falls back to default size and position if load fails.
        """
        if not PERSIST_GEOMETRY:
            self.resize(WIN_W, WIN_H)
            return

        try:
            x = WIN_X
            y = WIN_Y
            w = WIN_W
            h = WIN_H

            self.setGeometry(x, y, max(300, w), max(250, h))
            return

        except Exception as e:
            print(f"[window] geometry restore failed: {e}")

        self.resize(WIN_W, WIN_H)
        
    def _save_window_geometry(self):
        """Save current window geometry to config if PERSIST_GEOMETRY is True."""
        if not PERSIST_GEOMETRY:
            return

        try:
            # Read all lines from the INI
            with open(_INI_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()

            in_window_section = False
            keys_to_update = {
                "win_x": str(self.x()),
                "win_y": str(self.y()),
                "win_w": str(self.width()),
                "win_h": str(self.height())
            }

            new_lines = []
            for line in lines:
                stripped = line.strip()
                
                # Detect section headers
                if stripped.startswith("[") and stripped.endswith("]"):
                    in_window_section = (stripped[1:-1].lower() == "window")

                # If we are in the window section, replace the keys
                if in_window_section and "=" in line:
                    key = line.split("=", 1)[0].strip().lower()
                    if key in keys_to_update:
                        # Keep any comment at the end of the line
                        parts = line.split(";", 1)
                        comment = f";{parts[1]}" if len(parts) > 1 else ""
                        line = f"{key} = {keys_to_update[key]} {comment}\n"

                new_lines.append(line)

            # Write the updated lines back to the INI
            with open(_INI_PATH, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

            print(f"[config] Saved window geometry to {_INI_PATH} (comments preserved)")

        except Exception as e:
            print(f"[window] geometry save failed: {e}")

    def _schedule_geom_save(self):
        """
        Start or restart the debounce timer for saving window geometry.
        Prevents disk write on every small resize/move event.
        """
        if PERSIST_GEOMETRY:
            self._geom_save_timer.start(350)
    
     # ==========================================================
    # MAP FITTING  —  fill / crop mode (no white space)
    # ==========================================================
    def _fit_map_to_window(self):
        """
        Scale map to FILL the canvas (crop-to-fill). Uses MAX(fit_w, fit_h)
        so the map covers every pixel with no white bars. Old code used MIN
        which caused white bars on sides/top -- now fixed.
        After fitting, centers the image in the canvas.
        """
        cw = max(1, self.canvas.width() or self.width())
        ch = max(1, self.canvas.height() or self.height() - TOP_BAR_HEIGHT)
        if self.map_layers and not self.map_layers[0].isNull():
            fit_w = cw / self.map_layers[0].width()
            fit_h = ch / self.map_layers[0].height()
            # MAX = fill (may crop edges); MIN = letterbox (shows white bars)
            self.zoom = max(max(fit_w, fit_h), MIN_ZOOM)
        else:
            self.zoom = 1.0
         # Always center after fitting
        self._center_map_image()

    def _center_map_image(self):
        """
        Center the map image in the canvas at the current zoom level.
        Does not alter zoom, just recalculates offsets for centering.
        """
        if not self.map_layers or self.map_layers[0].isNull():
            self.offset_x = 0.0; self.offset_y = 0.0; return
        cw = self.canvas.width()  or self.width()
        ch = self.canvas.height() or self.height() - TOP_BAR_HEIGHT
        mw = self.map_layers[0].width()  * self.zoom
        mh = self.map_layers[0].height() * self.zoom
        # Center the scaled map rect inside the canvas
        self.offset_x = (cw - mw) / 2.0
        self.offset_y = (ch - mh) / 2.0
    
    # ==========================================================
    # PLAYER DOT ANIMATION
    # ==========================================================
    
    def _tick_pulse(self):
        """Advance the pulse ring animation and request a redraw."""
        self.pulse_phase = (self.pulse_phase + 0.12) % (math.tau * 2)
        self.canvas.update()
    
    # ==========================================================
    # WINDOW VISIBILITY  (Shift+M toggle — minimize / restore)
    # ==========================================================
    
    def _toggle_window_visibility(self):
        """
        Minimize if visible+normal; restore if minimized or hidden.
        Called by global hotkey thread AND fallback Qt shortcut.
        Works system-wide because hotkey thread uses RegisterHotKey.
        """
        if self.isMinimized() or not self.isVisible():
            # Restore: bring it back from the taskbar / hidden state
            self.showNormal()
            self.activateWindow()
            self.raise_()
        else:
            # Minimize: tuck it into the taskbar
            self.showMinimized()
    
    def _load_named_markers(self, map_name):
        """
        Load named markers from the map's marker file.
        Supports both 'wy' and legacy 'wz' keys for Y values.
        Returns a cleaned list of marker dicts with name, wx, and wy.
        """
        f = _markers_file(map_name)
        if os.path.exists(f):
            try:
                with open(f, encoding="utf-8") as fp:
                    data = json.load(fp)
                out = []
                for m in data:
                    wy = float(m["wy"]) if "wy" in m else float(m["wz"])
                    out.append({
                        "name": str(m.get("name", "Marker")),
                        "wx": float(m["wx"]),
                        "wy": wy,
                    })
                return out
            except Exception as e:
                print(f"Named markers load error: {e}")
        return []

    def _save_named_markers(self):
        """
        Save current named markers to the map's marker file.
        Writes JSON with readable formatting. Logs errors if save fails.
        """
        f = _markers_file(self.current_map_name)
        try:
            with open(f, "w", encoding="utf-8") as fp:
                json.dump(self.named_markers, fp, indent=2)
        except Exception as e:
            print(f"Named markers save error: {e}")

    def _build_ui(self):
        """
        Build the full UI layout using the UIPanels mixin.
        Delegates actual construction of panels and widgets.
        """
        return OverlayUIPanelsMixin._build_ui(self)

    # ----------------------------------------------------------
    # Settings Panel  (new in v4.0)
    # ----------------------------------------------------------
    def _make_settings_panel(self, parent):
        """
        Create the settings panel UI.
        Delegates to UIPanels mixin for layout and controls.
        """
        return OverlayUIPanelsMixin._make_settings_panel(self, parent)

    def _on_auto_center_changed(self, state):
        """
        Handle checkbox change for auto-centering on player location.
        Updates internal flag via UIPanels mixin.
        """
        return OverlayUIPanelsMixin._on_auto_center_changed(self, state)

    def _on_auto_zoom_changed(self, state):
        """
        Handle checkbox change for auto-zoom behavior.
        Updates internal flag via UIPanels mixin.
        """
        return OverlayUIPanelsMixin._on_auto_zoom_changed(self, state)

    def _toggle_settings_panel(self):
        """
        Toggle visibility of the settings panel.
        Delegates behavior to UIPanels mixin.
        """
        return OverlayUIPanelsMixin._toggle_settings_panel(self)

    # ----------------------------------------------------------
    # Layers Panel
    # ----------------------------------------------------------
    def _make_layer_panel(self, parent):
        """
        Create the layer selection panel UI.
        Allows toggling visibility of map layers.
        """
        return OverlayUIPanelsMixin._make_layer_panel(self, parent)

    def _rebuild_layer_panel_content(self):
        """
        Rebuild the layer panel contents dynamically.
        Reflects current map layers and their visibility states.
        """
        return OverlayUIPanelsMixin._rebuild_layer_panel_content(self)

    def _on_layer_toggled(self, idx, state):
        """
        Handle toggling of an individual map layer.
        Updates visibility state and refreshes canvas.
        """
        return OverlayUIPanelsMixin._on_layer_toggled(self, idx, state)

    def _layers_all_on(self):
        """
        Enable visibility for all map layers at once.
        """
        return OverlayUIPanelsMixin._layers_all_on(self)

    def _layers_all_off(self):
        """
        Disable visibility for all map layers at once.
        """
        return OverlayUIPanelsMixin._layers_all_off(self)

    # ----------------------------------------------------------
    # Calibration Panel
    # ----------------------------------------------------------
    def _make_calib_panel(self, parent):
        """
        Create the calibration panel UI.
        Used for adding, editing, and managing calibration points.
        """
        return OverlayUIPanelsMixin._make_calib_panel(self, parent)

    def _make_pin_panel(self, parent):
        """
        Create the pin panel UI.
        Allows creating, renaming, and managing map pins.
        """
        return OverlayUIPanelsMixin._make_pin_panel(self, parent)

    # ----------------------------------------------------------
    # Named markers (typed world X / Z / optional Y)
    # ----------------------------------------------------------
    def _make_markers_panel(self, parent):
        """
        Create the named markers panel UI.
        Allows adding markers using world coordinates.
        """
        return OverlayUIPanelsMixin._make_markers_panel(self, parent)

    # ===========================================================
    # Layout
    # ===========================================================

    def _relayout(self):
        """
        Recalculate and apply layout for all UI elements.
        Positions panels, canvas, and flash label based on window size.
        """
        w, h = self.width(), self.height()
        self.canvas.setGeometry(0, 0, w, h)
        self.top_bar.setGeometry(0, 0, w, TOP_BAR_HEIGHT)
        pw = PANEL_WIDTH
        ph = min(h - TOP_BAR_HEIGHT - 8, 600)
        py = TOP_BAR_HEIGHT + 4
        self.layer_panel.setGeometry(w - pw - 6, py, pw, ph)
        self.calib_panel.setGeometry(w - pw - 6, py, pw, ph)
        self.pin_panel.setGeometry(w - pw - 6, py, pw, ph)
        self.markers_panel.setGeometry(w - pw - 6, py, pw, ph)
        self.settings_panel.setGeometry(w - pw - 6, py, pw, ph)
        if not self.flash_lbl.isHidden():
            self.flash_lbl.adjustSize()
            self.flash_lbl.move(
                (w - self.flash_lbl.width())  // 2,
                h // 2 - 60
            )

    def resizeEvent(self, event):
        """
        Handle window resize events.
        Triggers layout recalculation and schedules geometry save.
        """
        super().resizeEvent(event)
        self._relayout()
        self._schedule_geom_save()

    def moveEvent(self, event):
        """
        Handle window move events.
        Schedules geometry save to persist window position.
        """
        super().moveEvent(event)
        self._schedule_geom_save()

    # ===========================================================
    # Map switching
    # ===========================================================

    def _on_map_changed(self, map_name):
        """
        Handle map selection change from UI.
        Loads the selected map if it differs from current.
        """
        if map_name and map_name != self.current_map_name:
            self._load_map(map_name)

    # ===========================================================
    # Zoom / Center
    # ===========================================================

    def _zoom_in(self):
        """
        Increase zoom level while keeping the view centered.
        Respects calibration zoom lock if enabled.
        """
        if self.calib_mode and LOCK_ZOOM_CAL and CAL_SNAP_ZOOM > 0:
            self.zoom = CAL_SNAP_ZOOM
            self.canvas.update()
            return
        old = self.zoom
        self.zoom = min(self.zoom * (1 + ZOOM_STEP), MAX_ZOOM)
        cx, cy = self.canvas.width()/2, self.canvas.height()/2
        self.offset_x = cx - (cx - self.offset_x) * (self.zoom / old)
        self.offset_y = cy - (cy - self.offset_y) * (self.zoom / old)
        self.canvas.update()

    def _zoom_out(self):
        """
        Decrease zoom level while keeping the view centered.
        Respects calibration zoom lock if enabled.
        """
        if self.calib_mode and LOCK_ZOOM_CAL and CAL_SNAP_ZOOM > 0:
            self.zoom = CAL_SNAP_ZOOM
            self.canvas.update()
            return
        old = self.zoom
        self.zoom = max(self.zoom * (1 - ZOOM_STEP), MIN_ZOOM)
        cx, cy = self.canvas.width()/2, self.canvas.height()/2
        self.offset_x = cx - (cx - self.offset_x) * (self.zoom / old)
        self.offset_y = cy - (cy - self.offset_y) * (self.zoom / old)
        self.canvas.update()

    def _center_on_player(self):
        """
        Center the map view on the player's current location.
        Converts world coordinates to pixel space before centering.
        """
        if self.current_loc is None:
            return
        ipx, ipy = world_to_pixel(
            self.current_loc[0], self.current_loc[1], self.xc, self.yc)
        self.offset_x = self.canvas.width()/2  - ipx * self.zoom
        self.offset_y = self.canvas.height()/2 - ipy * self.zoom
        self.canvas.update()

    # ===========================================================
    # Opacity cycle
    # ===========================================================

    _opacity_cycle = [0.25, 0.5, 0.75, 0.85, 1.0]

    def _cycle_opacity(self):
        """
        Cycle through predefined opacity levels.
        Updates window transparency and button label.
        """
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

    def _toggle_layer_panel(self):
        """
        Toggle visibility of the layer panel.
        Hides other panels when shown.
        """
        vis = not self.layer_panel.isVisible()
        self.layer_panel.setVisible(vis)
        if vis:
            self._rebuild_layer_panel_content()
            self.calib_panel.hide()
            self.pin_panel.hide()
            self.markers_panel.hide()

    def _toggle_calib_panel(self):
        """
        Toggle visibility of the calibration panel.
        Refreshes calibration list and disables conflicting modes.
        """
        vis = not self.calib_panel.isVisible()
        self.calib_panel.setVisible(vis)
        if vis:
            self._calib_title_lbl.setText(f"Calibration  —  {self.current_map_name}")
            self._refresh_calib_list()
            self.pin_panel.hide()
            self.layer_panel.hide()
            self.markers_panel.hide()
            self._set_pin_drop_mode(False)

    def _toggle_pin_panel(self):
        """
        Toggle visibility of the pin panel.
        Refreshes pin list and disables calibration mode.
        """
        vis = not self.pin_panel.isVisible()
        self.pin_panel.setVisible(vis)
        if vis:
            self._refresh_pin_list()
            self.calib_panel.hide()
            self.layer_panel.hide()
            self.markers_panel.hide()
            self._set_calib_mode(False)

    def _toggle_markers_panel(self):
        """
        Toggle visibility of the markers panel.
        Refreshes marker list and disables other editing modes.
        """
        vis = not self.markers_panel.isVisible()
        self.markers_panel.setVisible(vis)
        if vis:
            self._refresh_named_marker_list()
            self.calib_panel.hide()
            self.layer_panel.hide()
            self.pin_panel.hide()
            self._set_calib_mode(False)
            self._set_pin_drop_mode(False)

    def _refresh_named_marker_list(self):
        """
        Refresh the markers list UI with current marker data.
        Formats each entry with name and coordinates.
        """
        self.markers_list.clear()
        for m in self.named_markers:
            if "wy" in m:
                map_y = float(m["wy"])
            elif "wz" in m:
                map_y = float(m["wz"])
            else:
                continue
            self.markers_list.addItem(
                f"◎ {m['name']}  X={m['wx']:.2f} Y={map_y:.2f}")

    def _add_named_marker_from_fields(self):
        """
        Create a new named marker from input fields.
        Validates input, adds marker, saves, and updates UI.
        """
        try:
            wx = float(self.marker_x_edit.text().strip())
            wmy = float(self.marker_map_y_edit.text().strip())
        except ValueError:
            self._flash("Markers: enter valid X (token 1) and Y map (token 3).")
            return
        name = self.marker_name_edit.text().strip() or "Marker"
        rec = {"name": name, "wx": wx, "wy": wmy}
        self.named_markers.append(rec)
        self.marker_x_edit.clear()
        self.marker_map_y_edit.clear()
        self.marker_name_edit.clear()
        self._refresh_named_marker_list()
        self._save_named_markers()
        self._flash(f"Marker '{name}' added.")
        self.canvas.update()

    def _delete_selected_named_marker(self):
        """
        Delete the currently selected marker from the list.
        Updates storage and UI after removal.
        """
        row = self.markers_list.currentRow()
        if 0 <= row < len(self.named_markers):
            self.named_markers.pop(row)
            self._refresh_named_marker_list()
            self._save_named_markers()
            self._flash("Marker removed.")
            self.canvas.update()
        else:
            self._flash("Select a marker first.")

    def _clear_all_named_markers(self):
        """
        Remove all named markers for the current map.
        Clears list, saves state, and updates UI.
        """
        if not self.named_markers:
            return
        self.named_markers.clear()
        self._refresh_named_marker_list()
        self._save_named_markers()
        self._flash("All markers cleared.")
        self.canvas.update()

    def _save_named_markers_flash(self):
        """
        Save named markers and show confirmation message.
        """
        self._save_named_markers()
        self._flash(f"Saved {len(self.named_markers)} markers.")

    # ===========================================================
    # Location update -- /loc -> /jumploc clipboard event
    # ===========================================================

    # Moved to overlay_location_update.py and overlay_update_download.py

    # ===========================================================
    # Calibration mode
    # ===========================================================

    def _toggle_calib_mode(self):
        """
        Toggle calibration mode on/off.
        Delegates behavior to editing mixin.
        """
        self._set_calib_mode(not self.calib_mode)

    def _set_calib_mode(self, enabled: bool):
        """
        Enable or disable calibration mode.
        Handles UI and behavior changes via mixin.
        """
        return OverlayEditingMixin._set_calib_mode(self, enabled)

    # ===========================================================
    # Pin-drop mode
    # ===========================================================

    def _on_pin_name_changed(self, text):
        """
        Update pending pin name as user types.
        Used when placing new pins on the map.
        """
        self.pending_pin_name = text.strip()
        self.canvas.update()

    def _toggle_pin_drop_mode(self):
        """
        Toggle pin-drop mode on/off.
        Allows placing pins via double-click.
        """
        self._set_pin_drop_mode(not self.pin_drop_mode)

    def _set_pin_drop_mode(self, enabled: bool):
        """
        Enable or disable pin-drop mode.
        Delegates logic to editing mixin.
        """
        return OverlayEditingMixin._set_pin_drop_mode(self, enabled)

    # ===========================================================
    # Edit mode
    # ===========================================================

    def _edit_selected_calib(self):
        """
        Enter edit mode for selected calibration point.
        """
        return OverlayEditingMixin._edit_selected_calib(self)

    def _edit_selected_pin(self):
        """
        Enter edit mode for selected pin.
        """
        return OverlayEditingMixin._edit_selected_pin(self)

    def _enter_edit_mode(self, edit_type: str, index: int):
        """
        Enter edit mode for a specific item (pin or calibration point).
        """
        return OverlayEditingMixin._enter_edit_mode(self, edit_type, index)

    def _exit_edit_mode(self):
        """
        Exit edit mode and reset related state.
        """
        return OverlayEditingMixin._exit_edit_mode(self)

    # ===========================================================
    # List helpers
    # ===========================================================

    def _refresh_calib_list(self):
        """
        Refresh calibration points list UI.
        """
        return OverlayEditingMixin._refresh_calib_list(self)

    def _refresh_pin_list(self):
        """
        Refresh pins list UI.
        """
        return OverlayEditingMixin._refresh_pin_list(self)

    def _delete_selected_calib(self):
        """
        Delete selected calibration point.
        """
        return OverlayEditingMixin._delete_selected_calib(self)

    def _clear_all_calib(self):
        """
        Remove all calibration points.
        """
        return OverlayEditingMixin._clear_all_calib(self)

    def _delete_selected_pin(self):
        """
        Delete selected pin.
        """
        return OverlayEditingMixin._delete_selected_pin(self)

    def _clear_all_pins(self):
        """
        Remove all pins.
        """
        return OverlayEditingMixin._clear_all_pins(self)

    def _rename_selected_pin(self):
        """
        Rename selected pin using input field.
        """
        return OverlayEditingMixin._rename_selected_pin(self)

    def _save_pins_flash(self):
        """
        Save pins and show confirmation message.
        """
        return OverlayEditingMixin._save_pins_flash(self)

    # ===========================================================
    # Double-click handler
    # ===========================================================

    def handle_double_click(self, img_x, img_y):
        """
        Handle double-click events on the map canvas.
        Used for calibration, pin placement, or editing.
        """
        return OverlayEditingMixin.handle_double_click(self, img_x, img_y)

    # ===========================================================
    # Flash
    # ===========================================================

    def _flash(self, text):
        """
        Display a temporary message overlay (flash message).
        """
        return OverlayEditingMixin._flash(self, text)

    # ===========================================================
    # Clipboard watcher
    # ===========================================================

    def _watch_clipboard(self):
        """
        Monitor clipboard for /loc or /jumploc updates.
        Triggers location updates when detected.
        """
        return OverlayLocationUpdateMixin._watch_clipboard(self)

    def _on_repaint_needed(self):
        """
        Handle repaint signal from background threads.
        Forces canvas update safely on main thread.
        """
        return OverlayLocationUpdateMixin._on_repaint_needed(self)

    def closeEvent(self, event):
        """
        Handle window close event.
        Saves geometry, stops threads, and shuts down application cleanly.
        """
        self._save_window_geometry()
        self.running = False
        # Tell the global hotkey thread to unregister and exit cleanly
        if hasattr(self, "_hotkey_thread"):
            self._hotkey_thread.stop()
        QApplication.quit()


# ==============================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MapOverlay()
    win.show()
    sys.exit(app.exec_())
