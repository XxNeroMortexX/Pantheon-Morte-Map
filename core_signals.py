import ctypes
import ctypes.wintypes
import threading

from PyQt5.QtCore import QObject, pyqtSignal

from app_settings import TOGGLE_MAP_KEYS


class Signals(QObject):
    """Qt signals for map updates, repaint, location updates, messages, and hotkey events."""
    
    repaint_needed = pyqtSignal()
    map_loaded = pyqtSignal(str, list)
    loc_updated = pyqtSignal()
    flash_msg = pyqtSignal(str)
    hotkey_fired = pyqtSignal()
    update_notice = pyqtSignal(str, str)
    update_finished = pyqtSignal(object)


_VK_MAP = {chr(c): c for c in range(ord("A"), ord("Z") + 1)}
_VK_MAP.update({str(i): 0x30 + i for i in range(10)})

_MOD_ALT = 0x0001
_MOD_CTRL = 0x0002
_MOD_SHIFT = 0x0004
_MOD_WIN = 0x0008


def _parse_hotkey(key_seq):
    """Converts a string hotkey sequence (e.g., 'CTRL+SHIFT+M') into Windows modifier and virtual key codes."""
    
    parts = [p.strip() for p in key_seq.upper().split("+")]
    mods = 0
    vk = 0
    for part in parts:
        if part == "SHIFT":
            mods |= _MOD_SHIFT
        elif part in ("CTRL", "CONTROL"):
            mods |= _MOD_CTRL
        elif part == "ALT":
            mods |= _MOD_ALT
        elif part in ("WIN", "META"):
            mods |= _MOD_WIN
        elif part in _VK_MAP:
            vk = _VK_MAP[part]
    return mods, vk


class _GlobalHotkeyThread(threading.Thread):
    """Daemon thread that registers and listens for a global system hotkey, emitting a signal when pressed."""

    HOTKEY_ID = 1

    def __init__(self, sig: Signals, key_seq: str):
        """Initializes the hotkey thread with a signal object and the hotkey sequence to listen for."""
        
        super().__init__(daemon=True)
        self.sig = sig
        self.mods, self.vk = _parse_hotkey(key_seq)
        self._stop = threading.Event()

    def run(self):
        """Registers the global hotkey with Windows and continuously checks for key events, emitting `hotkey_fired` when triggered."""
        
        if self.vk == 0:
            print(f"[hotkey] Could not parse '{TOGGLE_MAP_KEYS}' -- global hotkey disabled")
            return

        ok = ctypes.windll.user32.RegisterHotKey(None, self.HOTKEY_ID, self.mods, self.vk)
        if not ok:
            print("[hotkey] RegisterHotKey failed -- key may already be in use")
            return
        print(f"[hotkey] Global hotkey registered: {TOGGLE_MAP_KEYS}")
        msg = ctypes.wintypes.MSG()
        while not self._stop.is_set():
            if ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                if msg.message == 0x0312 and msg.wParam == self.HOTKEY_ID:
                    self.sig.hotkey_fired.emit()
            else:
                import time as _t

                _t.sleep(0.05)
        ctypes.windll.user32.UnregisterHotKey(None, self.HOTKEY_ID)
        print("[hotkey] Global hotkey unregistered")

    def stop(self):
        """Stops the hotkey listener and unregisters the global hotkey."""
        
        self._stop.set()
