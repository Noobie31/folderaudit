# core/report.py
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Tuple
import math
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from .paths import cache_reports_dir
from .logger import logger

def human_size(n: int) -> str:
    """Convert bytes to human-readable size."""
    if n == 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    f = float(n)
    while f >= 1024 and i < len(units) - 1:
        f /= 1024.0
        i += 1
    return f"{f:.2f} {units[i]}"

def neglect_days(now: datetime, modified: datetime) -> float:
    """Calculate days between now and modified time."""
    delta = now - modified
    return max(delta.total_seconds(), 0.0) / 86400.0

def color_state(days: float, red: Tuple[int, int], amber: Tuple[int, int], 
                green: Tuple[int, int]) -> str:
    """Determine color state based on neglect days."""
    d = math.floor(days)
    
    if red[0] <= d <= red[1]:
        return "red"
    if amber[0] <= d <= amber[1]:
        return "amber"
    if green[0] <= d <= green[1]:
        return "green"
    
    # Outside all ranges
    return ""

def format_neglect_time(days: float) -> str:
    """Format neglect time as 'X days HH h'."""
    whole_days = int(days)
    hours = int((days - whole_days) * 24)
    return f"{whole_days} days {hours:02d} h"

def render_pdf_reportlab(rows: List[Dict], thresholds, report_time: datetime, 
                         dest_path: Path) -> None:
    """
    Generate PDF report using ReportLab (no external dependencies).
    
    Args:
        rows: List of file data dictionaries
        thresholds: Thresholds object with red/amber/green ranges
        report_time: Time when report was generated
        dest_path: Output PDF path
    """
    try:
        logger.info(f"Generating PDF with {len(rows)} rows")
        
        # Create PDF document
        doc = SimpleDocTemplate(
            str(dest_path),
            pagesize=landscape(A4),
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=18,
        )
        
        # Container for content
        elements = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#333333'),
            spaceAfter=6,
            alignment=TA_LEFT
        )
        
        meta_style = ParagraphStyle(
            'MetaStyle',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#555555'),
            spaceAfter=12
        )
        
        # Title
        title = Paragraph("File Neglect Report", title_style)
        elements.append(title)
        
        # Generated time
        gen_time = report_time.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        meta = Paragraph(f"Generated at: {gen_time}", meta_style)
        elements.append(meta)
        elements.append(Spacer(1, 0.1 * inch))
        
        # Prepare table data
        table_data = [[
            "File path",
            "File size",
            "File contents last changed",
            "Last worked on by",
            "File name",
            "File neglect time",
            "File state"
        ]]
        
        # Process rows
        for r in rows:
            days = neglect_days(report_time, r["modified"])
            state = color_state(days, thresholds.red, thresholds.amber, thresholds.green)
            
            # Truncate long paths for better table fit
            file_path = r["file_path"]
            if len(file_path) > 50:
                file_path = "..." + file_path[-47:]
            
            table_data.append([
                file_path,
                human_size(r["file_size"]),
                r["modified"].astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                r["owner"][:30] if len(r["owner"]) > 30 else r["owner"],
                r["file_name"][:30] if len(r["file_name"]) > 30 else r["file_name"],
                format_neglect_time(days),
                state.capitalize() if state else "—"
            ])
        
        # Create table
        col_widths = [1.8*inch, 0.8*inch, 1.3*inch, 1.2*inch, 1.2*inch, 1*inch, 0.8*inch]
        
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # Table style
        table_style = TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f7f7f7')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            
            # Data cells
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fafafa')]),
            
            # Column highlights
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#e9f3ff')),  # File path - blue
            ('BACKGROUND', (2, 1), (2, -1), colors.HexColor('#fff1de')),  # Modified - orange
            
            # Padding
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ])
        
        # Add state colors
        for idx, r in enumerate(rows, start=1):
            days = neglect_days(report_time, r["modified"])
            state = color_state(days, thresholds.red, thresholds.amber, thresholds.green)
            
            if state == "red":
                table_style.add('TEXTCOLOR', (6, idx), (6, idx), colors.HexColor('#e53935'))
            elif state == "amber":
                table_style.add('TEXTCOLOR', (6, idx), (6, idx), colors.HexColor('#fb8c00'))
            elif state == "green":
                table_style.add('TEXTCOLOR', (6, idx), (6, idx), colors.HexColor('#43a047'))
        
        table.setStyle(table_style)
        elements.append(table)
        
        # Build PDF
        doc.build(elements)
        logger.info(f"PDF generated successfully: {dest_path}")
        
    except Exception as e:
        logger.error(f"Error generating PDF: {e}", exc_info=True)
        raise

def cache_copy(src: Path) -> Path:
    """Copy PDF to cache directory for 'Saved Reports' listing."""
    try:
        cache_dir = cache_reports_dir()
        
        # Create timestamped filename
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        cached = cache_dir / f"{ts}__{src.name}"
        
        cached.write_bytes(src.read_bytes())
        logger.info(f"Report cached: {cached}")
        return cached
        
    except Exception as e:
        logger.error(f"Error caching report: {e}", exc_info=True)
        raise