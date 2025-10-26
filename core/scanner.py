# core/scanner.py
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterable, List, Dict, Optional
import os
import stat
import sys
from .logger import logger

def _owner_for(path: Path) -> Optional[str]:
    """Get file owner (Windows only)."""
    if sys.platform != 'win32':
        return None
    
    try:
        import win32security
        sd = win32security.GetFileSecurity(
            str(path), 
            win32security.OWNER_SECURITY_INFORMATION
        )
        owner_sid = sd.GetSecurityDescriptorOwner()
        name, domain, _ = win32security.LookupAccountSid(None, owner_sid)
        return f"{domain}\\{name}" if domain else name
    except ImportError:
        logger.debug("pywin32 not available, owner info disabled")
        return None
    except Exception as e:
        logger.debug(f"Could not get owner for {path}: {e}")
        return None

def _modified_dt(path: Path) -> datetime:
    """Get file modification datetime in UTC."""
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc)

def scan_folders(folders: Iterable[Path], callback=None) -> List[Dict]:
    """
    Scan folders recursively and collect file metadata.
    
    Args:
        folders: List of folder paths to scan
        callback: Optional callback(current, total) for progress updates
    
    Returns:
        List of dictionaries with file information
    """
    rows: List[Dict] = []
    total_files = 0
    processed = 0
    
    # Count total files first for progress
    if callback:
        for root in folders:
            if root.exists():
                for _, _, filenames in os.walk(root):
                    total_files += len(filenames)
    
    logger.info(f"Starting scan of {len(list(folders))} folder(s)")
    
    for root in folders:
        if not root.exists():
            logger.warning(f"Folder does not exist: {root}")
            continue
        
        try:
            for dirpath, _, filenames in os.walk(root):
                for fn in filenames:
                    p = Path(dirpath) / fn
                    
                    try:
                        st = p.stat()
                    except (OSError, PermissionError) as e:
                        logger.debug(f"Cannot access {p}: {e}")
                        processed += 1
                        if callback:
                            callback(processed, total_files)
                        continue
                    
                    # Skip directories, symlinks, and special files
                    if not stat.S_ISREG(st.st_mode):
                        processed += 1
                        if callback:
                            callback(processed, total_files)
                        continue
                    
                    size_bytes = st.st_size
                    mod = _modified_dt(p)
                    owner = _owner_for(p)
                    
                    rows.append({
                        "file_path": str(p),
                        "file_size": size_bytes,
                        "modified": mod,
                        "owner": owner or "Unknown",
                        "file_name": p.name,
                    })
                    
                    processed += 1
                    if callback:
                        callback(processed, total_files)
                        
        except Exception as e:
            logger.error(f"Error scanning folder {root}: {e}", exc_info=True)
    
    logger.info(f"Scan completed: {len(rows)} files found")
    return rows