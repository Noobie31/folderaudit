# PDF Reporter

A Windows desktop application for monitoring file neglect across multiple folders. Generates detailed PDF reports with color-coded neglect indicators and can automatically email reports on a schedule.

## Features

- 📁 **Multi-folder scanning** - Select multiple folders to scan recursively
- 📊 **PDF Report Generation** - Creates formatted PDF reports with ReportLab
- 🎨 **Color-coded states** - Green, Amber, Red indicators based on file age
- 📧 **Automated emails** - Schedule automatic report generation and delivery via Resend
- ⚙️ **Configurable thresholds** - Customize neglect time ranges
- 💾 **Report history** - View and manage previously generated reports
- 📝 **Detailed logging** - Track all operations in log files

## Installation & Setup

### Prerequisites

- Python 3.9 or higher (for development)
- Windows OS (primary target, but can work on Linux/Mac)

### For Development

1. Clone or download this repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the application:

```bash
python app.py
```

### Building Standalone EXE

To create a standalone executable that doesn't require Python installation:

```bash
# Install PyInstaller (included in requirements.txt)
pip install pyinstaller

# Build the EXE
pyinstaller build.spec

# The executable will be in the 'dist' folder
# dist/PDFReporter.exe
```

**Note:** The built EXE can be distributed and run on any Windows computer without requiring Python or package installation!

## Configuration

### First-Time Setup

1. **Get a Resend API Key:**
   - Sign up at https://resend.com
   - Go to API Keys section
   - Create a new API key
   - Copy the key (starts with `re_`)

2. **Configure the Application:**
   - Open the "Global Settings" tab
   - Paste your API key in the "Resend API Configuration" section
   - Add recipient email addresses (comma-separated)
   - Configure neglect time thresholds if needed

### File Neglect Thresholds

Define inclusive day ranges for color coding:
- **Green:** Recently modified files (default: 0-3 days)
- **Amber:** Moderately neglected (default: 4-14 days)
- **Red:** Highly neglected (default: 15-20 days)

Ranges must not overlap and must be between 0-365 days.

## Usage

### Generating a Report

1. Go to the "Report" tab → "Current Report" subtab
2. Click "Add Folder..." and select folders to scan
3. Click "Generate PDF Report"
4. View the preview in the table
5. The PDF will be saved to the configured output directory

### Viewing Saved Reports

1. Go to "Report" tab → "Saved Reports" subtab
2. Double-click any report to open it
3. Use buttons to refresh, open, or delete reports

### Setting Up Automated Reports

1. Go to "Global Settings" tab
2. Configure API key and recipients (if not already done)
3. In the "Automated Report Scheduling" section:
   - Set start date (YYYY-MM-DD)
   - Set time (HH:MM in 24-hour format)
   - Choose frequency (Hourly, Daily, Weekly, etc.)
4. Click "Enable Schedule"
5. The application will automatically generate and email reports

**Note:** The application must be running for scheduled reports to be sent.

### Testing Email Configuration

1. Configure API key and recipients
2. In "Global Settings" → "Automated Report Scheduling"
3. Click "Send Test Email"
4. Check your inbox to confirm receipt

## Project Structure

```
pdf_reporter/
├── app.py                      # Main application (Tkinter GUI)
├── requirements.txt            # Python dependencies
├── build.spec                  # PyInstaller build configuration
├── README.md                   # This file
│
├── core/
│   ├── paths.py               # Application paths and directories
│   ├── logger.py              # Logging configuration
│   ├── config.py              # Configuration management
│   ├── scanner.py             # Folder scanning logic
│   ├── report.py              # PDF generation (ReportLab)
│   ├── emailer.py             # Email sending (Resend)
│   └── scheduler.py           # Job scheduling (APScheduler)
│
└── templates/                  # (Legacy, not used with ReportLab)
```

## Data Storage

All application data is stored in your Windows AppData folder:

```
%APPDATA%\PDFReporter\
├── config.json                # Configuration file
├── app.log                    # Application logs
└── reports\                   # Cached PDF reports
```

You can access this folder by clicking "Open Application Folder" in the About section.

## Dependencies

Key dependencies (all included in requirements.txt):

- **Tkinter** - GUI framework (built into Python)
- **ReportLab** - PDF generation (no external dependencies!)
- **Resend** - Email API
- **APScheduler** - Job scheduling
- **pywin32** - Windows file owner information (Windows only)

## Troubleshooting

### "No module named 'win32security'"

This is normal if you're not on Windows or pywin32 isn't installed. The app will work but won't show file owner information.

### "Email sending failed"

- Check your API key is correct
- Verify recipient emails are valid
- Ensure you have internet connection
- Check Resend dashboard for any issues

### "Report generation is slow"

- Large folders with many files take time to scan
- Progress bar shows current status
- Consider excluding very large directories

### EXE doesn't run

- Make sure you're on Windows
- Try running from command prompt to see error messages
- Check Windows Defender/antivirus isn't blocking it

## Building for Distribution

### Creating a Single-File EXE

```bash
pyinstaller build.spec
```

The output will be in `dist/PDFReporter.exe` - this single file contains everything needed!

### Optional: Add an Icon

1. Create or download an `.ico` file
2. Save it as `icon.ico` in the project root
3. The build.spec already references it

### Distributing

Simply share the `PDFReporter.exe` file. Users can:
1. Download the EXE
2. Run it (no installation needed)
3. Configure their settings
4. Start generating reports

## API Key Security

**Important:** 
- Never share your config.json file
- Never commit API keys to version control
- Each user should use their own Resend account
- The API key is stored locally on each machine

## License

This project is provided as-is for personal or commercial use.

## Support

For issues or questions:
1. Check the log file at `%APPDATA%\PDFReporter\app.log`
2. Review the Resend documentation: https://resend.com/docs
3. Check ReportLab documentation: https://www.reportlab.com/docs/

## Version History

### v1.0 (Current)
- Initial release
- Multi-folder scanning
- PDF report generation with ReportLab
- Email integration with Resend
- Automated scheduling
- Configurable thresholds
- Report history management
- Standalone EXE support

---

**Made with ❤️ using Python, Tkinter, ReportLab, and Resend**