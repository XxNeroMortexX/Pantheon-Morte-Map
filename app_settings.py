# Pantheon Morte Map — Current Release Version
APP_VERSION = "4.1.2.0"

APP_NAME = "Pantheon Morte Map"
APP_AUTHOR = "NeroMorte (AKA Morte)"
APP_DESCRIPTION = "Pantheon Morte Map Viewer"
APP_COPYRIGHT = "© 2026 NeroMorte"
APP_FILENAME = "Pantheon_Morte_Map.exe"

import configparser
import os
import sys
import ctypes

from PyQt5.QtGui import QColor

def resource_path(relative_path):
    """Return the absolute path to a resource file.  
    Handles both frozen executables and normal script runs."""
    base_path = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(
        os.path.abspath(__file__)
    )
    return os.path.join(base_path, relative_path)


_SETTINGS_DIR_EARLY = resource_path("Settings")
_INI_PATH = os.path.join(_SETTINGS_DIR_EARLY, "config.ini")

_INI_DEFAULTS = {
    "window": {
        "win_x": "100",
        "win_y": "100",
        "win_w": "1024",
        "win_h": "768",
        "default_opacity": "0.85",
        "top_bar_height": "76",
        "panel_width": "340",
        "flash_duration": "4000",
        "persist_window_geometry": "true",
        "keep_view_on_map_change": "true",
    },
    "zoom": {
        "min_zoom": "0.01",
        "max_zoom": "18.0",
        "zoom_step": "0.12"
    },
    "pins_and_calibration": {
        "dot_size": "14",
        "calib_dot_size": "12",
        "pin_w": "22",
        "pin_h": "30",
        "update_threshold": "50",
    },
    "layers": {
        "lower_layer_opacity": "0.75"
    },
    "cache": {
        "map_cache_resolution": "4k"
    },
    "colors": {
        "player_fill": "#ff3232",
        "player_ring": "#b40000",
        "player_outer_ring": "#ff5050",
        "ping_cross": "#ffb400",
        "ping_circle": "#ffb400",
        "cal_stroke": "#000000",
        "cal_fill": "#fff0f0",
        "cal_label": "#ffffb4",
        "cal_edit_stroke": "#ffdc00",
        "cal_edit_fill": "#fff064",
        "pin_stroke": "#640000",
        "pin_fill": "#d21e1e",
        "pin_highlight_stroke": "#ffdc00",
        "pin_highlight_fill": "#ffc800",
        "pin_label": "#ffdc50",
        "pin_label_shadow": "#000000",
        "marker_fill": "#2ee8c8",
        "marker_ring": "#00a88c",
        "marker_label": "#b0fff0",
    },
    "player_animation": {
        "pulse_rings": "2",
        "pulse_speed": "2.5",
        "pulse_extent": "1.35",
        "pulse_interval_ms": "40",
    },
    "keybinds": {
        "toggle_map_visibility": "Shift+M"
    },
    "jumploc": {
        "map_x_index": "1",
        "map_y_index": "3",
        "game_z_index": "2"
    },
    "calibration_extra": {
        "cal_mode_snap_zoom": "1.0",
        "lock_zoom_in_cal_mode": "false"
    },
    "update": {
        "manifest_url": "https://raw.githubusercontent.com/XxNeroMortexX/Pantheon-Morte-Map/refs/heads/main/update_manifest.json"
    },
    "location_behavior": {
        "auto_center_on_loc": "true",
        "auto_zoom_on_loc": "false"
    },
    "map_z_layers": {
        "Main_Map_Z_World": "0,0",
        "Halnir_Cave_Z_Upper": "39,41",
        "Halnir_Cave_Z_Mid": "0,0",
        "Halnir_Cave_Z_Lower": "0,0",
        "Goblin_Cave_Z_Upper": "0,0",
        "Goblin_Cave_Z_Mid": "0,0",
        "Goblin_Cave_Z_Lower": "0,0",
        "Black_Rose_Keep_Z_Upper_Dungeon": "0,0",
        "Black_Rose_Keep_Z_Mid_Dungeon": "0,0",
        "Black_Rose_Keep_Z_Lower_Dungeon_1": "0,0",
        "Black_Rose_Keep_Z_Lower_Dungeon_2": "0,0",
        "Black_Rose_Keep_Z_Reference": "0,0",
        "Wildmound_Cradle_Z_Reference": "0,0",
        "Wildmound_Cradle_Z_Lower_Dungeon": "0,0",
        "Wildmound_Cradle_Z_Mid_Dungeon": "0,0",
        "Wildmound_Cradle_Z_Upper_Dungeon": "0,0",
        "Nightfall_Crypt_Z_Lower_2": "0,0",
        "Nightfall_Crypt_Z_Lower_1": "0,0",
        "Nightfall_Crypt_Z_Mid": "0,0",
        "Nightfall_Crypt_Z_Upper": "0,0",
    },
}


