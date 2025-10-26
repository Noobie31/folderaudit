# app.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime, timezone
import threading
import sys
import os
import subprocess

from core.config import load_config, save_config, Config, Thresholds, Schedule, validate_email_list
from core.scanner import scan_folders
from core.report import render_pdf_reportlab, cache_copy, human_size, neglect_days, color_state, format_neglect_time
from core.emailer import send_with_resend, test_api_key
from core.paths import cache_reports_dir, appdata_dir
from core.scheduler import start_scheduler, schedule_job, ALLOWED_FREQUENCIES, get_next_run_time
from core.logger import logger

# ---------- Globals ----------
cfg = load_config()
sched = start_scheduler()
selected_folders = []
latest_output_path = None
is_generating = False

ALLOWED_FREQ = list(ALLOWED_FREQUENCIES)

# ---------- Main Window ----------
root = tk.Tk()
root.title("PDF Reporter")
root.geometry("1100x750")
root.minsize(900, 600)

# Set icon if available
try:
    if sys.platform == 'win32':
        icon_path = Path(__file__).parent / "icon.ico"
        if icon_path.exists():
            root.iconbitmap(str(icon_path))
except Exception:
    pass

# Main notebook
nb = ttk.Notebook(root)
nb.pack(fill="both", expand=True, padx=5, pady=5)

# Tab 1: Report (with subtabs)
tab_report = ttk.Frame(nb)
nb.add(tab_report, text="Report")

sub_nb = ttk.Notebook(tab_report)
sub_nb.pack(fill="both", expand=True)

sub_current = ttk.Frame(sub_nb)
sub_saved = ttk.Frame(sub_nb)
sub_nb.add(sub_current, text="Current Report")
sub_nb.add(sub_saved, text="Saved Reports")

# Tab 2: Global Settings
tab_global = ttk.Frame(nb)
nb.add(tab_global, text="Global Settings")

# ========== SUBTAB: CURRENT REPORT ==========

# Top: Select folders
frm_top = ttk.Frame(sub_current)
frm_top.pack(fill="x", padx=10, pady=8)

lbl_sel = ttk.Label(frm_top, text="Selected folders:")
lbl_sel.pack(side="left", padx=(0, 5))

lst_folders = tk.Listbox(frm_top, height=4)
lst_folders.pack(side="left", fill="x", expand=True, padx=5)

def on_select_folders():
    """Open folder dialog and add to selection list."""
    folder = filedialog.askdirectory(title="Select folder to scan")
    if folder:
        p = Path(folder).resolve()
        if p not in selected_folders:
            selected_folders.append(p)
            lst_folders.insert("end", str(p))
            logger.info(f"Added folder: {p}")

def on_remove_folder():
    """Remove selected folder from list."""
    selection = lst_folders.curselection()
    if selection:
        idx = selection[0]
        removed = selected_folders.pop(idx)
        lst_folders.delete(idx)
        logger.info(f"Removed folder: {removed}")

btn_frame = ttk.Frame(frm_top)
btn_frame.pack(side="right")

btn_select = ttk.Button(btn_frame, text="Add Folder...", command=on_select_folders)
btn_select.pack(pady=2)

btn_remove = ttk.Button(btn_frame, text="Remove", command=on_remove_folder)
btn_remove.pack(pady=2)

# Middle: Preview table
frm_mid = ttk.Frame(sub_current)
frm_mid.pack(fill="both", expand=True, padx=10, pady=8)

ttk.Label(frm_mid, text="Preview (first 500 files):").pack(anchor="w", pady=(0, 4))

# Create a frame for the tree and scrollbars
tree_frame = ttk.Frame(frm_mid)
tree_frame.pack(fill="both", expand=True)

cols = ("file_path", "file_size", "modified", "owner", "file_name", "neglect_time", "state")
tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=15)

for c, label in zip(cols, [
    "File path", "File size", "Last changed", 
    "Owner", "File name", "Neglect time", "State"
]):
    tree.heading(c, text=label)
    tree.column(c, width=150 if c == "file_path" else 100, anchor="w")

# Scrollbars
vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

tree.grid(row=0, column=0, sticky="nsew")
vsb.grid(row=0, column=1, sticky="ns")
hsb.grid(row=1, column=0, sticky="ew")

