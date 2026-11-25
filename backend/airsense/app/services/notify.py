"""Outbound e-mail. Uses SMTP when configured; otherwise logs (development) - never fails the request."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from airsense.app.core.config import get_settings

log = logging.getLogger("airsense.notify")


def send_email(to: str, subject: str, body: str) -> bool:
    s = get_settings()
    if not s.smtp_host:
        log.warning("SMTP not configured; e-mail to %s not sent (subject=%r)", to, subject)
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.smtp_from, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password or "")
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError):
        log.exception("failed to send e-mail")
        return False