def _write_ini_with_comments(path: str):
    """Write the default config INI file with helpful comments for each section.  
    Creates directories if needed and includes instructions for the user."""
    lines = []
    lines.append("; ================================================================")
    lines.append("; Pantheon Morte Map v{APP_VERSION} —  User Configuration")
    lines.append("; Edit values below, then restart the app for changes to take effect.")
    lines.append("; Lines starting with ; are comments and are ignored.")
    lines.append("; ================================================================")
    lines.append("")

    comment_map = {
        # window
        "win_x":           "; Window X position (pixels from left edge of screen)",
        "win_y":           "; Window Y position (pixels from top edge of screen)",
        "win_w":           "; Width of the map window when it first opens (pixels)",
        "win_h":           "; Height of the map window when it first opens (pixels)",
        "default_opacity": "; Starting window opacity  0.0=invisible  1.0=fully opaque",
        "top_bar_height":  "; Height of the top toolbar in pixels",
        "panel_width":     "; Width of the side panels (CAL / PINS / LAYERS) in pixels",
        "flash_duration":  "; How long flash messages stay on screen (milliseconds)",
        "persist_window_geometry": "; Enable saving/restoring window position and size",
        "keep_view_on_map_change": "; Keep zoom/pan when changing maps (still reload cal/pins)",
        # zoom
        "min_zoom":        "; Minimum zoom level  (0.01 lets you zoom way out for huge maps)",
        "max_zoom":        "; Maximum zoom level",
        "zoom_step":       "; How fast each scroll tick zooms (fraction of current zoom)",
        # pins_and_calibration
        "dot_size":           "; Radius of the player position dot in pixels",
        "calib_dot_size":     "; Diameter of calibration marker dots in pixels",
        "pin_w":              "; Width of drop-pin teardrop in pixels",
        "pin_h":              "; Height of drop-pin teardrop in pixels",
        "update_threshold":   "; Double-click within this many pixels to update existing cal point",
        # layers
        "lower_layer_opacity": "; Opacity of layers below the topmost visible layer  (0.75 recommended)",
        # cache
        "map_cache_resolution": (
            "; Resolution to cache large map images at.\n"
            "; Options: 720p  1080p  1440p  2k  4k  8k  16k\n"
            "; Cached copies sit next to originals (e.g. main_map_4k.png).\n"
            "; First load is slow while the cache is built; every load after is fast.\n"
            "; Delete the cached files to rebuild at a new resolution."
        ),
        # colors (representative; others get same section header)
        "player_fill":     "; Player dot fill #RRGGBB",
        "marker_fill":     "; Named world markers (typed coords) fill color",
        "pulse_rings":     "; Extra animated pulse ring count (0 disables)",
        "toggle_map_visibility": "; Qt key sequence to hide/show window",
        "map_x_index":     "; /jumploc parts[] index for map X (left ↔ right)",
        "map_y_index":     "; /jumploc parts[] index for map Y (up ↔ down on map)",
        "game_z_index":    "; Token for game Z only (layer pick); 0=off; not used for dot position or status line",
        "cal_mode_snap_zoom": "; Zoom level when entering CAL mode (0 = leave zoom unchanged)",
        "manifest_url":    "; Raw URL for update_manifest.json (GitHub raw)",
    }
    
    section_comments = {
        "map_z_layers": "; Per-map Z-value to layer selection.\n; Format: <map_safe_key>_Z_<LayerName> = <min_z>,<max_z>"
    }

    for section, keys in _INI_DEFAULTS.items():
        if section in section_comments:
            for line in section_comments[section].split("\n"):
                lines.append(line)
        lines.append(f"[{section}]")
        for key, value in keys.items():
            if key in comment_map:
                for cline in comment_map[key].split("\n"):
                    lines.append(cline)
            lines.append(f"{key} = {value}")
            lines.append("")
        lines.append("")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _dedupe_ini_file(path: str):
    """Remove duplicate section keys case-insensitively, keeping the first entry.
    This recovers older merged configs that accidentally appended lowercase
    duplicates of existing template keys."""
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    rendered = []
    current_section = None
    seen_keys = {}

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1].strip()
            seen_keys.setdefault(current_section.casefold(), set())
            rendered.append(line)
            continue

        if current_section and stripped and not stripped.startswith((";", "#")) and "=" in line:
            key_name = line.partition("=")[0].strip()
            section_key = current_section.casefold()
            normalized_key = key_name.casefold()
            if normalized_key in seen_keys.setdefault(section_key, set()):
                continue
            seen_keys[section_key].add(normalized_key)

        rendered.append(line)

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(rendered).rstrip() + "\n")
        