tree_frame.grid_rowconfigure(0, weight=1)
tree_frame.grid_columnconfigure(0, weight=1)

# Progress bar
progress_var = tk.DoubleVar()
progress_bar = ttk.Progressbar(sub_current, variable=progress_var, maximum=100)
progress_bar.pack(fill="x", padx=10, pady=(0, 5))
progress_bar.pack_forget()  # Hide initially

progress_label = ttk.Label(sub_current, text="")
progress_label.pack(pady=(0, 5))
progress_label.pack_forget()  # Hide initially

# Output path
frm_out = ttk.Frame(sub_current)
frm_out.pack(fill="x", padx=10, pady=(0, 4))

var_out = tk.StringVar(value=str(appdata_dir() / "reports"))
ttk.Label(frm_out, text="Report will be saved to: ").pack(side="left")
ttk.Label(frm_out, textvariable=var_out, foreground="#0066cc").pack(side="left")

def change_output_dir():
    """Change output directory."""
    folder = filedialog.askdirectory(title="Select output directory", initialdir=var_out.get())
    if folder:
        var_out.set(folder)
        logger.info(f"Output directory changed to: {folder}")

ttk.Button(frm_out, text="Change...", command=change_output_dir).pack(side="right", padx=5)

# Bottom: Generate button
frm_bottom = ttk.Frame(sub_current)
frm_bottom.pack(fill="x", padx=10, pady=8)

btn_gen = ttk.Button(frm_bottom, text="Generate PDF Report", state="normal")
btn_gen.pack(side="right")

def populate_preview(rows):
    """Populate the preview tree with file data."""
    tree.delete(*tree.get_children())
    
    max_rows = 500
    for r in rows[:max_rows]:
        # Truncate long paths
        path = r["file_path"]
        if len(path) > 60:
            path = "..." + path[-57:]
        
        tree.insert("", "end", values=(
            path,
            r["file_size_h"],
            r["modified_s"],
            r["owner"][:20],
            r["file_name"][:30],
            r["neglect_s"],
            r["state_title"]
        ))
    
    if len(rows) > max_rows:
        tree.insert("", "end", values=(
            f"... and {len(rows) - max_rows} more files (see PDF)",
            "", "", "", "", "", ""
        ))

def update_progress(current, total):
    """Update progress bar (called from scanner thread)."""
    if total > 0:
        percent = (current / total) * 100
        root.after(0, lambda: progress_var.set(percent))
        root.after(0, lambda: progress_label.config(text=f"Scanning: {current}/{total} files"))

def do_generate():
    """Generate PDF report (runs in thread)."""
    global latest_output_path, is_generating
    
    try:
        is_generating = True
        
        # Show progress
        root.after(0, lambda: progress_bar.pack(fill="x", padx=10, pady=(0, 5)))
        root.after(0, lambda: progress_label.pack(pady=(0, 5)))
        root.after(0, lambda: btn_gen.config(state="disabled", text="Generating..."))
        root.after(0, lambda: progress_var.set(0))
        root.after(0, lambda: progress_label.config(text="Starting scan..."))
        
        if not selected_folders:
            root.after(0, lambda: messagebox.showwarning(
                "No folders selected",
                "Please select at least one folder to scan."
            ))
            return
        
        # Scan folders
        logger.info("Starting folder scan")
        rows_src = scan_folders(selected_folders, callback=update_progress)
        
        if not rows_src:
            root.after(0, lambda: messagebox.showinfo(
                "No files found",
                "No files were found in the selected folders."
            ))
            return
        
        root.after(0, lambda: progress_label.config(text="Processing files..."))
        
        now = datetime.now(timezone.utc)
        
        # Transform data for preview
        vis_rows = []
        for r in rows_src:
            days = neglect_days(now, r["modified"])
            state = color_state(days, cfg.thresholds.red, cfg.thresholds.amber, cfg.thresholds.green)
            vis_rows.append({
                "file_path": r["file_path"],
                "file_size_h": human_size(r["file_size"]),
                "modified_s": r["modified"].strftime("%Y-%m-%d %H:%M UTC"),
                "owner": r["owner"],
                "file_name": r["file_name"],
                "neglect_s": format_neglect_time(days),
                "state_title": state.capitalize() if state else "—"
            })
        
        # Update preview
        root.after(0, lambda: populate_preview(vis_rows))
        
        # Generate PDF
        root.after(0, lambda: progress_label.config(text="Generating PDF..."))
        
        out_dir = Path(var_out.get())
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"report_{now.strftime('%Y%m%d_%H%M%S')}.pdf"
        
        render_pdf_reportlab(rows_src, cfg.thresholds, now, out_path)
        
        # Cache copy
        cached = cache_copy(out_path)
        latest_output_path = cached
        
        logger.info(f"Report generated: {out_path}")
        
        root.after(0, lambda: messagebox.showinfo(
            "Report Generated",
            f"PDF report created successfully!\n\nSaved to:\n{out_path}\n\n"
            f"Total files: {len(rows_src)}"
        ))
        
        # Refresh saved reports
        root.after(0, refresh_saved)
        
    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        root.after(0, lambda: messagebox.showerror(
            "Generation Error",
            f"Failed to generate report:\n\n{str(e)}"
        ))
    
    finally:
        is_generating = False
        root.after(0, lambda: progress_bar.pack_forget())
        root.after(0, lambda: progress_label.pack_forget())
        root.after(0, lambda: btn_gen.config(state="normal", text="Generate PDF Report"))
        root.after(0, lambda: progress_var.set(0))

