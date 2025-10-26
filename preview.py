# preview.py
import html
from typing import List, Dict
import tkinter as tk
from tkinter import ttk

# Try HTML webview first; fallback to Treeview if unavailable
try:
    from tkinterweb import HtmlFrame  # pip install tkinterweb
    _WEB_AVAILABLE = True
except Exception:
    _WEB_AVAILABLE = False


class FilePreview:
    """
    Columns:
      1) File path
      2) File size
      3) Last modified
      4) Last worked on by
      5) File name
      6) File neglect time
      7) File state  (colored badge in HTML mode)

    - Uses HtmlFrame scrollbars only (no duplicate outer scrollbar).
    - Export to PDF = vector (fpdf2), includes all rows, independent of viewport.
    """
    COLUMNS = (
        "file_path",
        "file_size",
        "last_modified",
        "last_worked_by",
        "file_name",
        "file_neglect_time",
        "file_state",
    )
    HEADERS = [
        "File path",
        "File size",
        "Last modified",
        "Last worked on by",
        "File name",
        "File neglect time",
        "File state",
    ]

    def __init__(self, parent, theme: str = "light") -> None:
        self.parent = parent
        self.theme = theme
        if _WEB_AVAILABLE:
            # Single source of scrollbars: HtmlFrame itself
            self.widget = HtmlFrame(
                parent,
                messages_enabled=False,
                vertical_scrollbar="auto",
                horizontal_scrollbar="auto",
            )
            self._html_mode = True
        else:
            frame = ttk.Frame(parent)
            self.widget = frame
            self._tree = ttk.Treeview(frame, columns=self.COLUMNS, show="headings")
            self._tree.pack(side="left", fill="both", expand=True)

            sb = ttk.Scrollbar(frame, orient="vertical", command=self._tree.yview)
            sb.pack(side="right", fill="y")
            self._tree.configure(yscrollcommand=sb.set)

            for key, title, width, anchor in [
                ("file_path", "File path", 520, "w"),
                ("file_size", "File size", 110, "e"),
                ("last_modified", "Last modified", 160, "center"),
                ("last_worked_by", "Last worked on by", 160, "center"),
                ("file_name", "File name", 220, "w"),
                ("file_neglect_time", "File neglect time", 150, "center"),
                ("file_state", "File state", 120, "center"),
            ]:
                self._tree.heading(key, text=title)
                self._tree.column(key, width=width, anchor=anchor)

            self._html_mode = False

    # ---------------- Public API ----------------
    def render(self, rows: List[Dict]) -> None:
        if self._html_mode:
            self._render_html(rows)
        else:
            self._render_tree(rows)

    def export_pdf(self, out_path: str, rows: list[dict]) -> None:
        """
        Vector PDF:
        - No MultiCell; manual wrap with explicit (x,y) drawing to prevent overlaps.
        - Two-pass per header & row: measure -> draw borders -> paint text.
        - 'File state' as a color badge (no text).
        """
        from fpdf import FPDF  # pip install fpdf2

        headers = self.HEADERS
        # Column proportions (sum = 1.00): path,size,modified,worked,name,neglect,state
        REL = [0.30, 0.08, 0.13, 0.13, 0.18, 0.12, 0.06]
        LINE_H = 6.0

        pdf = FPDF(orientation="L", unit="mm", format="A4")
        pdf.set_margins(10, 12, 10)
        pdf.set_auto_page_break(auto=True, margin=12)
        pdf.add_page()

        printable_w = pdf.w - pdf.l_margin - pdf.r_margin
        col_w = [printable_w * r for r in REL]

        # -------- helpers --------
        def sanitize(s):
            if s is None: return ""
            s = str(s).replace("—","-").replace("–","-").replace("•","*")
            return s.encode("ascii","ignore").decode("ascii")

        def human_size(n):
            if n in (None, "", "—"):
                return "-"
            try: n = int(n)
            except Exception: return "-"
            units = ["B","KB","MB","GB","TB"]; i = 0; f = float(n)
            while f >= 1024 and i < len(units)-1:
                f /= 1024.0; i += 1
            return f"{f:.1f} {units[i]}"

        def wrap_lines(text: str, width: float, *, font_bold=False) -> list[str]:
            """Return a list of wrapped lines that fit within 'width' without drawing."""
            text = sanitize(text)
            pdf.set_font("Helvetica", style=("B" if font_bold else ""), size=(11 if font_bold else 10))
            if not text:
                return [""]
            lines = []
            cur = ""
            cur_w = 0.0
            max_w = max(1e-3, width)

            for ch in text:
                if ch == "\n":
                    lines.append(cur); cur = ""; cur_w = 0.0
                    continue
                w = pdf.get_string_width(ch)
                if cur_w + w > max_w and cur:
                    lines.append(cur)
                    cur, cur_w = ch, w
                else:
                    cur += ch; cur_w += w
            lines.append(cur)
            return lines

        def draw_text_block(x, y, w, h, text, *, font_bold=False, align="L"):
            """Draw wrapped text inside a box (x,y,w,h) without borders."""
            lines = wrap_lines(text, w, font_bold=font_bold)
            pdf.set_font("Helvetica", style=("B" if font_bold else ""), size=(11 if font_bold else 10))
            for i, line in enumerate(lines):
                yy = y + i*LINE_H
                if yy + LINE_H > y + h:  # avoid drawing outside the cell
                    break
                pdf.set_xy(x, yy)
                pdf.cell(w, LINE_H, line, border=0, align=align)

        def draw_state_badge(x, y, w, h, state):
            s = (state or "").lower()
            if s == "green": pdf.set_fill_color(16,185,129)   # #10B981
            elif s == "amber": pdf.set_fill_color(245,158,11) # #F59E0B
            elif s == "red": pdf.set_fill_color(239,68,68)    # #EF4444
            else: pdf.set_fill_color(229,231,235)             # neutral
            # outer border
            pdf.rect(x, y, w, h, style="D")
            # inner fill
            inset = 1.2
            pdf.rect(x+inset, y+inset, max(0.1, w-2*inset), max(0.1, h-2*inset), style="F")

        def measure_block_height(text, w, *, font_bold=False) -> float:
            """Height needed to draw 'text' in width 'w' using our manual wrapping."""
            lines = wrap_lines(text, w, font_bold=font_bold)
            return max(LINE_H, len(lines) * LINE_H)

        def page_maybe_add_header():
            if pdf.get_y() > (pdf.h - pdf.b_margin - 12):
                pdf.add_page()
                add_header()

        # -------- header (measure -> border -> text) --------
        def add_header():
            x0, y0 = pdf.get_x(), pdf.get_y()
            heights = [measure_block_height(h, col_w[i], font_bold=True) for i, h in enumerate(headers)]
            row_h = max(heights)
            # borders
            x = x0
            for w in col_w:
                pdf.rect(x, y0, w, row_h)
                x += w
            # text
            x = x0
            for i, htxt in enumerate(headers):
                draw_text_block(x, y0, col_w[i], row_h, htxt, font_bold=True, align="L")
                x += col_w[i]
            # move
            pdf.set_xy(x0, y0 + row_h)
            pdf.set_font("Helvetica", size=10)

        # -------- row (measure -> border -> text) --------
        def add_row(vals):
            vals = [sanitize(v) for v in vals]
            x0, y0 = pdf.get_x(), pdf.get_y()

            # measure (wrap path & name; others single line)
            heights = [
                measure_block_height(vals[0], col_w[0]),  # path
                LINE_H,                                   # size
                LINE_H,                                   # modified
                LINE_H,                                   # worked by
                measure_block_height(vals[4], col_w[4]),  # name
                LINE_H,                                   # neglect
                LINE_H,                                   # state box
            ]
            row_h = max(heights)

            # borders for full row
            x = x0
            for w in col_w:
                pdf.rect(x, y0, w, row_h)
                x += w

            # text cells
            x = x0
            draw_text_block(x, y0, col_w[0], row_h, vals[0]); x += col_w[0]              # path
            pdf.set_xy(x, y0); pdf.cell(col_w[1], LINE_H, vals[1], 0, 0, "R"); x += col_w[1]  # size
            pdf.set_xy(x, y0); pdf.cell(col_w[2], LINE_H, vals[2], 0, 0, "L"); x += col_w[2]  # modified
            pdf.set_xy(x, y0); pdf.cell(col_w[3], LINE_H, vals[3], 0, 0, "L"); x += col_w[3]  # worked by
            draw_text_block(x, y0, col_w[4], row_h, vals[4]); x += col_w[4]                  # name
            pdf.set_xy(x, y0); pdf.cell(col_w[5], LINE_H, vals[5], 0, 0, "L");               # neglect
            # state badge
            draw_state_badge(x + col_w[5], y0, col_w[6], row_h, vals[6])

            # advance
            pdf.set_xy(x0, y0 + row_h)
            page_maybe_add_header()

        # -------- render --------
        add_header()
        for r in rows:
            add_row([
                r.get("file_path", ""),
                human_size(r.get("file_size", None)),
                r.get("last_modified", ""),
                r.get("last_worked_by", "—"),
                r.get("file_name", ""),
                r.get("file_neglect_time", "—"),
                r.get("file_state", ""),  # color key only
            ])

        pdf.output(out_path)


    # ---------------- HTML mode ----------------
    def _render_html(self, rows: List[Dict]) -> None:
        def h(s) -> str:
            return html.escape("" if s is None else str(s))

        def human_size(n) -> str:
            if n in (None, "", "—"):
                return "—"
            try:
                n = int(n)
            except Exception:
                return "—"
            units = ["B", "KB", "MB", "GB", "TB"]
            i = 0
            f = float(n)
            while f >= 1024 and i < len(units) - 1:
                f /= 1024.0
                i += 1
            return f"{f:.1f} {units[i]}"

        def state_badge(state: str) -> str:
            s = (state or "").lower()
            if s == "green":  bg, fg, label = "#10B981", "#ffffff", "GREEN"
            elif s == "amber": bg, fg, label = "#F59E0B", "#000000", "AMBER"
            elif s == "red":   bg, fg, label = "#EF4444", "#ffffff", "RED"
            else:              bg, fg, label = "#e5e7eb", "#111827", "—"
            return f"<span class='badge' style='background:{bg};color:{fg};'>{label}</span>"

        trs = []
        for r in rows:
            trs.append(
                "<tr>"
                f"<td class='path'>{h(r.get('file_path'))}</td>"
                f"<td class='size'>{h(human_size(r.get('file_size')))}</td>"
                f"<td class='ts'>{h(r.get('last_modified'))}</td>"
                f"<td class='user'>{h(r.get('last_worked_by'))}</td>"
                f"<td class='name'>{h(r.get('file_name'))}</td>"
                f"<td class='neglect'>{h(r.get('file_neglect_time'))}</td>"
                f"<td class='state'>{state_badge(r.get('file_state'))}</td>"
                "</tr>"
            )
        if not trs:
            trs.append("<tr><td class='empty' colspan='7'>No folders yet. Add one above.</td></tr>")

        bg = "#ffffff" if self.theme == "light" else "#0f1014"
        text = "#000000" if self.theme == "light" else "#e9ecf1"
        muted = "#444444" if self.theme == "light" else "#9aa3ad"
        border = "#e5e7eb" if self.theme == "light" else "#262b35"
        header_bg = "#ffffff" if self.theme == "light" else "#151922"

        # IMPORTANT: .table-wrap has NO overflow; HtmlFrame owns scrollbars
        html_doc = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
