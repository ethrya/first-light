"""
Sends the newsletter email via Gmail SMTP.

Uses only Python standard library modules (smtplib, email).
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def send_newsletter(
    subject: str,
    html_body: str,
    plain_body: str,
    recipient: str,
) -> bool:
    """Send the newsletter via Gmail SMTP.

    Returns True on success, False on failure.
    """
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"First Light <{gmail_address}>"
    msg["To"] = recipient

    # Plain text first, HTML second — email clients prefer the last part
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(gmail_address, gmail_app_password)
            server.send_message(msg)

        logger.info(f"Newsletter sent to {recipient}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Gmail authentication failed. Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD. "
            "Ensure you are using an App Password, not your regular Gmail password."
        )
        return False
    except smtplib.SMTPException as exc:
        logger.error(f"SMTP error: {exc}")
        return False
    except OSError as exc:
        logger.error(f"Network error sending email: {exc}")
        return False
