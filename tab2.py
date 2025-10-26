# tab2.py
from __future__ import annotations
import os
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import time

import storage


class TabTwo(ttk.Frame):
    """
    Tab 2: List all archived reports (newest first) from ~/Documents/FilePulse/Reports.
    Columns: Title, Saved at, Size, Path
    Toolbar: Refresh, Open, Show in Folder
    """
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self._build_ui()
        self._load_rows()

    def _build_ui(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(8, 4), padx=10)

        ttk.Button(bar, text="Refresh", command=self._load_rows).pack(side="left")
        ttk.Button(bar, text="Open", command=self._open_selected).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="Show in Folder", command=self._reveal_selected).pack(side="left", padx=(8, 0))

        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("title", "when", "size", "path")
        self._tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="browse")
        self._tree.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(wrap, orient="vertical", command=self._tree.yview)
        sb.pack(side="right", fill="y")
        self._tree.configure(yscrollcommand=sb.set)

        self._tree.heading("title", text="Title")
        self._tree.heading("when", text="Saved at")
        self._tree.heading("size", text="Size")
        self._tree.heading("path", text="Path")

        self._tree.column("title", width=240, anchor="w")
        self._tree.column("when", width=160, anchor="center")
        self._tree.column("size", width=100, anchor="e")
        self._tree.column("path", width=520, anchor="w")

    def _load_rows(self) -> None:
        try:
            items = storage.list_reports()
        except Exception as e:
            messagebox.showerror("Error", f"Couldn't load archive:\n{e}")
            return
        self._tree.delete(*self._tree.get_children())

        def human_size(n):
            try:
                n = int(n)
            except Exception:
                return "-"
            units = ["B","KB","MB","GB","TB"]
            i = 0; f = float(n)
            while f >= 1024 and i < len(units)-1:
                f /= 1024.0; i += 1
            return f"{f:.1f} {units[i]}"

        for it in items:
            when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(it.get("ts", 0)))
            size = human_size(it.get("size", 0))
            self._tree.insert("", "end", values=(it.get("title",""), when, size, it.get("path","")))

    def _selected_path(self) -> str | None:
        sel = self._tree.selection()
        if not sel:
            return None
        vals = self._tree.item(sel[0], "values")
        return vals[3] if len(vals) >= 4 else None

    def _open_selected(self) -> None:
        path = self._selected_path()
        if not path:
            messagebox.showinfo("Open", "Select a report first.")
            return
        if not os.path.exists(path):
            messagebox.showerror("Open", "File no longer exists.")
            return
        try:
            os.startfile(path)  # Windows
        except Exception as e:
            messagebox.showerror("Open", f"Couldn't open:\n{e}")

    def _reveal_selected(self) -> None:
        path = self._selected_path()
        if not path:
            messagebox.showinfo("Show in Folder", "Select a report first.")
            return
        folder = os.path.dirname(path)
        if not os.path.exists(folder):
            messagebox.showerror("Show in Folder", "Folder no longer exists.")
            return
        try:
            subprocess.Popen(f'explorer /select,"{path}"')
        except Exception:
            try:
                os.startfile(folder)
            except Exception as e:
                messagebox.showerror("Show in Folder", f"Couldn't open folder:\n{e}")
