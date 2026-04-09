import json

import numpy as np
import pyperclip

from app_functions import _jumploc_required_token_count, compute_affine_transform, jumploc_map_xy
from app_settings import CAL_SNAP_ZOOM, FLASH_DURATION, UPDATE_THRESHOLD


class OverlayEditingMixin:
    """
    Provides automatic map overlay updates based on in-game location
    data from the clipboard. Supports optional zoom, auto-centering,
    and Z-layer auto-selection.
    """
    
    # ===========================================================
    # Calibration mode
    # ===========================================================
    def _toggle_calib_mode(self):
        """
        Toggle calibration mode on/off.
        """
        self._set_calib_mode(not self.calib_mode)

    def _set_calib_mode(self, enabled: bool):
        """
        Enable or disable calibration mode, adjusting zoom and UI accordingly.
        """
        self.calib_mode = enabled
        if enabled:
            self._set_pin_drop_mode(False)
            self._exit_edit_mode()
            if CAL_SNAP_ZOOM > 0:
                old = self.zoom
                self.zoom = CAL_SNAP_ZOOM
                cx = self.canvas.width() / 2.0
                cy = self.canvas.height() / 2.0
                self.offset_x = cx - (cx - self.offset_x) * (self.zoom / old)
                self.offset_y = cy - (cy - self.offset_y) * (self.zoom / old)

        label = "■  Disable Calibration Mode" if enabled else "▶  Enable Calibration Mode"
        self.btn_calib_toggle.setText(label)
        self.btn_calib_toggle.setChecked(enabled)
        self.btn_calib_toggle.setStyleSheet(
            "QPushButton{background:%s;color:white;border:%s;"
            "font-weight:bold;font-size:12px;border-radius:4px;padding:5px;}"
            "QPushButton:hover{background:#fff;color:#111;}"
            % (
                "#e07020" if enabled else "#c0782a",
                "2px solid #f0c040" if enabled else "none",
            )
        )
        self.canvas.update()

    # ===========================================================
    # Pin-drop mode
    # ===========================================================
    def _on_pin_name_changed(self, text):
        """
        Update the pending pin name when the user edits the pin name input field.
        """
        self.pending_pin_name = text.strip()
        self.canvas.update()

    def _toggle_pin_drop_mode(self):
        """
        Toggle pin-drop mode on/off.
        """
        self._set_pin_drop_mode(not self.pin_drop_mode)

    def _set_pin_drop_mode(self, enabled: bool):
        """
        Enable or disable pin-drop mode.
        Shows pin panel if enabling and disables calibration/edit modes.
        Updates the UI to reflect the current state.
        """
        self.pin_drop_mode = enabled
        if enabled:
            self._set_calib_mode(False)
            self._exit_edit_mode()
            if not self.pin_panel.isVisible():
                self.pin_panel.show()
                self._refresh_pin_list()

        label = "■  Cancel Pin-Drop Mode" if enabled else "▶  Activate Pin-Drop Mode"
        self.btn_pin_mode.setText(label)
        self.btn_pin_mode.setChecked(enabled)
        self.btn_pin_mode.setStyleSheet(
            "QPushButton{background:%s;color:white;border:%s;"
            "font-weight:bold;font-size:12px;border-radius:4px;padding:5px;}"
            "QPushButton:hover{background:#fff;color:#111;}"
            % (
                "#e03030" if enabled else "#c0392b",
                "2px solid #ff8080" if enabled else "none",
            )
        )
        self.canvas.update()

    # ===========================================================
    # Edit mode
    # ===========================================================
    def _edit_selected_calib(self):
        """
        Enter edit mode for the currently selected calibration point.
        """
        row = self.calib_list.currentRow()
        if 0 <= row < len(self.calibration_points):
            self._enter_edit_mode("cal", row)
        else:
            self._flash("Select a calibration point first.")

    def _edit_selected_pin(self):
        """
        Enter edit mode for the currently selected pin.
        """
        row = self.pin_list.currentRow()
        if 0 <= row < len(self.drop_pins):
            self._enter_edit_mode("pin", row)
        else:
            self._flash("Select a pin first.")

    def _enter_edit_mode(self, edit_type: str, index: int):
        """
        Activate edit mode for a specific calibration point or pin.
        Disables other modes, highlights the target, and updates UI.
        """
        self._set_calib_mode(False)
        self._set_pin_drop_mode(False)
        self.edit_mode = True
        self.edit_type = edit_type
        self.edit_index = index
        if edit_type == "cal":
            pt = self.calibration_points[index]
            self._flash(f"EDIT: double-click new location for cal pt #{index+1}  X={pt[2]:.1f} Y={pt[3]:.1f}")
        else:
            name = self.drop_pins[index]["name"]
            self._flash(f'EDIT: double-click new location for pin "{name}"')
        self.canvas.update()

    def _exit_edit_mode(self):
        """
        Exit edit mode and reset related flags.
        """
        self.edit_mode = False
        self.edit_type = None
        self.edit_index = -1
        self.canvas.update()

    # ===========================================================
    # List helpers
    # ===========================================================
    def _refresh_calib_list(self):
        """
        Refresh the calibration point list in the UI to reflect current data.
        """
        self.calib_list.clear()
        for i, (img_x, img_y, map_x, map_y) in enumerate(self.calibration_points):
            self.calib_list.addItem(f"#{i+1}  Px={int(img_x)} Py={int(img_y)}  X={map_x:.1f} Y={map_y:.1f}")

    def _refresh_pin_list(self):
        """
        Refresh the pin list in the UI to reflect current pins.
        """
        self.pin_list.clear()
        for pin in self.drop_pins:
            self.pin_list.addItem(f"📍 {pin['name']}  Px={int(pin['px'])} Py={int(pin['py'])}")

    def _delete_selected_calib(self):
        """
        Delete the currently selected calibration point.
        Updates affine transform, UI, and flashes a message.
        """
        row = self.calib_list.currentRow()
        if 0 <= row < len(self.calibration_points):
            self.calibration_points.pop(row)
            self.xc, self.yc = compute_affine_transform(self.calibration_points)
            self._refresh_calib_list()
            self.canvas.update()
            self._flash("Calibration point deleted.")

    def _clear_all_calib(self):
        """
        Delete all calibration points, reset transforms, and update UI.
        """
        if not self.calibration_points:
            return
        self.calibration_points.clear()
        self.xc, self.yc = compute_affine_transform(self.calibration_points)
        self._refresh_calib_list()
        self.canvas.update()
        self._flash("All calibration points cleared.")

    def _delete_selected_pin(self):
        """
        Delete the currently selected pin.
        Updates the pin list, saves changes, and flashes a message.
        """
        row = self.pin_list.currentRow()
        if 0 <= row < len(self.drop_pins):
            name = self.drop_pins[row]["name"]
            self.drop_pins.pop(row)
            self._refresh_pin_list()
            self.canvas.update()
            self._save_pins()
            self._flash(f"Pin '{name}' deleted.")

    def _clear_all_pins(self):
        """
        Delete all pins, update the list, save changes, and update UI.
        """
        if not self.drop_pins:
            return
        self.drop_pins.clear()
        self._refresh_pin_list()
        self.canvas.update()
        self._save_pins()
        self._flash("All pins cleared.")

    def _rename_selected_pin(self):
        """
        Rename the currently selected pin using input from the rename field.
        Updates the UI and saves the new name.
        """
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
        """
        Save all current pins to storage and flash a confirmation message.
        """
        self._save_pins()
        self._flash(f"Saved {len(self.drop_pins)} pins.")

    # ===========================================================
    # Double-click handler
    # ===========================================================
    def handle_double_click(self, img_x, img_y):
        """
        Handle double-clicks on the overlay canvas.
        In edit mode, moves selected calibration/pin point.
        In calibration mode, adds or updates calibration points using /jumploc.
        In pin-drop mode, places a new pin at the clicked location.
        Updates UI and flashes feedback messages.
        """
        x_click = int(round(img_x))
        y_click = int(round(img_y))
        self.last_click_px = (x_click, y_click)

        if self.edit_mode:
            if self.edit_type == "cal" and 0 <= self.edit_index < len(self.calibration_points):
                old = self.calibration_points[self.edit_index]
                self.calibration_points[self.edit_index] = (x_click, y_click, old[2], old[3])
                self.xc, self.yc = compute_affine_transform(self.calibration_points)
                self._refresh_calib_list()
                self._save_calib()
                self._flash(f"Cal pt #{self.edit_index+1} moved to Px={x_click} Py={y_click} — saved.")
            elif self.edit_type == "pin" and 0 <= self.edit_index < len(self.drop_pins):
                self.drop_pins[self.edit_index]["px"] = x_click
                self.drop_pins[self.edit_index]["py"] = y_click
                name = self.drop_pins[self.edit_index]["name"]
                self._refresh_pin_list()
                self._save_pins()
                self._flash(f'Pin "{name}" moved to Px={x_click} Py={y_click} — saved.')

            self._exit_edit_mode()
            self.canvas.update()
            return

        if self.calib_mode:
            text = pyperclip.paste().strip()
            if not text.startswith("/jumploc"):
                self._flash("CAL mode: copy /jumploc in-game first, then double-click.")
                self.canvas.update()
                return

            parts = text.split()
            need = _jumploc_required_token_count()
            if len(parts) <= need:
                self._flash(f"/jumploc needs at least {need + 1} tokens.")
                self.canvas.update()
                return

            try:
                map_x, map_y = jumploc_map_xy(parts)
                if self.calibration_points:
                    dists = [(np.hypot(p[0] - x_click, p[1] - y_click), i) for i, p in enumerate(self.calibration_points)]
                    min_d, ni = min(dists)
                    if min_d <= UPDATE_THRESHOLD:
                        self.calibration_points[ni] = (x_click, y_click, map_x, map_y)
                        msg = f"Updated pt #{ni+1}: Px={x_click} Py={y_click} X={map_x:.1f} Y={map_y:.1f}"
                    else:
                        self.calibration_points.append((x_click, y_click, map_x, map_y))
                        msg = f"Added pt #{len(self.calibration_points)}: Px={x_click} Py={y_click} X={map_x:.1f} Y={map_y:.1f}"
                else:
                    self.calibration_points.append((x_click, y_click, map_x, map_y))
                    msg = f"Added pt #1: Px={x_click} Py={y_click} X={map_x:.1f} Y={map_y:.1f}"

                self.xc, self.yc = compute_affine_transform(self.calibration_points)
                self._refresh_calib_list()
                self._flash(msg)
            except Exception as e:
                self._flash(f"Error reading /jumploc: {e}")

        elif self.pin_drop_mode:
            name = self.pending_pin_name or f"Pin {len(self.drop_pins) + 1}"
            self.drop_pins.append({"name": name, "px": x_click, "py": y_click})
            self._refresh_pin_list()
            self._save_pins()
            self._flash(f"📍 '{name}' placed at Px={x_click} Py={y_click}")
            self.pin_name_edit.clear()
            self.pending_pin_name = ""
            self._set_pin_drop_mode(False)

        self.canvas.update()

    # ===========================================================
    # Flash
    # ===========================================================
    def _flash(self, text):
        """
        Display a temporary message at the center of the overlay.
        Automatically hides after FLASH_DURATION.
        """
        self.flash_lbl.setText(text)
        self.flash_lbl.adjustSize()
        self.flash_lbl.move(
            (self.width() - self.flash_lbl.width()) // 2,
            (self.height() - self.flash_lbl.height()) // 2 - 40,
        )
        self.flash_lbl.show()
        self.flash_lbl.raise_()
        self.flash_timer.start(FLASH_DURATION)