def _load_ini() -> configparser.ConfigParser:
    """Load the configuration INI file, creating it if it doesn't exist.  
    Returns a ConfigParser object with defaults applied."""
    cfg = configparser.ConfigParser()
    for section, keys in _INI_DEFAULTS.items():
        cfg[section] = keys
    if not os.path.exists(_INI_PATH):
        _write_ini_with_comments(_INI_PATH)
        print(f"[config] Created default config: {_INI_PATH}")
    else:
        try:
            cfg.read(_INI_PATH, encoding="utf-8")
        except configparser.DuplicateOptionError:
            _dedupe_ini_file(_INI_PATH)
            cfg.read(_INI_PATH, encoding="utf-8")
        print(f"[config] Loaded config: {_INI_PATH}")
    return cfg


def _parse_hex_color(s: str, default: QColor) -> QColor:
    """Parse a hex color string (e.g., '#RRGGBB' or '#AARRGGBB') into a QColor.  
    Falls back to the provided default on invalid input."""
    s = (s or "").strip()
    if not s.startswith("#"):
        return QColor(default)
    h = s[1:]
    try:
        if len(h) == 6:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return QColor(r, g, b)
        if len(h) == 8:
            a, r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16)
            return QColor(r, g, b, a)
    except ValueError:
        pass
    return QColor(default)


def _build_theme(cfg: configparser.ConfigParser) -> dict:
    """Build a dictionary of QColor objects from the 'colors' section of the config.  
    Returns an empty dict if no colors section is present."""
    out = {}
    if "colors" not in cfg:
        return out
    for key in cfg["colors"]:
        out[key] = _parse_hex_color(cfg.get("colors", key), QColor(255, 255, 255))
    return out


_CFG = _load_ini()

WIN_X = _CFG.getint("window", "win_x", fallback=_INI_DEFAULTS["window"]["win_x"])
WIN_Y = _CFG.getint("window", "win_y", fallback=_INI_DEFAULTS["window"]["win_y"])
WIN_W = _CFG.getint("window", "win_w", fallback=_INI_DEFAULTS["window"]["win_w"])
WIN_H = _CFG.getint("window", "win_h", fallback=_INI_DEFAULTS["window"]["win_h"])
DEFAULT_OPACITY = _CFG.getfloat("window", "default_opacity", fallback=_INI_DEFAULTS["window"]["default_opacity"])
TOP_BAR_HEIGHT = _CFG.getint("window", "top_bar_height", fallback=_INI_DEFAULTS["window"]["top_bar_height"])
PANEL_WIDTH = _CFG.getint("window", "panel_width", fallback=_INI_DEFAULTS["window"]["panel_width"])
FLASH_DURATION = _CFG.getint("window", "flash_duration", fallback=_INI_DEFAULTS["window"]["flash_duration"])
PERSIST_GEOMETRY = _CFG.getboolean("window", "persist_window_geometry", fallback=_INI_DEFAULTS["window"]["persist_window_geometry"])
KEEP_VIEW = _CFG.getboolean("window", "keep_view_on_map_change", fallback=_INI_DEFAULTS["window"]["keep_view_on_map_change"])

MIN_ZOOM = _CFG.getfloat("zoom", "min_zoom", fallback=_INI_DEFAULTS["zoom"]["min_zoom"])
MAX_ZOOM = _CFG.getfloat("zoom", "max_zoom", fallback=_INI_DEFAULTS["zoom"]["max_zoom"])
ZOOM_STEP = _CFG.getfloat("zoom", "zoom_step", fallback=_INI_DEFAULTS["zoom"]["zoom_step"])

