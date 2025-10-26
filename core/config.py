# core/config.py
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Tuple, Optional, List
from .paths import config_path
from .logger import logger

@dataclass
class Thresholds:
    """Threshold ranges for file neglect coloring (inclusive days)."""
    red: Tuple[int, int] = (15, 20)
    amber: Tuple[int, int] = (4, 14)
    green: Tuple[int, int] = (0, 3)
    
    def validate(self) -> bool:
        """Validate that ranges don't overlap and are valid."""
        ranges = [self.red, self.amber, self.green]
        
        # Check each range is valid
        for start, end in ranges:
            if start < 0 or end < 0:
                return False
            if start > end:
                return False
            if end > 365:
                return False
        
        # Check for overlaps
        def overlaps(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
            return not (a[1] < b[0] or b[1] < a[0])
        
        if overlaps(self.red, self.amber):
            return False
        if overlaps(self.red, self.green):
            return False
        if overlaps(self.amber, self.green):
            return False
        
        return True

@dataclass
class Schedule:
    """Scheduling configuration for automated reports."""
    date: Optional[str] = None  # "YYYY-MM-DD"
    time: Optional[str] = None  # "HH:MM" 24h format
    frequency: Optional[str] = None  # "Daily", "Weekly", etc.

@dataclass
class Config:
    """Main application configuration."""
    recipients: str = ""  # comma-separated emails
    api_key: str = ""  # Resend API key
    thresholds: Thresholds = field(default_factory=Thresholds)
    schedule: Schedule = field(default_factory=Schedule)

def load_config() -> Config:
    """Load configuration from JSON file."""
    p = config_path()
    if not p.exists():
        logger.info("No config file found, using defaults")
        return Config()
    
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        
        th = data.get("thresholds", {})
        sc = data.get("schedule", {})
        
        config = Config(
            recipients=data.get("recipients", ""),
            api_key=data.get("api_key", ""),
            thresholds=Thresholds(
                red=tuple(th.get("red", (15, 20))),
                amber=tuple(th.get("amber", (4, 14))),
                green=tuple(th.get("green", (0, 3))),
            ),
            schedule=Schedule(
                date=sc.get("date"),
                time=sc.get("time"),
                frequency=sc.get("frequency"),
            )
        )
        
        logger.info("Configuration loaded successfully")
        return config
        
    except Exception as e:
        logger.error(f"Error loading config: {e}", exc_info=True)
        return Config()

def save_config(cfg: Config) -> bool:
    """Save configuration to JSON file."""
    try:
        p = config_path()
        data = asdict(cfg)
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Configuration saved successfully")
        return True
    except Exception as e:
        logger.error(f"Error saving config: {e}", exc_info=True)
        return False

def validate_email_list(emails: str) -> List[str]:
    """Parse and validate email list."""
    import re
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    valid_emails = []
    for email in emails.split(','):
        email = email.strip()
        if email and email_pattern.match(email):
            valid_emails.append(email)
    
    return valid_emails