def on_click_generate():
    """Start PDF generation in background thread."""
    if is_generating:
        messagebox.showinfo("Please wait", "Report generation is already in progress.")
        return
    
    threading.Thread(target=do_generate, daemon=True).start()

btn_gen.config(command=on_click_generate)

# ========== SUBTAB: SAVED REPORTS ==========

frm_saved = ttk.Frame(sub_saved)
frm_saved.pack(fill="both", expand=True, padx=10, pady=8)

ttk.Label(frm_saved, text="Previously generated reports (double-click to open):").pack(anchor="w", pady=(0, 4))

# Create a frame for the tree and scrollbars
tree_saved_frame = ttk.Frame(frm_saved)
tree_saved_frame.pack(fill="both", expand=True)

cols2 = ("ts", "name", "size", "path")
tree_saved = ttk.Treeview(tree_saved_frame, columns=cols2, show="headings", height=20)

for c, label, width in [
    ("ts", "Generated", 180),
    ("name", "Filename", 300),
    ("size", "Size", 100),
    ("path", "Path", 400)
]:
    tree_saved.heading(c, text=label)
    tree_saved.column(c, width=width, anchor="w")

vsb2 = ttk.Scrollbar(tree_saved_frame, orient="vertical", command=tree_saved.yview)
hsb2 = ttk.Scrollbar(tree_saved_frame, orient="horizontal", command=tree_saved.xview)
tree_saved.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)

tree_saved.grid(row=0, column=0, sticky="nsew")
vsb2.grid(row=0, column=1, sticky="ns")
hsb2.grid(row=1, column=0, sticky="ew")

tree_saved_frame.grid_rowconfigure(0, weight=1)
tree_saved_frame.grid_columnconfigure(0, weight=1)

