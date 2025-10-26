import sys
import tkinter as tk
from tkinter import ttk

# Windows DPI fix to keep the UI crisp on high-DPI screens (safe no-op on other OSes)
if sys.platform.startswith("win"):
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Per-monitor DPI Aware (Windows 8.1+)
    except Exception:
        pass

from tab1 import TabOne
from tab2 import TabTwo
from tab3 import TabThree


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Python Tabs App")
        self._set_default_size(900, 600)
        self._configure_style()
        self._build_ui()

    def _set_default_size(self, width: int, height: int) -> None:
        # Center the window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(600, 400)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        # Use a nice built-in theme if available
        preferred = "vista" if sys.platform.startswith("win") else "clam"
        try:
            style.theme_use(preferred)
        except tk.TclError:
            pass

        # Slight padding defaults
        style.configure("TNotebook", tabposition="n")
        style.configure("TNotebook.Tab", padding=(16, 8))

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        # Create tabs from separate modules
        tab1 = TabOne(notebook)
        tab2 = TabTwo(notebook)
        tab3 = TabThree(notebook)

        notebook.add(tab1, text="Analysis")
        notebook.add(tab2, text="Tab 2")
        notebook.add(tab3, text="Tab 3")

        # Optional: a tiny status bar
        status = ttk.Label(self, text="Ready", anchor="w")
        status.pack(fill="x", side="bottom")


if __name__ == "__main__":
    app = App()
    app.mainloop()
