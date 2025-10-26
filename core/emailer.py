# core/emailer.py
import resend
from pathlib import Path
from typing import List
from .logger import logger

DEFAULT_FROM_EMAIL = "onboarding@resend.dev"
DEFAULT_SUBJECT = "File Neglect Report"

class EmailError(Exception):
    """Raised when email sending fails."""
    pass

def send_with_resend(
    api_key: str,
    to_emails: List[str],
    html_body: str,
    attachments: List[Path],
    subject: str = DEFAULT_SUBJECT,
    from_email: str = DEFAULT_FROM_EMAIL
) -> None:
    """
    Send an email through Resend with optional attachments.
    
    Args:
        api_key: Resend API key
        to_emails: List of recipient email addresses
        html_body: HTML content of the email
        attachments: List of file paths to attach
        subject: Email subject
        from_email: Sender email (must be verified in Resend)
    
    Raises:
        EmailError: If sending fails
    """
    # Validate inputs
    clean_to = [e.strip() for e in to_emails if e.strip()]
    if not clean_to:
        raise EmailError("Recipient list is empty.")
    
    if not api_key or api_key.strip() == "":
        raise EmailError("API key is not configured.")
    
    # Set API key
    resend.api_key = api_key.strip()
    
    # Prepare attachments
    attach_objs = []
    for path in attachments:
        p = Path(path)
        if not p.exists():
            raise EmailError(f"Attachment not found: {p}")
        
        try:
            # Read file content
            content = p.read_bytes()
            attach_objs.append({
                "filename": p.name,
                "content": list(content)  # Resend expects list of bytes
            })
        except Exception as e:
            raise EmailError(f"Cannot read attachment {p}: {e}")
    
    # Prepare email payload
    email_data = {
        "from": from_email,
        "to": clean_to,
        "subject": subject,
        "html": html_body,
    }
    
    if attach_objs:
        email_data["attachments"] = attach_objs
    
    # Send email
    try:
        logger.info(f"Sending email to {len(clean_to)} recipient(s)")
        response = resend.Emails.send(email_data)
        logger.info(f"Email sent successfully: {response}")
        
    except Exception as e:
        error_msg = f"Resend send failed: {e}"
        logger.error(error_msg, exc_info=True)
        raise EmailError(error_msg)

def test_api_key(api_key: str) -> bool:
    """
    Test if the API key is valid by attempting to set it.
    
    Args:
        api_key: Resend API key to test
    
    Returns:
        True if key appears valid, False otherwise
    """
    if not api_key or len(api_key.strip()) < 10:
        return False
    
    try:
        resend.api_key = api_key.strip()
        return True
    except Exception as e:
        logger.error(f"API key test failed: {e}")
        return False