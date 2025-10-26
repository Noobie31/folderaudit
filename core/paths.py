# core/paths.py
from pathlib import Path
import os
import sys

APP_NAME = "PDFReporter"

def get_base_path() -> Path:
    """Get base path - handles both script and frozen (PyInstaller) mode."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).resolve().parent.parent

def appdata_dir() -> Path:
    """Get application data directory in user's AppData."""
    if sys.platform == 'win32':
        base = os.getenv("APPDATA") or str(Path.home() / "AppData/Roaming")
    else:
        base = str(Path.home() / ".config")
    
    p = Path(base) / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p

def config_path() -> Path:
    """Get path to config.json."""
    return appdata_dir() / "config.json"

def cache_reports_dir() -> Path:
    """Get directory for cached reports."""
    p = appdata_dir() / "reports"
    p.mkdir(parents=True, exist_ok=True)
    return p

def log_file_path() -> Path:
    """Get path to log file."""
    return appdata_dir() / "app.log"

def templates_dir() -> Path:
    """Get templates directory."""
    base = get_base_path()
    return base / "templates"