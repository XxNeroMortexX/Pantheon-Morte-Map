import configparser
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


class OverlayUpdater:
    """Fetch and apply updates described by a remote manifest."""

    USER_DATA_PREFIXES = (
        "calibration_",
        "pins_",
        "named_markers_",
    )
    NORMALIZED_TEXT_SUFFIXES = {".ini", ".json"}

    def __init__(
        self,
        manifest_url,
        app_dir,
        temp_folder="Update_Temp",
        log_file="update.log",
        user_agent="Pantheon Morte Map",
        progress_callback=None,
    ):
        self.manifest_url = str(manifest_url).strip()
        self.app_dir = Path(app_dir).resolve()
        self.temp_dir = self.app_dir / temp_folder
        self.log_file = self.app_dir / log_file
        self.user_agent = user_agent
        self.progress_callback = progress_callback
        self.update_summary = []
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _emit_progress(self, message):
        self.update_summary.append(message)
        if self.progress_callback:
            self.progress_callback(message)
        else:
            print(message)

    @staticmethod
    def _parse_version_parts(version_text):
        parts = []
        for token in str(version_text or "").strip().split("."):
            try:
                parts.append(int(token))
            except ValueError:
                parts.append(0)
        while parts and parts[-1] == 0:
            parts.pop()
        return tuple(parts)

    def _request_bytes(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()

    def fetch_manifest(self):
        raw = self._request_bytes(self.manifest_url)
        manifest = json.loads(raw.decode("utf-8", errors="replace"))
        if not isinstance(manifest, dict):
            raise ValueError("Manifest root must be a JSON object.")
        files = manifest.get("files", [])
        if not isinstance(files, list):
            raise ValueError("Manifest 'files' must be a list.")
        return manifest

    def check_for_update(self, current_version):
        manifest = self.fetch_manifest()
        remote_version = str(manifest.get("version", "")).strip()
        return {
            "current_version": str(current_version or "").strip(),
            "remote_version": remote_version,
            "has_update": self._parse_version_parts(remote_version) > self._parse_version_parts(current_version),
        }

    def _safe_destination(self, rel_path):
        rel_path = str(rel_path).replace("\\", "/").lstrip("/")
        dest = (self.app_dir / Path(rel_path)).resolve()
        try:
            dest.relative_to(self.app_dir)
        except ValueError as exc:
            raise ValueError(f"Unsafe path outside app directory: {rel_path}") from exc
        return dest

    def _display_path(self, rel_path):
        rel = str(rel_path).replace("/", "\\").replace("\\\\", "\\").lstrip("\\")
        if "\\" not in rel:
            return f"Root\\{rel}"
        return rel

    def _compute_sha256(self, path):
        path = Path(path)
        data = path.read_bytes()
        if path.suffix.lower() in self.NORMALIZED_TEXT_SUFFIXES:
            data = data.replace(b"\r\n", b"\n")
        return hashlib.sha256(data).hexdigest()

    def _download_to_temp(self, url, dest_path, expected_sha256=None):
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        sha256 = hashlib.sha256() if expected_sha256 else None
        try:
            with urllib.request.urlopen(req, timeout=60) as resp, open(dest_path, "wb") as out:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    if sha256:
                        sha256.update(chunk)
            if expected_sha256:
                got = sha256.hexdigest()
                if got.lower() != str(expected_sha256).lower():
                    raise ValueError(f"SHA-256 mismatch: expected {expected_sha256}, got {got}")
        except Exception:
            if dest_path.exists():
                dest_path.unlink()
            raise

    def _is_existing_user_data(self, dest):
        name = dest.name.lower()
        return any(name.startswith(prefix) and name.endswith(".json") for prefix in self.USER_DATA_PREFIXES)

    def _is_same_file(self, dest, entry):
        if not dest.exists() or not dest.is_file():
            return False
        expected_sha256 = entry.get("sha256")
        if expected_sha256:
            try:
                return self._compute_sha256(dest).lower() == str(expected_sha256).lower()
            except OSError:
                return False
        expected_size = entry.get("size")
        if expected_size is None:
            return False
        try:
            return dest.stat().st_size == int(expected_size)
        except (OSError, TypeError, ValueError):
            return False

    def _merge_config(self, existing_path, downloaded_path):
        existing_cfg = configparser.ConfigParser()
        template_cfg = configparser.ConfigParser()
        existing_cfg.read(existing_path, encoding="utf-8")
        template_cfg.read(downloaded_path, encoding="utf-8")

        with open(downloaded_path, "r", encoding="utf-8") as f:
            template_lines = f.read().splitlines()

        rendered = []
        seen_sections = set()
        seen_keys = set()
        section_insert_at = {}
        current_section = None

        for line in template_lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                if current_section is not None:
                    section_insert_at[current_section.casefold()] = len(rendered)
                current_section = stripped[1:-1].strip()
                seen_sections.add(current_section.casefold())
                rendered.append(line)
                continue

            if current_section and stripped and not stripped.startswith((";", "#")) and "=" in line:
                key, _, value = line.partition("=")
                key_name = key.strip()
                seen_keys.add((current_section.casefold(), key_name.casefold()))
                if existing_cfg.has_option(current_section, key_name):
                    user_value = existing_cfg.get(current_section, key_name, raw=True)
                    rendered.append(f"{key.rstrip()} = {user_value}")
                else:
                    rendered.append(line)
                continue

            rendered.append(line)

        if current_section is not None:
            section_insert_at[current_section.casefold()] = len(rendered)

        insertions = []
        tail_blocks = []
        for section in existing_cfg.sections():
            section_key = section.casefold()
            if section_key not in seen_sections:
                tail_blocks.append("")
                tail_blocks.append(f"[{section}]")
                for key, value in existing_cfg.items(section, raw=True):
                    tail_blocks.append(f"{key} = {value}")
                continue

            missing_keys = []
            for key, value in existing_cfg.items(section, raw=True):
                if (section_key, key.casefold()) not in seen_keys:
                    missing_keys.append(f"{key} = {value}")
            if missing_keys:
                block = [""]
                block.append(f"; Preserved user-only keys from existing [{section}]")
                block.extend(missing_keys)
                insertions.append((section_insert_at[section_key], block))

        for insert_at, block in sorted(insertions, key=lambda item: item[0], reverse=True):
            rendered[insert_at:insert_at] = block

        merged_text = "\n".join(rendered + tail_blocks).rstrip() + "\n"
        with open(existing_path, "w", encoding="utf-8") as f:
            f.write(merged_text)

    def _launch_exe_swap(self, current_exe, downloaded_exe):
        current_dir = os.path.dirname(current_exe)
        batch_lines = [
            "@echo off",
            "setlocal",
            f'set "CURRENT={current_exe}"',
            f'set "NEWEXE={downloaded_exe}"',
            f'set "APPDIR={current_dir}"',
            ":waitloop",
            'move /Y "%NEWEXE%" "%CURRENT%" >nul 2>nul',
            "if errorlevel 1 (",
            "  timeout /t 1 /nobreak >nul",
            "  goto waitloop",
            ")",
            "timeout /t 2 /nobreak >nul",
            'set "PYINSTALLER_RESET_ENVIRONMENT=1"',
            'start "" /D "%APPDIR%" "%CURRENT%"',
            'del "%~f0"',
        ]

        fd, batch_path = tempfile.mkstemp(prefix="pantheon_update_", suffix=".cmd", dir=str(self.temp_dir))
        os.close(fd)
        with open(batch_path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write("\r\n".join(batch_lines) + "\r\n")

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            ["cmd.exe", "/c", batch_path],
            cwd=str(self.app_dir),
            creationflags=creationflags,
        )

    def _apply_entry(self, entry, idx, total):
        rel_path = entry.get("path") or entry.get("local") or entry.get("name")
        url = entry.get("url")
        if not rel_path or not url:
            raise ValueError("Manifest entry must include path/local/name and url.")

        dest = self._safe_destination(rel_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        display_path = self._display_path(rel_path)

        short_name = dest.name

        overwrite = bool(entry.get("overwrite", False))
        if self._is_existing_user_data(dest) and dest.exists():
            self._emit_progress(f"Skipping     [{idx}/{total}]  {display_path} (preserved user data)")
            return "skipped", f"{display_path} (preserved user data)"

        if self._is_same_file(dest, entry):
            self._emit_progress(f"Skipping     [{idx}/{total}]  {display_path} (already up to date)")
            return "skipped", display_path

        if dest.exists() and not overwrite and not dest.name.lower().endswith(".ini"):
            self._emit_progress(f"Skipping     [{idx}/{total}]  {display_path} (overwrite disabled)")
            return "skipped", f"{display_path} (overwrite disabled)"

        self._emit_progress(f"Downloading  [{idx}/{total}]  {display_path}")

        temp_name = f"{short_name}.download"
        temp_dest = self.temp_dir / temp_name
        if temp_dest.exists():
            temp_dest.unlink()

        self._download_to_temp(url, temp_dest, entry.get("sha256"))

        if dest.name.lower().endswith(".ini") and dest.exists():
            self._merge_config(dest, temp_dest)
            temp_dest.unlink(missing_ok=True)
            return "updated", f"{display_path} (merged)"

        running_frozen = getattr(sys, "frozen", False)
        current_exe = Path(sys.executable).resolve() if running_frozen else None
        if running_frozen and dest.resolve() == current_exe:
            staged_exe = self.temp_dir / f"{dest.stem}_new{dest.suffix}"
            if staged_exe.exists():
                staged_exe.unlink()
            os.replace(temp_dest, staged_exe)
            self._launch_exe_swap(str(current_exe), str(staged_exe))
            return "updated_restart", f"{display_path} (restart required)"

        os.replace(temp_dest, dest)
        return "updated", display_path

    def write_log(self):
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write("\n".join(self.update_summary) + "\n")

    def cleanup_temp(self, keep_restart_files=False):
        if not self.temp_dir.exists():
            return

        keep_suffixes = {".cmd", "_new.exe"} if keep_restart_files else set()
        for child in self.temp_dir.iterdir():
            name_lower = child.name.lower()
            keep = any(name_lower.endswith(suffix) for suffix in keep_suffixes)
            if keep:
                continue
            try:
                if child.is_dir():
                    continue
                child.unlink()
            except OSError:
                pass

        try:
            if not any(self.temp_dir.iterdir()):
                self.temp_dir.rmdir()
        except OSError:
            pass

    def perform_update(self):
        updated = []
        skipped = []
        errors = []
        manifest_version = ""
        restart_required = False

        try:
            self._emit_progress("Connecting to update server...")
            manifest = self.fetch_manifest()
            manifest_version = str(manifest.get("version", "")).strip()
            files = manifest.get("files", [])
            if not files:
                raise ValueError("Manifest has no files.")

            for idx, entry in enumerate(files, start=1):
                try:
                    status, detail = self._apply_entry(entry, idx, len(files))
                    if status == "updated":
                        updated.append(detail)
                    elif status == "updated_restart":
                        updated.append(detail)
                        restart_required = True
                    else:
                        skipped.append(detail)
                except Exception as exc:
                    rel_path = entry.get("path") or entry.get("local") or entry.get("name") or "<unknown>"
                    errors.append(f"{self._display_path(rel_path)}: {exc}")

        except (urllib.error.URLError, json.JSONDecodeError, ValueError, OSError) as exc:
            errors.append(str(exc))

        if errors:
            self._emit_progress("Errors:")
            for item in errors:
                self._emit_progress(f"  - {item}")
            self._emit_progress("Update finished with errors.")
        elif updated:
            self._emit_progress("Update complete.")
        else:
            self._emit_progress("Everything is already up to date.")

        self.write_log()
        self.cleanup_temp(keep_restart_files=restart_required)

        result = {
            "version": manifest_version,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "log_file": str(self.log_file),
            "reloaded_files": bool(updated),
            "restart_required": restart_required,
        }

        return result
