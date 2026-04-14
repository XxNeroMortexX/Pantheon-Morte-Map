import ctypes
import ctypes.wintypes
import threading
import platform

from PyQt5.QtCore import QObject, pyqtSignal

from app_settings import TOGGLE_MAP_KEYS

if not hasattr(ctypes.wintypes, "ULONG_PTR"):
    if platform.architecture()[0] == "64bit":
        ctypes.wintypes.ULONG_PTR = ctypes.c_uint64
    else:
        ctypes.wintypes.ULONG_PTR = ctypes.c_uint32


class Signals(QObject):
    repaint_needed  = pyqtSignal()
    map_loaded      = pyqtSignal(str, list)
    loc_updated     = pyqtSignal()
    flash_msg       = pyqtSignal(str)
    hotkey_fired    = pyqtSignal()
    update_notice   = pyqtSignal(str, str)
    update_finished = pyqtSignal(object)


_VK_MAP = {chr(c): c for c in range(ord("A"), ord("Z") + 1)}
_VK_MAP.update({str(i): 0x30 + i for i in range(10)})

_MOD_ALT   = 0x0001
_MOD_CTRL  = 0x0002
_MOD_SHIFT = 0x0004
_MOD_WIN   = 0x0008

_WH_KEYBOARD_LL = 13
_HC_ACTION      = 0
_WM_KEYDOWN     = 0x0100
_WM_KEYUP       = 0x0101
_WM_SYSKEYDOWN  = 0x0104
_WM_SYSKEYUP    = 0x0105
_WM_QUIT        = 0x0012

_VK_RETURN   = 0x0D
_VK_SHIFT    = 0x10
_VK_CONTROL  = 0x11
_VK_MENU     = 0x12
_VK_LSHIFT   = 0xA0
_VK_RSHIFT   = 0xA1
_VK_LCONTROL = 0xA2
_VK_RCONTROL = 0xA3
_VK_LMENU    = 0xA4
_VK_RMENU    = 0xA5
_VK_LWIN     = 0x5B
_VK_RWIN     = 0x5C

_MODIFIER_VKS = {
    _MOD_SHIFT: (_VK_SHIFT,   _VK_LSHIFT,   _VK_RSHIFT),
    _MOD_CTRL:  (_VK_CONTROL, _VK_LCONTROL, _VK_RCONTROL),
    _MOD_ALT:   (_VK_MENU,    _VK_LMENU,    _VK_RMENU),
    _MOD_WIN:   (_VK_LWIN,    _VK_RWIN),
}


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode",      ctypes.wintypes.DWORD),
        ("scanCode",    ctypes.wintypes.DWORD),
        ("flags",       ctypes.wintypes.DWORD),
        ("time",        ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.wintypes.ULONG_PTR),
    ]


_HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.wintypes.LPARAM,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
)


def is_game_focused():
    import psutil
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hwnd   = user32.GetForegroundWindow()
    pid    = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    try:
        proc = psutil.Process(pid.value)
        name = proc.name().lower()
        #print(f"[hotkey-debug] Foreground process: {name!r}")
        return "pantheon" in name
    except Exception as e:
        print(f"[hotkey-debug] is_game_focused() exception: {e}")
        return False


def _vk_is_down(vk_code):
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000)


def _current_modifier_mask():
    mask = 0
    for mod_flag, vk_codes in _MODIFIER_VKS.items():
        if any(_vk_is_down(vk) for vk in vk_codes):
            mask |= mod_flag
    return mask


