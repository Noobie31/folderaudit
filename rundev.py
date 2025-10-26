# rundev.py
# Auto-restart main.py on .py changes.
# Default behavior: start/restart the app MINIMIZED (no focus steal).
# Optional: set USE_MINIMIZED_ON_RESTART=False to restore last position without activating.

import os
import sys
import time
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
MAIN_FILE = PROJECT_DIR / "main.py"
PYTHON = sys.executable

# --- behavior toggle ---
USE_MINIMIZED_ON_RESTART = False  # <- set to False to try "stay where it was" (no activation)

# ---------------------- Windows helpers (ctypes) ----------------------
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
GetWindowThreadProcessId.restype = wintypes.DWORD

IsWindowVisible = user32.IsWindowVisible
IsWindowVisible.argtypes = [wintypes.HWND]
IsWindowVisible.restype = wintypes.BOOL

GetWindowRect = user32.GetWindowRect
GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
GetWindowRect.restype = wintypes.BOOL

SetWindowPos = user32.SetWindowPos
SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                         ctypes.c_int, ctypes.c_int, ctypes.c_uint]
SetWindowPos.restype = wintypes.BOOL

ShowWindow = user32.ShowWindow
ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
ShowWindow.restype = wintypes.BOOL

EnumWindows = user32.EnumWindows
EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
EnumWindows.restype = wintypes.BOOL

SWP_NOZORDER   = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_NOSIZE     = 0x0001
SWP_NOMOVE     = 0x0002

SW_SHOWNA           = 8   # show without activating
SW_SHOWMINNOACTIVE  = 7   # show minimized, no activate
SW_MINIMIZE         = 6   # minimize (may activate another window)

HWND_BOTTOM = wintypes.HWND(1)

def _enum_windows():
    hwnds = []
    @EnumWindowsProc
    def cb(hwnd, lparam):
        hwnds.append(hwnd)
        return True
    EnumWindows(cb, 0)
    return hwnds

def _pid_for_hwnd(hwnd):
    pid = wintypes.DWORD(0)
    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value

def find_top_windows_for_pid(pid):
    result = []
    for hwnd in _enum_windows():
        if _pid_for_hwnd(hwnd) == pid and IsWindowVisible(hwnd):
            result.append(hwnd)
    return result

def get_rect(hwnd):
    rect = wintypes.RECT()
    if not GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return (rect.left, rect.top, rect.right, rect.bottom)

def set_rect_noactivate(hwnd, rect):
    if not rect: return
    l, t, r, b = rect
    w = max(0, r - l); h = max(0, b - t)
    SetWindowPos(hwnd, 0, l, t, w, h, SWP_NOZORDER | SWP_NOACTIVATE)

def send_to_back_noactivate(hwnd):
    SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE)

# ---------------------- Watcher (watchdog if available, else polling) ----------------------
def _has_watchdog():
    try:
        import watchdog  # noqa
        return True
    except Exception:
        return False

def _iter_py_files():
    for p in PROJECT_DIR.rglob("*.py"):
        parts = {part.lower() for part in p.parts}
        if "venv" in parts or ".venv" in parts:
            continue
        yield p

def _snapshot():
    return {str(p): p.stat().st_mtime for p in _iter_py_files()}

# ---------------------- Runner ----------------------
def run_loop():
    print("👀 Watching for *.py changes (recursive). Ctrl+C to stop.")
    process = None
    last_rect = None
    last_pid = None

    def _start():
        nonlocal process, last_pid
        # Launch minimized (no focus) using STARTUPINFO
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = SW_SHOWMINNOACTIVE if USE_MINIMIZED_ON_RESTART else SW_SHOWNA

        print("🚀 Starting main.py ...")
        process = subprocess.Popen([PYTHON, str(MAIN_FILE)],
                                   cwd=str(PROJECT_DIR),
                                   startupinfo=si)
        last_pid = process.pid

        # Wait up to 5s to find the window
        hwnd = None
        t0 = time.time()
        while time.time() - t0 < 5.0:
            wins = find_top_windows_for_pid(last_pid)
            if wins:
                hwnd = wins[0]
                break
            time.sleep(0.05)

        if not hwnd:
            return

        if USE_MINIMIZED_ON_RESTART:
            # Force minimized, no activation
            ShowWindow(hwnd, SW_SHOWMINNOACTIVE)
        else:
            # Restore last position w/o activation and keep it behind
            if last_rect:
                set_rect_noactivate(hwnd, last_rect)
            else:
                ShowWindow(hwnd, SW_SHOWNA)
            send_to_back_noactivate(hwnd)

    def _stop():
        nonlocal process, last_rect, last_pid
        if not process:
            return
        # remember current position
        if last_pid:
            wins = find_top_windows_for_pid(last_pid)
            if wins:
                r = get_rect(wins[0])
                if r:
                    last_rect = r
        print("⏹ Stopping ...")
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
        process = None

    _start()

    if _has_watchdog():
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        class H(FileSystemEventHandler):
            def __init__(self): self._last=0
            def _hit(self, path):
                now=time.time()
                if now-self._last<0.25: return
                self._last=now
                print(f"🔁 Change: {path}")
                _stop(); _start()
            def on_modified(self,e):
                if not e.is_directory and e.src_path.lower().endswith(".py"): self._hit(e.src_path)
            on_created=on_moved=on_deleted=on_modified
        obs=Observer(); obs.schedule(H(), str(PROJECT_DIR), recursive=True); obs.start()
        try:
            while True: time.sleep(0.5)
        except KeyboardInterrupt: pass
        finally:
            obs.stop(); obs.join(); _stop()
    else:
        print("⚠️ watchdog not installed; using polling every 500ms.")
        snap=_snapshot()
        try:
            while True:
                time.sleep(0.5)
                cur=_snapshot()
                if cur!=snap:
                    snap=cur
                    print("🔁 Change detected.")
                    _stop(); _start()
                if process and process.poll() is not None:
                    print("⚠️ App exited. Restarting...")
                    _start()
        except KeyboardInterrupt:
            pass
        finally:
            _stop()

if __name__ == "__main__":
    if not MAIN_FILE.exists():
        print(f"❌ Can't find {MAIN_FILE}")
        sys.exit(1)
    run_loop()
