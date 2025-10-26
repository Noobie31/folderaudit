# storage.py
from __future__ import annotations
import json
import os
import shutil
import time
from pathlib import Path
from typing import Dict, List

# App archive folder: ~/Documents/FilePulse/Reports
APP_DIR = Path.home() / "Documents" / "FilePulse" / "Reports"
INDEX = APP_DIR / "index.json"


# ---------------- basics ----------------

def ensure_repo() -> Path:
    """
    Ensure the archive folder and index.json exist.
    Returns the archive Path.
    """
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX.exists():
        INDEX.write_text("[]", encoding="utf-8")
    return APP_DIR


def _load_index() -> List[Dict]:
    ensure_repo()
    try:
        return json.loads(INDEX.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_index(items: List[Dict]) -> None:
    ensure_repo()
    INDEX.write_text(json.dumps(items, indent=2), encoding="utf-8")


# ---------------- saving ----------------

def _unique_dest(preferred_name: str) -> Path:
    """
    Return a unique path inside APP_DIR using the same filename
    the user chose. If it already exists, append ' (2)', ' (3)', ...
    before the extension (Windows-style).
    """
    ensure_repo()

    # Basic sanitize (the source file should already be valid on disk)
    base = "".join(c for c in preferred_name if c not in '\\/:*?"<>|').strip() or "report.pdf"

    # Split name and extension
    dot = base.rfind(".")
    if dot <= 0:  # no ext or hidden file with no ext
        stem, ext = base, ""
    else:
        stem, ext = base[:dot], base[dot:]

    candidate = APP_DIR / f"{stem}{ext}"
    n = 2
    while candidate.exists():
        candidate = APP_DIR / f"{stem} ({n}){ext}"
        n += 1
    return candidate


def save_report_copy(src_pdf_path: str, title_hint: str | None = None) -> str:
    """
    Copy an existing PDF into the archive using the SAME filename
    the user saved. If a clash occurs, auto-dedupe with ' (2)', ' (3)', ...

    Also appends a record to index.json.

    Returns the absolute path to the archived copy.
    """
    ensure_repo()
    src = Path(src_pdf_path)
    if not src.exists():
        raise FileNotFoundError(f"Source PDF not found: {src_pdf_path}")

    dst = _unique_dest(src.name)
    shutil.copy2(src, dst)

    item = {
        "ts": int(time.time()),           # when archived (epoch seconds)
        "name": dst.name,                 # filename in archive folder
        "title": (title_hint or src.stem),
        "size": dst.stat().st_size,       # bytes
        "path": str(dst),                 # absolute path to archived copy
        "original_name": src.name,        # what the user chose when saving
    }
    items = _load_index()
    items.append(item)
    _save_index(items)
    return str(dst)


# ---------------- listing ----------------

def list_reports() -> List[Dict]:
    """
    Return all archived reports sorted newest-first.
    If the index is empty/corrupt, reconstruct quickly from files in the folder.
    """
    ensure_repo()
    items = _load_index()

    if not items:
        # Rebuild from existing PDFs if any (best-effort)
        for p in APP_DIR.glob("*.pdf"):
            try:
                st = p.stat()
            except OSError:
                continue
            items.append({
                "ts": int(st.st_mtime),
                "name": p.name,
                "title": p.stem,
                "size": st.st_size,
                "path": str(p),
                "original_name": p.name,
            })
        _save_index(items)

    items.sort(key=lambda x: x.get("ts", 0), reverse=True)
    return items


# ---------------- optional helpers ----------------

def delete_report(path_or_name: str) -> bool:
    """
    Delete a report both from disk and index.json.
    Accepts either the absolute path or the filename inside APP_DIR.
    Returns True if something was deleted.
    """
    ensure_repo()
    # Resolve path
    p = Path(path_or_name)
    if not p.is_absolute():
        p = APP_DIR / path_or_name

    deleted = False
    try:
        if p.exists():
            p.unlink()
            deleted = True
    except Exception:
        pass

    # Update index
    items = _load_index()
    new_items = [it for it in items if Path(it.get("path", "")) != p]
    if len(new_items) != len(items):
        _save_index(new_items)
        deleted = True

    return deleted
