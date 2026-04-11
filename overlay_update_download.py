import os
import sys
import threading

from PyQt5.QtWidgets import QMessageBox

from app_settings import APP_NAME, APP_VERSION, UPDATE_MANIFEST_URL
from overlay_updater import OverlayUpdater


class OverlayUpdateDownloadMixin:
    """Provides methods for checking and downloading overlay updates."""

    def _on_update_notice(self, current_version, remote_version):
        answer = QMessageBox.question(
            self,
            "Update Available",
            f"A new update is available on GitHub.\n\nCurrent version: {current_version}\nAvailable version: {remote_version}\n\nWould you like to download it now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Yes:
            self._run_update_check()
        else:
            self.sig.flash_msg.emit(
                f"Update available: {remote_version} (current {current_version})"
            )

    def _on_update_finished(self, result):
        self._update_in_progress = False
        self.btn_update.setEnabled(True)

        lines = []
        if result["version"]:
            lines.append(f"Manifest version: {result['version']}")

        if result["updated"]:
            lines.append("")
            lines.append(f"Updated {len(result['updated'])} file(s):")
            lines.extend(f"  + {item}" for item in result["updated"][:30])
            if len(result["updated"]) > 30:
                lines.append(f"  ... +{len(result['updated']) - 30} more")

        if result["skipped"]:
            lines.append("")
            lines.append(f"Skipped {len(result['skipped'])} file(s):")
            lines.extend(f"  - {item}" for item in result["skipped"][:20])
            if len(result["skipped"]) > 20:
                lines.append(f"  ... +{len(result['skipped']) - 20} more")

        if result["errors"]:
            lines.append("")
            lines.append("Errors:")
            lines.extend(f"  - {item}" for item in result["errors"][:12])

        if result["restart_required"]:
            lines.append("")
            lines.append("The application will now close and reopen to finish the EXE update.")

        if not result["updated"] and not result["errors"]:
            lines.append("")
            lines.append("Everything is already up to date.")

        lines.append("")
        lines.append(f"Log: {result['log_file']}")

        title = "Update Complete" if not result["errors"] else "Update Finished With Errors"
        QMessageBox.information(self, title, "\n".join(lines))

        if result["updated"] and not result["restart_required"]:
            self._load_map(self.current_map_name)

        if result["restart_required"]:
            self.sig.flash_msg.emit("Restarting to finish EXE update...")
            self.close()

    def _start_update_notice_check(self):
        if not UPDATE_MANIFEST_URL:
            return
        if getattr(self, "_update_notice_started", False):
            return
        self._update_notice_started = True
        threading.Thread(target=self._check_for_update_notice, daemon=True).start()

    def _run_update_check(self):
        if getattr(self, "_update_in_progress", False):
            self.sig.flash_msg.emit("Update already running...")
            return

        if not UPDATE_MANIFEST_URL:
            QMessageBox.information(
                self,
                "Update",
                "Set update/manifest_url in Settings\\config.ini to a raw JSON URL.",
            )
            return

        self._update_in_progress = True
        self.btn_update.setEnabled(False)
        self.sig.flash_msg.emit("Connecting to update server...")
        threading.Thread(target=self._do_update_download, daemon=True).start()

    def _check_for_update_notice(self):
        base_dir = (
            os.path.dirname(sys.executable)
            if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__))
        )

        updater = OverlayUpdater(
            manifest_url=UPDATE_MANIFEST_URL,
            app_dir=base_dir,
            temp_folder="Update_Temp",
            log_file="update.log",
            user_agent=f"{APP_NAME}/{APP_VERSION}",
        )

        try:
            result = updater.check_for_update(APP_VERSION)
        except Exception:
            return

        if not result["has_update"]:
            return
        self.sig.update_notice.emit(result["current_version"], result["remote_version"])

    def _do_update_download(self):
        base_dir = (
            os.path.dirname(sys.executable)
            if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__))
        )

        updater = OverlayUpdater(
            manifest_url=UPDATE_MANIFEST_URL,
            app_dir=base_dir,
            temp_folder="Update_Temp",
            log_file="update.log",
            user_agent=f"{APP_NAME}/{APP_VERSION}",
            progress_callback=self.sig.flash_msg.emit,
        )

        try:
            result = updater.perform_update()
        except Exception as exc:
            result = {
                "version": "",
                "updated": [],
                "skipped": [],
                "errors": [str(exc)],
                "log_file": str(updater.log_file),
                "restart_required": False,
            }
        self.sig.update_finished.emit(result)
