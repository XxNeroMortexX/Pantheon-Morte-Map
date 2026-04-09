import json
import os
import sys
import threading
import urllib.error
import urllib.request

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox

from app_settings import APP_NAME, APP_VERSION, UPDATE_MANIFEST_URL


class OverlayUpdateDownloadMixin:
    """Provides methods for checking and downloading overlay updates."""
    def _run_update_check(self):
        """
        UPD button entry point.
        Shows help if no manifest URL set, otherwise kicks off background download.
        """
        if not UPDATE_MANIFEST_URL:
            QMessageBox.information(
                self,
                "Update",
                "Set  update/manifest_url  in Settings\\config.ini to a raw JSON URL\n"
                "(e.g. a GitHub raw content URL for update_manifest.json).\n\n"
                "See CHANGELOG.md for the manifest file format.",
            )
            return

        # Disable button during download to prevent double-clicks
        self.btn_update.setEnabled(False)
        self._flash("Connecting to update server...")
        threading.Thread(target=self._do_update_download, daemon=True).start()

    def _do_update_download(self):
        """
        Background thread: fetch manifest JSON, then download each file.
        Uses sig.flash_msg to show per-file progress in the flash label (like map loading).
        Shows a full summary dialog at the end via QTimer on the main thread.
        """
        base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        base_abs = os.path.abspath(base)

        # Step 1: fetch manifest
        try:
            req = urllib.request.Request(
                UPDATE_MANIFEST_URL,
                headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            manifest = json.loads(raw)
        except urllib.error.URLError as e:
            self.sig.flash_msg.emit(f"Update failed: {e}")
            QTimer.singleShot(0, lambda: self.btn_update.setEnabled(True))
            return
        except json.JSONDecodeError as e:
            self.sig.flash_msg.emit(f"Bad manifest JSON: {e}")
            QTimer.singleShot(0, lambda: self.btn_update.setEnabled(True))
            return
        except Exception as e:
            self.sig.flash_msg.emit(f"Update error: {e}")
            QTimer.singleShot(0, lambda: self.btn_update.setEnabled(True))
            return

        remote_ver = manifest.get("version", "")
        files = manifest.get("files", [])
        if not files:
            self.sig.flash_msg.emit("Manifest has no files.")
            QTimer.singleShot(0, lambda: self.btn_update.setEnabled(True))
            return

        # Step 2: download each file, flashing its name as we go
        updated = []
        skipped = []
        errors = []
        for idx, ent in enumerate(files):
            rel = ent.get("path") or ent.get("local")
            url = ent.get("url")
            if not rel or not url:
                continue
            rel = str(rel).replace("\\", "/")
            dest = os.path.normpath(os.path.join(base, *rel.split("/")))
            dest_abs = os.path.abspath(dest)
            # Security: never write outside the app folder
            if not (dest_abs == base_abs or dest_abs.startswith(base_abs + os.sep)):
                errors.append(f"Unsafe path skipped: {rel}")
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)

            exp_size = ent.get("size")
            if os.path.isfile(dest):
                if exp_size is not None and int(exp_size) == os.path.getsize(dest):
                    skipped.append(rel)
                    continue
                if exp_size is None and not ent.get("overwrite"):
                    skipped.append(rel)
                    continue

            # Flash the current filename -- just like map loading progress
            short_name = os.path.basename(rel)
            self.sig.flash_msg.emit(f"Downloading  [{idx+1}/{len(files)}]  {short_name}...")
            try:
                part = dest + ".download_part"
                urllib.request.urlretrieve(url, part)
                os.replace(part, dest)
                updated.append(rel)
            except Exception as e:
                errors.append(f"{rel}: {e}")

        # Step 3: build summary and show via main thread
        lines = []
        if remote_ver:
            lines.append(f"Manifest version: {remote_ver}\n")
        if updated:
            lines.append(
                f"Downloaded {len(updated)} file(s):\n" + "\n".join(f"  + {r}" for r in updated[:30])
            )
            if len(updated) > 30:
                lines.append(f"  ... +{len(updated)-30} more")
        if skipped:
            lines.append(f"\nSkipped {len(skipped)} already up-to-date file(s).")
        if not updated and not errors:
            lines.append("Everything is already up to date.")
        if errors:
            lines.append("\nErrors:\n" + "\n".join(errors[:12]))

        QTimer.singleShot(0, lambda: self.btn_update.setEnabled(True))
        QTimer.singleShot(0, lambda: QMessageBox.information(self, "Update Complete", "\n".join(lines)))

        if updated:
            QTimer.singleShot(200, lambda: self._load_map(self.current_map_name))

