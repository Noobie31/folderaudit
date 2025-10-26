import os
import time
from datetime import datetime, timezone
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import config
import storage
from preview import FilePreview  # renders the table (HTML or Treeview)


class TabOne(ttk.Frame):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self._folders: list[str] = []   # selected folders
        self._rows: list[dict] = []     # one row per folder
        self._build_ui()
        config.register_callback(lambda *_: self._recompute_states_and_render())

    def _build_ui(self) -> None:
        # Toolbar
        bar = ttk.Frame(self)
        bar.pack(fill="x")

        ttk.Button(bar, text="Add Folder", command=self._on_add_folder).pack(
            side="left", padx=(10, 8), pady=10
        )
        self._count_var = tk.StringVar(value="Folders: 0")
        ttk.Label(bar, textvariable=self._count_var).pack(side="left", padx=(0, 10))

        # Body uses grid: preview fills row 0, generate row stays at bottom
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        # Preview (fills available space)
        self._preview = FilePreview(body, theme="light")
        self._preview.widget.grid(row=0, column=0, sticky="nsew", padx=10, pady=(0, 8))

        # Generate button (always visible)
        btn_row = ttk.Frame(body)
        btn_row.grid(row=1, column=0, sticky="e", padx=10, pady=(0, 10))
        ttk.Button(btn_row, text="Generate", command=self._on_generate).pack()

        self._render()

    def _on_add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select a folder")
        if not folder:
            return
        folder = os.path.normpath(folder)
        if folder in self._folders:
            messagebox.showinfo("Already added", "This folder is already in the list.")
            return

        self._folders.append(folder)
        row = self._folder_row(folder)
        if not any(r["file_path"] == row["file_path"] for r in self._rows):
            self._rows.append(row)
        self._render()

    def _on_generate(self) -> None:
        if not self._rows:
            messagebox.showinfo("Nothing to export", "Please add at least one folder.")
            return
        # Let the user pick their own save path
        fpath = filedialog.asksaveasfilename(
            title="Save PDF",
            defaultextension=".pdf",
            initialfile="preview_report.pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not fpath:
            return
        try:
            # 1) Write the chosen PDF
            self._preview.export_pdf(fpath, self._rows)

            # 2) Also archive a copy in ~/Documents/FilePulse/Reports
            # use the first folder's name (or "report") as hint
            title_hint = os.path.basename(self._rows[0].get("file_name") or "report")
            archived = storage.save_report_copy(fpath, title_hint=title_hint)

            messagebox.showinfo(
                "Saved",
                f"PDF saved:\n{fpath}\n\nArchived copy:\n{archived}"
            )
        except Exception as e:
            messagebox.showerror("Export failed", f"Couldn't create PDF:\n{e}")
    # --- helpers (unchanged) ---
    def _folder_row(self, folder: str) -> dict:
        try:
            st = os.stat(folder)
            last_modified_ts = st.st_mtime
            last_modified_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_modified_ts))
        except OSError:
            last_modified_ts = None
            last_modified_str = "—"

        total_size = self._folder_size_bytes(folder)

        neglect_seconds = None
        neglect_str = "—"
        if last_modified_ts is not None:
            now_ts = datetime.now(timezone.utc).timestamp()
            neglect_seconds = max(0, int(now_ts - last_modified_ts))
            neglect_str = _format_duration(neglect_seconds)

        state = self._compute_state(neglect_seconds)

        return {
            "file_path": folder,
            "file_size": total_size,
            "last_modified": last_modified_str,
            "last_worked_by": "—",
            "file_name": os.path.basename(folder) or folder,
            "file_neglect_time": neglect_str,
            "neglect_seconds": neglect_seconds,
            "file_state": state,
        }

    def _compute_state(self, neglect_seconds: int | None) -> str:
        if neglect_seconds is None:
            return "red"
        days = neglect_seconds // 86400
        g, a, r = config.get_thresholds()
        if days <= g:
            return "green"
        elif days <= a:
            return "amber"
        else:
            return "red"

    def _recompute_states_and_render(self) -> None:
        for r in self._rows:
            r["file_state"] = self._compute_state(r.get("neglect_seconds"))
        self._render()

    def _folder_size_bytes(self, folder: str) -> int | None:
        total = 0
        try:
            stack = [folder]
            while stack:
                cur = stack.pop()
                try:
                    with os.scandir(cur) as it:
                        for entry in it:
                            try:
                                if entry.is_dir(follow_symlinks=False):
                                    stack.append(entry.path)
                                elif entry.is_file(follow_symlinks=False):
                                    try:
                                        total += entry.stat(follow_symlinks=False).st_size
                                    except OSError:
                                        pass
                            except OSError:
                                pass
                except OSError:
                    pass
            return total
        except Exception:
            return None

    def _render(self) -> None:
        self._count_var.set(f"Folders: {len(self._folders)}")
        self._preview.render(self._rows)


def _format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "0s"
    parts = []
    days, rem = divmod(seconds, 86400)
    if days:
        parts.append(f"{days}d")
    hours, rem = divmod(rem, 3600)
    if hours:
        parts.append(f"{hours}h")
    minutes, rem = divmod(rem, 60)
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{rem}s")
    return " ".join(parts)
