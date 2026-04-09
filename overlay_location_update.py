import time

import pyperclip

from app_functions import jumploc_game_z, jumploc_map_xy, _jumploc_required_token_count
from app_settings import MAP_DEFINITIONS, MAP_Z_LAYER_RANGES, UPDATE_THRESHOLD, _safe_key


class OverlayLocationUpdateMixin:
    """
    Handles live location updates and Z-layer logic for the map overlay.
    """
    def _on_loc_updated(self):
        """
        Called on main thread when clipboard watcher sees a fresh /jumploc.
        1. Optional zoom reset to 1.0  (auto_zoom checkbox in SET panel)
        2. Optional auto-center on player dot  (auto_center checkbox)
        3. Z-based layer auto-selection  (configured in [map_z_layers])
        """
        # Step 1: optional zoom reset
        if self.auto_zoom:
            self.zoom = 1.0

        # Step 2: optional auto-center on player dot
        if self.auto_center:
            self._center_on_player()

        # Step 3: Z-based layer auto-selection
        if self.current_game_z is not None:
            self._apply_z_layer(self.current_game_z)
        self.canvas.update()

    def _apply_z_layer(self, z_value: float):
        """
        Look up z_value in the per-map range table (from [map_z_layers] in config.ini).
        If a match is found, turn that layer ON and all others OFF, then sync
        the layer panel checkboxes. If no ranges configured, does nothing.
        """
        safe = _safe_key(self.current_map_name)
        ranges = MAP_Z_LAYER_RANGES.get(safe)
        if not ranges:
            return  # no Z-layer config for this map

        # Find the first range that Z falls into
        matched_layer = None
        for layer_name, min_z, max_z in ranges:
            lo, hi = min(min_z, max_z), max(min_z, max_z)
            if lo <= z_value <= hi:
                matched_layer = layer_name
                break

        if matched_layer is None:
            return  # Z doesn't match any configured range

        # Update layer_visible: only the matched layer is on
        layer_defs = MAP_DEFINITIONS.get(self.current_map_name, [])
        changed = False
        for i, ld in enumerate(layer_defs):
            want = (ld["name"] == matched_layer)
            if i < len(self.layer_visible) and self.layer_visible[i] != want:
                self.layer_visible[i] = want
                changed = True

        if changed:
            # Sync layer panel checkboxes so UI matches reality
            for i, cb in enumerate(self._layer_checkboxes):
                cb.blockSignals(True)
                cb.setChecked(self.layer_visible[i] if i < len(self.layer_visible) else False)
                cb.blockSignals(False)
            self._flash(f"Layer: {matched_layer}  (Z={z_value:.0f})")

    def _watch_clipboard(self):
        """
        Runs in a background thread to monitor the system clipboard.
        Detects new '/jumploc' entries, parses coordinates and game Z,
        updates current location, and emits signals to trigger map updates.
        """

        while self.running:
            try:
                text = pyperclip.paste().strip()
                if text.startswith("/jumploc"):
                    parts = text.split()
                    need = _jumploc_required_token_count()
                    if len(parts) <= need:
                        time.sleep(0.1)
                        continue

                    map_x, map_y = jumploc_map_xy(parts)
                    self.current_loc = (map_x, map_y)
                    # Parse game Z for layer selection (None if game_z_index=0)
                    self.current_game_z = jumploc_game_z(parts)
                    self.sig.repaint_needed.emit()
                    # Trigger auto-center/zoom/layer logic on the main thread
                    self.sig.loc_updated.emit()
                    
                    # --- clear clipboard so same data won't trigger again ---
                    pyperclip.copy("")  # empty clipboard
                
            except Exception:
                pass
            time.sleep(0.1)

    def _on_repaint_needed(self):
        """
        Called on the main thread when a repaint is requested.
        Refreshes the map canvas to reflect any changes in location or layers.
        """
        self.canvas.update()

