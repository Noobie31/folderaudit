# tab3.py
import tkinter as tk
from tkinter import ttk, messagebox
import config


class TabThree(ttk.Frame):
    """
    Tab 3: Configure "traffic signal" thresholds (in days).
      - Green: 0..G
      - Amber: G+1..A
      - Red:   A+1..R  (and beyond stays Red)
    """
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self._build_ui()
        self._load_current()

    def _build_ui(self) -> None:
        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True, padx=16, pady=16)

        ttk.Label(wrap, text="File State Thresholds (in days)", font=("", 12, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10)
        )

        # Green
        ttk.Label(wrap, text="Green alert").grid(row=1, column=0, sticky="w", pady=6)
        self.green_var = tk.StringVar()
        ttk.Entry(wrap, textvariable=self.green_var, width=10).grid(row=1, column=1, sticky="w")

        # Amber
        ttk.Label(wrap, text="Amber alert").grid(row=2, column=0, sticky="w", pady=6)
        self.amber_var = tk.StringVar()
        ttk.Entry(wrap, textvariable=self.amber_var, width=10).grid(row=2, column=1, sticky="w")

        # Red
        ttk.Label(wrap, text="Red alert").grid(row=3, column=0, sticky="w", pady=6)
        self.red_var = tk.StringVar()
        ttk.Entry(wrap, textvariable=self.red_var, width=10).grid(row=3, column=1, sticky="w")

        # Helper text
        help_txt = (
            "Ranges:\n"
            "  Green: 0..G days\n"
            "  Amber: (G+1)..A days\n"
            "  Red:   (A+1)..R days (and beyond stays Red)"
        )
        ttk.Label(wrap, text=help_txt).grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 12))

        # Save button
        ttk.Button(wrap, text="Save thresholds", command=self._on_save).grid(
            row=5, column=0, sticky="w", pady=6
        )

        # Layout tweaks
        for i in range(3):
            wrap.columnconfigure(i, weight=0)
        wrap.columnconfigure(2, weight=1)

    def _load_current(self) -> None:
        g, a, r = config.get_thresholds()
        self.green_var.set(str(g))
        self.amber_var.set(str(a))
        self.red_var.set(str(r))

    def _on_save(self) -> None:
        try:
            g = int(self.green_var.get())
            a = int(self.amber_var.get())
            r = int(self.red_var.get())
            if g < 0 or a < 0 or r < 0:
                raise ValueError("Values must be non-negative.")
            if not (g <= a <= r):
                raise ValueError("Must satisfy: Green ≤ Amber ≤ Red.")
        except Exception as e:
            messagebox.showerror("Invalid thresholds", str(e))
            return

        config.set_thresholds(g, a, r)
        messagebox.showinfo("Saved", f"Thresholds updated:\nGreen={g}, Amber={a}, Red={r}")