DOT_SIZE = _CFG.getint("pins_and_calibration", "dot_size", fallback=_INI_DEFAULTS["pins_and_calibration"]["dot_size"])
CALIB_DOT_SIZE = _CFG.getint("pins_and_calibration", "calib_dot_size", fallback=_INI_DEFAULTS["pins_and_calibration"]["calib_dot_size"])
PIN_W = _CFG.getint("pins_and_calibration", "pin_w", fallback=_INI_DEFAULTS["pins_and_calibration"]["pin_w"])
PIN_H = _CFG.getint("pins_and_calibration", "pin_h", fallback=_INI_DEFAULTS["pins_and_calibration"]["pin_h"])
UPDATE_THRESHOLD = _CFG.getint("pins_and_calibration", "update_threshold", fallback=_INI_DEFAULTS["pins_and_calibration"]["update_threshold"])

LOWER_LAYER_OPACITY = _CFG.getfloat("layers", "lower_layer_opacity", fallback=_INI_DEFAULTS["layers"]["lower_layer_opacity"])
MAP_CACHE_RESOLUTION = _CFG.get("cache", "map_cache_resolution", fallback=_INI_DEFAULTS["cache"]["map_cache_resolution"]).strip().lower()
THEME = _build_theme(_CFG)


def theme_q(key: str, default: QColor) -> QColor:
    """Return the QColor for a given theme key.  
    Uses the default if the key is missing or invalid."""
    c = THEME.get(key)
    if c is not None and c.isValid():
        return QColor(c)
    return QColor(default)


PULSE_RINGS = _CFG.getint("player_animation", "pulse_rings", fallback=_INI_DEFAULTS["player_animation"]["pulse_rings"])
PULSE_SPEED = _CFG.getfloat("player_animation", "pulse_speed", fallback=_INI_DEFAULTS["player_animation"]["pulse_speed"])
PULSE_EXTENT = _CFG.getfloat("player_animation", "pulse_extent", fallback=_INI_DEFAULTS["player_animation"]["pulse_extent"])
PULSE_INTERVAL_MS = _CFG.getint("player_animation", "pulse_interval_ms", fallback=_INI_DEFAULTS["player_animation"]["pulse_interval_ms"])

TOGGLE_MAP_KEYS = _CFG.get("keybinds", "toggle_map_visibility", fallback=_INI_DEFAULTS["keybinds"]["toggle_map_visibility"])
MAP_X_I = _CFG.getint("jumploc", "map_x_index", fallback=_INI_DEFAULTS["jumploc"]["map_x_index"])
MAP_Y_I = _CFG.getint("jumploc", "map_y_index", fallback=_INI_DEFAULTS["jumploc"]["map_y_index"])
GAME_Z_I = _CFG.getint("jumploc", "game_z_index", fallback=_INI_DEFAULTS["jumploc"]["game_z_index"])

CAL_SNAP_ZOOM = _CFG.getfloat("calibration_extra", "cal_mode_snap_zoom", fallback=_INI_DEFAULTS["calibration_extra"]["cal_mode_snap_zoom"])
LOCK_ZOOM_CAL = _CFG.getboolean("calibration_extra", "lock_zoom_in_cal_mode", fallback=_INI_DEFAULTS["calibration_extra"]["lock_zoom_in_cal_mode"])
UPDATE_MANIFEST_URL = _CFG.get("update", "manifest_url", fallback=_INI_DEFAULTS["update"]["manifest_url"]).strip()
AUTO_CENTER_ON_LOC = _CFG.getboolean("location_behavior", "auto_center_on_loc", fallback=_INI_DEFAULTS["location_behavior"]["auto_center_on_loc"])
AUTO_ZOOM_ON_LOC = _CFG.getboolean("location_behavior", "auto_zoom_on_loc", fallback=_INI_DEFAULTS["location_behavior"]["auto_zoom_on_loc"])

_RESOLUTION_MAP = {
    "720p": 1280,
    "1080p": 1920,
    "1440p": 2560,
    "2k": 2048,
    "4k": 4096,
    "8k": 8192,
    "16k": 16384,
}