def _parse_hotkey(key_seq):
    parts = [p.strip() for p in key_seq.upper().split("+")]
    mods  = 0
    vk    = 0
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

    def __init__(self, sig: Signals, key_seq: str):
        super().__init__(daemon=True)
        self.sig  = sig
        self.mods, self.vk = _parse_hotkey(key_seq)
        self._stop_event   = threading.Event()
        self._thread_id    = None
        self._hook_handle  = None
        self._hook_proc    = None
        self._chat_mode    = False
        self._hotkey_armed = False
        self._enter_down   = False

        print(f"[hotkey-debug] key_seq={key_seq!r}  parsed mods=0x{self.mods:02X}  vk=0x{self.vk:02X}")

    def _call_next(self, n_code, w_param, l_param):
        user32 = ctypes.windll.user32

        # Define signature ONCE (safe to repeat, ctypes ignores duplicates)
        user32.CallNextHookEx.argtypes = (
            ctypes.wintypes.HHOOK,
            ctypes.c_int,
            ctypes.wintypes.WPARAM,
            ctypes.wintypes.LPARAM,
        )
        user32.CallNextHookEx.restype = ctypes.wintypes.LPARAM

        return user32.CallNextHookEx(
            self._hook_handle,
            n_code,
            w_param,
            ctypes.wintypes.LPARAM(l_param)  # CRITICAL FIX
        )

    def _suppress(self):
        return 1

    def _keyboard_proc(self, n_code, w_param, l_param):
        if n_code != _HC_ACTION:
            return self._call_next(n_code, w_param, l_param)
        
        # HARD FILTER — nothing runs unless game is focused
        if not is_game_focused():
            #self._chat_mode = False
            self._hotkey_armed = False
            return self._call_next(n_code, w_param, l_param)
        
        key_info = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        vk       = key_info.vkCode
        
        # CHAT MODE INPUT GATE (CRITICAL FIX)
        if self._chat_mode:
            if vk == self.vk:
                # Let hotkey key still pass through (so it types in chat)
                return self._call_next(n_code, w_param, l_param)

            if vk in (_VK_RETURN, 0x1B):
                # Allow Enter + ESC to still function normally
                pass
            else:
                # Everything else becomes normal typing input
                return self._call_next(n_code, w_param, l_param)
        
        if vk not in (
            self.vk,        # User's configured hotkey key (e.g. M, G, 1, etc.)

            _VK_RETURN,     # Enter key (used to open/close chat)
            0x1B,           # Escape key (force exit chat)

            # Modifier keys (needed for combos like Ctrl+Alt+M)

            # Ctrl (generic + left + right)
            _VK_CONTROL,    # Ctrl (generic)
            _VK_LCONTROL,   # Left Ctrl
            _VK_RCONTROL,   # Right Ctrl

            # Shift (generic + left + right)
            _VK_SHIFT,      # Shift (generic)
            _VK_LSHIFT,     # Left Shift
            _VK_RSHIFT,     # Right Shift

            # Alt (called "Menu" in Windows API)
            _VK_MENU,       # Alt (generic)
            _VK_LMENU,      # Left Alt
            _VK_RMENU,      # Right Alt

            # Windows key (left + right)
            _VK_LWIN,       # Left Windows key
            _VK_RWIN,       # Right Windows key
        ):
            # Ignore ALL other keys (typing, random input, etc.)
            return self._call_next(n_code, w_param, l_param)
        
        is_down  = w_param in (_WM_KEYDOWN, _WM_SYSKEYDOWN)
        is_up    = w_param in (_WM_KEYUP,   _WM_SYSKEYUP)
        
        if is_down:
            print(f"[hotkey-debug] KEY DOWN  vk=0x{vk:02X}  target=0x{self.vk:02X}  match={vk == self.vk}")

        game_focused = is_game_focused()
        print(f"[hotkey-debug]   game_focused={game_focused}  chat_mode={self._chat_mode}  armed={self._hotkey_armed}")

        if not game_focused:
            #self._chat_mode    = False
            self._hotkey_armed = False
            return self._call_next(n_code, w_param, l_param)

        if vk == _VK_RETURN:
            if is_down:
                # NEW: Ignore numpad Enter — it has the LLKHF_EXTENDED flag set
                # Main Enter = flags bit 0 is NOT set; Numpad Enter = flags bit 0 IS set
                is_numpad_enter = bool(key_info.flags & 0x01)  # LLKHF_EXTENDED = 0x01
                if is_numpad_enter:
                    # Numpad Enter: never toggle chat mode, just pass through
                    return self._call_next(n_code, w_param, l_param)

                # Only trigger once per physical Enter press (prevents double toggle)
                if not self._enter_down:
                    self._enter_down = True

                    # Toggle chat mode (open/close chat state)
                    self._chat_mode = not self._chat_mode

                    # FULL RESET
                    # Prevents hotkey from staying "armed" after chat interaction
                    self._hotkey_armed = False

                    print(f"[hotkey-debug]   Enter -> chat_mode now {self._chat_mode} (RESET)")

            elif is_up:
                # Also skip numpad Enter on key-up to keep _enter_down consistent
                is_numpad_enter = bool(key_info.flags & 0x01)
                if is_numpad_enter:
                    return self._call_next(n_code, w_param, l_param)

                # Reset Enter tracking when key is released
                self._enter_down = False

            # Always pass Enter to game/chat system
            return self._call_next(n_code, w_param, l_param)
        
        #NEW: ESC should ALWAYS exit chat mode
        if vk == 0x1B:  # ESC key
            if is_down:
                self._chat_mode = False
                self._hotkey_armed = False
                print("[hotkey-debug]   ESC -> chat_mode forced OFF")
            return self._call_next(n_code, w_param, l_param)
        
        if vk == self.vk:
            if is_down:
                mod_mask = _current_modifier_mask()
                print(f"[hotkey-debug]   Hotkey DOWN  chat={self._chat_mode}  mod_mask=0x{mod_mask:02X}  need=0x{self.mods:02X}  mod_ok={mod_mask == self.mods}")
                # Only block gameplay hotkey, not system keys
                if self._chat_mode and vk == self.vk:
                    return self._call_next(n_code, w_param, l_param)
                if mod_mask == self.mods:
                    if not self._hotkey_armed:
                        self._hotkey_armed = True
                        print("[hotkey-debug]   -> ARMED")
                    return self._suppress()
                else:
                    # NEW: force reset if mods don't match
                    self._hotkey_armed = False
                    return self._call_next(n_code, w_param, l_param)

            elif is_up:
                print(f"[hotkey-debug]   Hotkey UP  armed={self._hotkey_armed}")
                if self._hotkey_armed:
                    self._hotkey_armed = False
                    print("[hotkey-debug]   -> EMITTING hotkey_fired")
                    self.sig.hotkey_fired.emit()
                    print("[hotkey-debug]   -> Emit done")
                    return self._suppress()

        return self._call_next(n_code, w_param, l_param)

    def run(self):
        if self.vk == 0:
            print("[hotkey-debug] vk==0 -- bad key_seq, hotkey disabled")
            return

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        self._thread_id = kernel32.GetCurrentThreadId()
        self._hook_proc = _HOOKPROC(self._keyboard_proc)

        # Define function signature (prevents silent failure)
        user32.SetWindowsHookExW.argtypes = (
            ctypes.c_int,
            _HOOKPROC,
            ctypes.wintypes.HINSTANCE,
            ctypes.wintypes.DWORD,
        )
        user32.SetWindowsHookExW.restype = ctypes.wintypes.HHOOK

        # FIX: hMod MUST be None for low-level keyboard hooks
        self._hook_handle = user32.SetWindowsHookExW(
            _WH_KEYBOARD_LL,
            self._hook_proc,
            None,   # <-- CRITICAL FIX
            0
        )

        # Better error output
        if not self._hook_handle:
            error = kernel32.GetLastError()
            print(f"[hotkey-debug] SetWindowsHookExW FAILED, error={error}")
            return

        print(f"[hotkey-debug] Hook installed OK, handle={self._hook_handle}")

        msg = ctypes.wintypes.MSG()
        while not self._stop_event.is_set():
            status = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if status <= 0 or msg.message == _WM_QUIT:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._hook_handle:
            user32.UnhookWindowsHookEx(self._hook_handle)
            self._hook_handle = None

        print("[hotkey-debug] Hook stopped")

    def stop(self):
        self._stop_event.set()
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, _WM_QUIT, 0, 0)