* {{ box-sizing: border-box; }}
html, body {{ height:100%; margin:0; background:{bg}; color:{text};
  font-family:-apple-system, Segoe UI, Roboto, Arial, sans-serif; }}
.wrapper {{ height:100%; padding:16px; }}
.table-wrap {{
  width:100%; height:100%;
  background:{bg}; border:1px solid {border}; border-radius:12px;
}}
table {{
  border-collapse:separate; border-spacing:0;
  background:{bg}; color:{text};
  min-width: 1300px;
  width: max(100%, 1300px); /* triggers HtmlFrame's horizontal scrollbar */
}}
thead th {{
  position: sticky; top: 0; z-index: 1;
  text-align:left; padding:12px; font-weight:700; font-size:14px;
  background:{header_bg}; color:{text}; border-bottom:1px solid {border};
  white-space:nowrap;
}}
tbody td {{
  padding:10px 12px; font-size:13px; border-bottom:1px solid {border};
  vertical-align: middle; background:{bg}; color:{text}; white-space:nowrap;
}}
.badge {{ display:inline-block; padding:4px 10px; border-radius:999px;
  font-size:12px; font-weight:700; letter-spacing:0.3px; }}
td.path {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
td.size {{ text-align:right; }}
td.ts, td.user, td.neglect {{ color:{muted}; }}
td.name {{ font-weight:600; }}
td.empty {{ color:{muted}; text-align:center; padding:18px; white-space:normal; }}
</style>
</head>
<body>
  <div class="wrapper">
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>File path</th>
            <th>File size</th>
            <th>Last modified</th>
            <th>Last worked on by</th>
            <th>File name</th>
            <th>File neglect time</th>
            <th>File state</th>
          </tr>
        </thead>
        <tbody>
          {''.join(trs)}
        </tbody>
      </table>
    </div>
  </div>
</body>
</html>"""

        if hasattr(self.widget, "load_html"):
            self.widget.load_html(html_doc)
        elif hasattr(self.widget, "add_html"):
            self.widget.load_html("<!doctype html><html><body></body></html>")
            self.widget.add_html(html_doc)
        else:
            setter = getattr(self.widget, "set_html", None)
            if callable(setter):
                setter(html_doc)
            else:
                raise RuntimeError("No supported method to set HTML in HtmlFrame.")

    # ---------------- Fallback Treeview ----------------
    def _render_tree(self, rows: List[Dict]) -> None:
        for i in self._tree.get_children():
            self._tree.delete(i)
        for r in rows:
            vals = (
                r.get("file_path", ""),
                _human_size(r.get("file_size", None)),
                r.get("last_modified", ""),
                r.get("last_worked_by", "—"),
                r.get("file_name", ""),
                r.get("file_neglect_time", "—"),
                (r.get("file_state", "") or "").upper(),
            )
            self._tree.insert("", "end", values=vals)


def _human_size(n) -> str:
    if n in (None, "", "—"):
        return "—"
    try:
        n = int(n)
    except Exception:
        return "—"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    f = float(n)
    while f >= 1024 and i < len(units) - 1:
        f /= 1024.0
        i += 1
    return f"{f:.1f} {units[i]}"
