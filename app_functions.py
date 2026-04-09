import os

import numpy as np

from app_settings import GAME_Z_I, MAPS_DIR, MAP_X_I, MAP_Y_I, SETTINGS_DIR, _safe_key


def _calib_file(map_name: str) -> str:
    """Return the full path to the calibration JSON file for a given map name."""
    return os.path.join(SETTINGS_DIR, f"calibration_{_safe_key(map_name)}.json")


def _pins_file(map_name: str) -> str:
    """Return the full path to the pins JSON file for a given map name."""
    return os.path.join(SETTINGS_DIR, f"pins_{_safe_key(map_name)}.json")


def _markers_file(map_name: str) -> str:
    """Return the full path to the named markers JSON file for a given map name."""
    return os.path.join(SETTINGS_DIR, f"named_markers_{_safe_key(map_name)}.json")


def _map_layer_path(map_name: str, layer_file: str) -> str:
    """Return the full path to a specific map layer file in the maps directory."""
    return os.path.join(MAPS_DIR, layer_file)


def compute_affine_transform(pts):
    """Compute affine transform coefficients to map world coordinates to image pixels.  
    Requires at least 3 calibration points; returns two arrays for X and Y transformations."""
    if len(pts) < 3:
        return np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])
    A, bpx, bpy = [], [], []
    for img_x, img_y, map_x, map_y in pts:
        A.append([map_x, map_y, 1])
        bpx.append(img_x)
        bpy.append(img_y)
    A = np.array(A, dtype=float)
    bpx = np.array(bpx, dtype=float)
    bpy = np.array(bpy, dtype=float)
    xc, _, _, _ = np.linalg.lstsq(A, bpx, rcond=None)
    yc, _, _, _ = np.linalg.lstsq(A, bpy, rcond=None)
    return xc, yc


def world_to_pixel(map_x, map_y, xc, yc):
    """Convert world coordinates (map X/Y) to pixel coordinates using affine transform arrays."""
    return (xc[0] * map_x + xc[1] * map_y + xc[2], yc[0] * map_x + yc[1] * map_y + yc[2])


def pixel_to_world(img_px, img_py, xc, yc):
    """Convert pixel coordinates back to world coordinates using affine transform arrays.  
    Returns NaN if the transform is singular."""
    A = np.array([[xc[0], xc[1]], [yc[0], yc[1]]], dtype=float)
    det = float(np.linalg.det(A))
    if abs(det) < 1e-14:
        return float("nan"), float("nan")
    v = np.array([img_px - xc[2], img_py - yc[2]], dtype=float)
    w = np.linalg.solve(A, v)
    return float(w[0]), float(w[1])


def jumploc_map_xy(parts: list, mx_i: int = None, my_i: int = None) -> tuple:
    """Extract world X/Y coordinates from a /jumploc token list.  
    Defaults to configured MAP_X_I and MAP_Y_I indices."""
    mx_i = MAP_X_I if mx_i is None else mx_i
    my_i = MAP_Y_I if my_i is None else my_i
    return float(parts[mx_i]), float(parts[my_i])


def jumploc_game_z(parts: list):
    """Extract the game Z coordinate from a /jumploc token list if available.  
    Returns None if the Z index is not set or out of range."""
    if GAME_Z_I <= 0:
        return None
    if len(parts) <= GAME_Z_I:
        return None
    return float(parts[GAME_Z_I])


def _jumploc_required_token_count() -> int:
    """Return the minimum number of tokens required for a /jumploc line.  
    Considers X, Y, and optionally Z indices."""
    n = max(MAP_X_I, MAP_Y_I)
    if GAME_Z_I > 0:
        n = max(n, GAME_Z_I)
    return n