SETTINGS_DIR = resource_path("Settings")
MAPS_DIR = resource_path("Maps")
WINDOW_ICON_PATH = resource_path("Pantheon_Morte_Map.ico")

MAP_DEFINITIONS = {
    "Main Map": [{"name": "World", "file": "World_z9.png"}],
    "Halnir Cave": [
        {"name": "Upper", "file": "HC_MAP_L1_UpperArea_z7.png"},
        {"name": "Mid", "file": "HC_MAP_L23_MidArea_z7.png"},
        {"name": "Lower", "file": "HC_MAP_L4_LowerArea_z7.png"},
    ],
    "Goblin Cave": [
        {"name": "Upper", "file": "HGC_Upper_clear_z6.png"},
        {"name": "Mid", "file": "HGC_Mid_clear_z6.png"},
        {"name": "Lower", "file": "HGC_Lower_clear_z6.png"},
    ],
    "Black Rose Keep": [
        {"name": "Upper Dungeon", "file": "BRK_1_Upper_Dungeon_Area_z6.png"},
        {"name": "Mid Dungeon", "file": "BRK_2_Mid_Dungeon_Area_z6.png"},
        {"name": "Lower Dungeon 1", "file": "BRK_3_Lower_Dungeon_Area_1_z6.png"},
        {"name": "Lower Dungeon 2", "file": "BRK_4_Lower_Dungeon_Area_2_z6.png"},
        {"name": "Reference", "file": "BRK_5_Dungeon_Reference_Layer_z6.png"},
    ],
    "Wildmound Cradle": [
        {"name": "Reference", "file": "WMC_0_Reference_Layer_z5.png"},
        {"name": "Lower Dungeon", "file": "WMC_01_Lower_Dungeon_z5.png"},
        {"name": "Mid Dungeon", "file": "WMC_02_Mid_Dungeon_z5.png"},
        {"name": "Upper Dungeon", "file": "WMC_03_Upper_Dungeon_z5.png"},
    ],
    "Nightfall Crypt": [
        {"name": "Lower 2", "file": "NFC_01_Lower2_z5.png"},
        {"name": "Lower 1", "file": "NFC_02_Lower1_z5.png"},
        {"name": "Mid", "file": "NFC_03_Mid_z5.png"},
        {"name": "Upper", "file": "NFC_04_Upper_z5.png"},
    ],
}


def _safe_key(map_name: str) -> str:
    """Return a normalized map name suitable for INI keys.  
    Converts to lowercase and replaces spaces with underscores."""
    return map_name.lower().replace(" ", "_")


def _load_map_z_layer_ranges(cfg):
    """Parse the 'map_z_layers' section of the config and return structured ranges.
    Maps safe keys to a list of tuples: (layer_name, min_z, max_z)."""
    
    result = {}
    
    if not cfg.has_section("map_z_layers"):
        return result

    for raw_key, val in cfg.items("map_z_layers"):
        raw_key_lower = raw_key.lower()
        sep = "_z_"
        idx = raw_key_lower.find(sep)
        if idx < 1:
            continue

        # Split map + layer
        safe_key_ini = raw_key_lower[:idx]
        layer_name_raw = raw_key_lower[idx + len(sep):]

        # Normalize layer name from config
        layer_name_safe = _safe_key(layer_name_raw)

        matched = None

        # Find matching map
        for mname, layers in MAP_DEFINITIONS.items():
            if _safe_key(mname) == safe_key_ini:

                for ld in layers:
                    if _safe_key(ld["name"]) == layer_name_safe:
                        matched = ld["name"]  # keep original case
                        break

                break  # stop once correct map found

        # Fallback if no match
        if matched is None:
            print(f"[z_layers] Warning: No layer match for '{raw_key}'")
            matched = layer_name_raw

        # Parse Z range
        parts = val.split(",")
        if len(parts) != 2:
            print(f"[z_layers] Bad format for '{raw_key}' -- expected 'min,max'")
            continue

        try:
            min_z = float(parts[0].strip())
            max_z = float(parts[1].strip())
        except ValueError:
            print(f"[z_layers] Non-numeric range for '{raw_key}'")
            continue

        result.setdefault(safe_key_ini, []).append((matched, min_z, max_z))

    return result


MAP_Z_LAYER_RANGES = _load_map_z_layer_ranges(_CFG)