def refresh_saved():
    """Refresh the list of saved reports."""
    tree_saved.delete(*tree_saved.get_children())
    
    try:
        rdir = cache_reports_dir()
        items = sorted(rdir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
        
        for p in items:
            ts = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            size = human_size(p.stat().st_size)
            tree_saved.insert("", "end", values=(ts, p.name, size, str(p)))
        
        logger.info(f"Refreshed saved reports: {len(items)} found")
        
    except Exception as e:
        logger.error(f"Error refreshing saved reports: {e}", exc_info=True)

def open_selected_pdf(event=None):
    """Open selected PDF with default application."""
    sel = tree_saved.selection()
    if not sel:
        return
    
    path = Path(tree_saved.item(sel[0], "values")[3])
    
    try:
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.run(['open', str(path)])
        else:
            subprocess.run(['xdg-open', str(path)])
        
        logger.info(f"Opened PDF: {path}")
        
    except Exception as e:
        logger.error(f"Error opening PDF: {e}", exc_info=True)
        messagebox.showerror("Error", f"Could not open file:\n{e}")

def delete_selected_pdf():
    """Delete selected PDF from cache."""
    sel = tree_saved.selection()
    if not sel:
        messagebox.showinfo("No selection", "Please select a report to delete.")
        return
    
    path = Path(tree_saved.item(sel[0], "values")[3])
    
    if messagebox.askyesno("Confirm Delete", f"Delete this report?\n\n{path.name}"):
        try:
            path.unlink()
            refresh_saved()
            logger.info(f"Deleted report: {path}")
            messagebox.showinfo("Deleted", "Report deleted successfully.")
        except Exception as e:
            logger.error(f"Error deleting report: {e}", exc_info=True)
            messagebox.showerror("Error", f"Could not delete file:\n{e}")

tree_saved.bind("<Double-1>", open_selected_pdf)

frm_saved_btns = ttk.Frame(sub_saved)
frm_saved_btns.pack(fill="x", padx=10, pady=5)

ttk.Button(frm_saved_btns, text="Refresh", command=refresh_saved).pack(side="left", padx=2)
ttk.Button(frm_saved_btns, text="Open", command=open_selected_pdf).pack(side="left", padx=2)
ttk.Button(frm_saved_btns, text="Delete", command=delete_selected_pdf).pack(side="left", padx=2)

def open_reports_folder():
    """Open the reports folder in file explorer."""
    try:
        folder = cache_reports_dir()
        if sys.platform == 'win32':
            os.startfile(folder)
        elif sys.platform == 'darwin':
            subprocess.run(['open', str(folder)])
        else:
            subprocess.run(['xdg-open', str(folder)])
    except Exception as e:
        logger.error(f"Error opening folder: {e}", exc_info=True)
        messagebox.showerror("Error", f"Could not open folder:\n{e}")

ttk.Button(frm_saved_btns, text="Open Folder", command=open_reports_folder).pack(side="right", padx=2)

# Initial load
refresh_saved()

# ========== TAB 2: GLOBAL SETTINGS ==========

# Create scrollable frame
canvas = tk.Canvas(tab_global)
scrollbar = ttk.Scrollbar(tab_global, orient="vertical", command=canvas.yview)
scrollable_frame = ttk.Frame(canvas)

scrollable_frame.bind(
    "<Configure>",
    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)

canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

pad = {"padx": 10, "pady": 8}

# === API KEY SECTION ===
frm_api = ttk.LabelFrame(scrollable_frame, text="Resend API Configuration")
frm_api.pack(fill="x", **pad)

ttk.Label(frm_api, text="API Key (required for email functionality):").pack(anchor="w", padx=5, pady=(5, 2))

var_api_key = tk.StringVar(value=cfg.api_key)
ent_api = ttk.Entry(frm_api, textvariable=var_api_key, width=60, show="*")
ent_api.pack(fill="x", padx=5, pady=(0, 5))

def toggle_api_visibility():
    if ent_api.cget('show') == '*':
        ent_api.config(show='')
        btn_show_api.config(text="Hide")
    else:
        ent_api.config(show='*')
        btn_show_api.config(text="Show")

btn_frame_api = ttk.Frame(frm_api)
btn_frame_api.pack(fill="x", padx=5, pady=(0, 8))

btn_show_api = ttk.Button(btn_frame_api, text="Show", command=toggle_api_visibility, width=10)
btn_show_api.pack(side="left", padx=(0, 5))

def save_api_key():
    key = var_api_key.get().strip()
    if not key:
        messagebox.showwarning("Empty Key", "Please enter an API key.")
        return
    
    if test_api_key(key):
        cfg.api_key = key
        if save_config(cfg):
            messagebox.showinfo("Saved", "API key saved successfully!")
        else:
            messagebox.showerror("Error", "Failed to save API key.")
    else:
        messagebox.showerror("Invalid Key", "The API key appears to be invalid.")

ttk.Button(btn_frame_api, text="Save API Key", command=save_api_key).pack(side="left")

ttk.Label(frm_api, text="Get your API key from: https://resend.com/api-keys", 
          foreground="#0066cc", cursor="hand2").pack(anchor="w", padx=5, pady=(0, 5))

# === EMAIL RECIPIENTS ===
frm_emails = ttk.LabelFrame(scrollable_frame, text="Email Recipients")
frm_emails.pack(fill="x", **pad)

ttk.Label(frm_emails, text="Recipient emails (comma-separated):").pack(anchor="w", padx=5, pady=(5, 2))

var_recip = tk.StringVar(value=cfg.recipients)
ent_recip = ttk.Entry(frm_emails, textvariable=var_recip, width=80)
ent_recip.pack(fill="x", padx=5, pady=(0, 5))

def save_recip():
    emails = var_recip.get().strip()
    valid = validate_email_list(emails)
    
    if emails and not valid:
        messagebox.showwarning("Invalid Emails", "No valid email addresses found.")
        return
    
    cfg.recipients = emails
    if save_config(cfg):
        messagebox.showinfo("Saved", f"Recipients saved! ({len(valid)} valid email(s))")
    else:
        messagebox.showerror("Error", "Failed to save recipients.")

ttk.Button(frm_emails, text="Save Recipients", command=save_recip).pack(anchor="e", padx=5, pady=(0, 8))

# === THRESHOLDS ===
frm_thresh = ttk.LabelFrame(scrollable_frame, text="File Neglect Thresholds (days)")
frm_thresh.pack(fill="x", **pad)

ttk.Label(frm_thresh, text="Define inclusive day ranges for color coding:").pack(anchor="w", padx=5, pady=(5, 5))

def make_range_row(parent, label, current, color):
    r = ttk.Frame(parent)
    r.pack(fill="x", padx=5, pady=2)
    
    color_label = tk.Label(r, text="  ", bg=color, width=2, relief="solid", borderwidth=1)
    color_label.pack(side="left", padx=(0, 5))
    
    ttk.Label(r, text=f"{label}:", width=8).pack(side="left")
    ttk.Label(r, text="from").pack(side="left", padx=(5, 2))
    
    v1 = tk.StringVar(value=str(current[0]))
    e1 = ttk.Entry(r, textvariable=v1, width=6)
    e1.pack(side="left", padx=2)
    
    ttk.Label(r, text="to").pack(side="left", padx=2)
    
    v2 = tk.StringVar(value=str(current[1]))
    e2 = ttk.Entry(r, textvariable=v2, width=6)
    e2.pack(side="left", padx=2)
    
    ttk.Label(r, text="days").pack(side="left", padx=(2, 0))
    
    return v1, v2

v_gr1, v_gr2 = make_range_row(frm_thresh, "Green", cfg.thresholds.green, "#43a047")
v_am1, v_am2 = make_range_row(frm_thresh, "Amber", cfg.thresholds.amber, "#fb8c00")
v_red1, v_red2 = make_range_row(frm_thresh, "Red", cfg.thresholds.red, "#e53935")

def save_thresh():
    try:
        red = (int(v_red1.get()), int(v_red2.get()))
        amber = (int(v_am1.get()), int(v_am2.get()))
        green = (int(v_gr1.get()), int(v_gr2.get()))
    except ValueError:
        messagebox.showerror("Invalid Input", "Thresholds must be integers.")
        return
    
    # Validate
    for name, (start, end) in [("Red", red), ("Amber", amber), ("Green", green)]:
        if start < 0 or end < 0:
            messagebox.showerror("Invalid Range", f"{name} range cannot be negative.")
            return
        if start > end:
            messagebox.showerror("Invalid Range", f"{name} range: start must be ≤ end.")
            return
        if end > 365:
            messagebox.showerror("Invalid Range", f"{name} range exceeds 365 days.")
            return
    
    # Check overlaps
    def overlaps(a, b):
        return not (a[1] < b[0] or b[1] < a[0])
    
    if overlaps(red, amber) or overlaps(red, green) or overlaps(amber, green):
        messagebox.showerror("Overlap Detected", "Ranges must not overlap.")
        return
    
    cfg.thresholds = Thresholds(red, amber, green)
    if save_config(cfg):
        messagebox.showinfo("Saved", "Thresholds saved successfully!")
    else:
        messagebox.showerror("Error", "Failed to save thresholds.")

ttk.Button(frm_thresh, text="Save Thresholds", command=save_thresh).pack(anchor="e", padx=5, pady=(5, 8))

# === SCHEDULER ===
frm_sched = ttk.LabelFrame(scrollable_frame, text="Automated Report Scheduling")
frm_sched.pack(fill="x", **pad)

ttk.Label(frm_sched, text="Automatically generate and email reports on a schedule:").pack(anchor="w", padx=5, pady=(5, 5))

var_date = tk.StringVar(value=cfg.schedule.date or datetime.now().strftime("%Y-%m-%d"))
var_time = tk.StringVar(value=cfg.schedule.time or "09:00")
var_freq = tk.StringVar(value=cfg.schedule.frequency or "Daily")

r1 = ttk.Frame(frm_sched)
r1.pack(fill="x", padx=5, pady=2)
ttk.Label(r1, text="Start date (YYYY-MM-DD):", width=22).pack(side="left")
ttk.Entry(r1, textvariable=var_date, width=15).pack(side="left", padx=5)

r2 = ttk.Frame(frm_sched)
r2.pack(fill="x", padx=5, pady=2)
ttk.Label(r2, text="Time (HH:MM, 24h):", width=22).pack(side="left")
ttk.Entry(r2, textvariable=var_time, width=10).pack(side="left", padx=5)

r3 = ttk.Frame(frm_sched)
r3.pack(fill="x", padx=5, pady=2)
ttk.Label(r3, text="Frequency:", width=22).pack(side="left")
ttk.Combobox(r3, textvariable=var_freq, values=ALLOWED_FREQ, state="readonly", width=18).pack(side="left", padx=5)

# Next run time display
var_next_run = tk.StringVar(value="Not scheduled")
r4 = ttk.Frame(frm_sched)
r4.pack(fill="x", padx=5, pady=5)
ttk.Label(r4, text="Next scheduled run:", width=22).pack(side="left")
ttk.Label(r4, textvariable=var_next_run, foreground="#0066cc").pack(side="left", padx=5)

def update_next_run_display():
    """Update the next run time display."""
    next_run = get_next_run_time(sched, "send_latest")
    if next_run:
        var_next_run.set(next_run.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        var_next_run.set("Not scheduled")

def scheduled_email_job():
    """Job that runs on schedule to email latest report."""
    try:
        logger.info("Scheduled job started")
        
        # Find latest cached report
        items = sorted(
            cache_reports_dir().glob("*.pdf"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        if not items:
            logger.warning("No reports found for scheduled email")
            return
        
        latest = items[0]
        
        # Get recipients
        to = validate_email_list(cfg.recipients)
        if not to:
            logger.warning("No valid recipients configured")
            return
        
        # Check API key
        if not cfg.api_key:
            logger.error("No API key configured")
            return
        
        # Send email
        html_body = f"""
        <html>
        <body>
            <h2>File Neglect Report</h2>
            <p>Please find the latest automated File Neglect Report attached.</p>
            <p><strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p>This is an automated email from PDF Reporter.</p>
        </body>
        </html>
        """
        
        send_with_resend(
            api_key=cfg.api_key,
            to_emails=to,
            html_body=html_body,
            attachments=[latest],
            subject=f"File Neglect Report - {datetime.now().strftime('%Y-%m-%d')}"
        )
        
        logger.info(f"Scheduled email sent successfully to {len(to)} recipient(s)")
        
    except Exception as e:
        logger.error(f"Scheduled job failed: {e}", exc_info=True)

def save_schedule():
    """Save and activate the schedule."""
    date = var_date.get().strip()
    time = var_time.get().strip()
    freq = var_freq.get().strip()
    
    if not all([date, time, freq]):
        messagebox.showwarning("Incomplete", "Please fill in all schedule fields.")
        return
    
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        messagebox.showerror("Invalid Date", "Date must be in YYYY-MM-DD format.")
        return
    
    # Validate time format
    try:
        hh, mm = time.split(":")
        if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
            raise ValueError()
    except:
        messagebox.showerror("Invalid Time", "Time must be in HH:MM format (24h).")
        return
    
    # Check prerequisites
    if not cfg.api_key:
        messagebox.showwarning(
            "API Key Required",
            "Please configure your Resend API key before enabling scheduling."
        )
        return
    
    if not cfg.recipients:
        messagebox.showwarning(
            "Recipients Required",
            "Please configure email recipients before enabling scheduling."
        )
        return
    
    # Save config
    cfg.schedule.date = date
    cfg.schedule.time = time
    cfg.schedule.frequency = freq
    
    if not save_config(cfg):
        messagebox.showerror("Error", "Failed to save schedule configuration.")
        return
    
    # Schedule the job
    if schedule_job(sched, "send_latest", scheduled_email_job, date, time, freq):
        update_next_run_display()
        messagebox.showinfo(
            "Schedule Activated",
            f"Automated reports will be sent {freq.lower()} at {time}.\n\n"
            f"Next run: {var_next_run.get()}"
        )
    else:
        messagebox.showerror("Error", "Failed to activate schedule.")

def disable_schedule():
    """Disable the scheduled job."""
    from core.scheduler import remove_job
    
    if remove_job(sched, "send_latest"):
        cfg.schedule.date = None
        cfg.schedule.time = None
        cfg.schedule.frequency = None
        save_config(cfg)
        update_next_run_display()
        messagebox.showinfo("Disabled", "Automated scheduling has been disabled.")
    else:
        messagebox.showinfo("Not Active", "No active schedule to disable.")

btn_sched_frame = ttk.Frame(frm_sched)
btn_sched_frame.pack(fill="x", padx=5, pady=(5, 8))

ttk.Button(btn_sched_frame, text="Enable Schedule", command=save_schedule).pack(side="left", padx=2)
ttk.Button(btn_sched_frame, text="Disable Schedule", command=disable_schedule).pack(side="left", padx=2)
ttk.Button(btn_sched_frame, text="Refresh Status", command=update_next_run_display).pack(side="left", padx=2)

# Test email button
ttk.Separator(frm_sched, orient="horizontal").pack(fill="x", padx=5, pady=5)

ttk.Label(frm_sched, text="Test your email configuration:").pack(anchor="w", padx=5, pady=(5, 2))

def send_test_email():
    """Send a test email."""
    if not cfg.api_key:
        messagebox.showwarning("API Key Required", "Please configure your Resend API key first.")
        return
    
    to = validate_email_list(cfg.recipients)
    if not to:
        messagebox.showwarning("Recipients Required", "Please configure valid email recipients first.")
        return
    
    try:
        html_body = """
        <html>
        <body>
            <h2>Test Email - PDF Reporter</h2>
            <p>This is a test email from your PDF Reporter application.</p>
            <p>If you received this email, your configuration is working correctly!</p>
        </body>
        </html>
        """
        
        send_with_resend(
            api_key=cfg.api_key,
            to_emails=to,
            html_body=html_body,
            attachments=[],
            subject="PDF Reporter - Test Email"
        )
        
        messagebox.showinfo(
            "Test Email Sent",
            f"Test email sent successfully to:\n" + "\n".join(to)
        )
        
    except Exception as e:
        logger.error(f"Test email failed: {e}", exc_info=True)
        messagebox.showerror("Send Failed", f"Failed to send test email:\n\n{str(e)}")

ttk.Button(frm_sched, text="Send Test Email", command=send_test_email).pack(anchor="w", padx=5, pady=(0, 8))

# === ABOUT SECTION ===
frm_about = ttk.LabelFrame(scrollable_frame, text="About")
frm_about.pack(fill="x", **pad)

about_text = """PDF Reporter v1.0

A tool for monitoring file neglect across multiple folders.
Generates detailed PDF reports and can email them automatically.

Configuration & logs are stored in:
"""

ttk.Label(frm_about, text=about_text, justify="left").pack(anchor="w", padx=5, pady=5)
ttk.Label(frm_about, text=str(appdata_dir()), foreground="#0066cc", cursor="hand2").pack(anchor="w", padx=5)

def open_appdata_folder():
    """Open the application data folder."""
    try:
        folder = appdata_dir()
        if sys.platform == 'win32':
            os.startfile(folder)
        elif sys.platform == 'darwin':
            subprocess.run(['open', str(folder)])
        else:
            subprocess.run(['xdg-open', str(folder)])
    except Exception as e:
        logger.error(f"Error opening folder: {e}", exc_info=True)

ttk.Button(frm_about, text="Open Application Folder", command=open_appdata_folder).pack(anchor="w", padx=5, pady=(0, 8))

# Initialize next run display
update_next_run_display()

# ========== MAIN LOOP ==========

def on_closing():
    """Handle window close event."""
    if is_generating:
        if not messagebox.askyesno(
            "Generation in Progress",
            "A report is currently being generated. Are you sure you want to exit?"
        ):
            return
    
    logger.info("Application closing")
    sched.shutdown(wait=False)
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)

logger.info("Application started")
root.mainloop()