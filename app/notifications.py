from __future__ import annotations

import os
import re
import ssl
import smtplib
from email.message import EmailMessage
from typing import Iterable

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "") or f"no-reply@{SMTP_HOST or 'quotation-registry.local'}"
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() in {"1", "true", "yes", "on"}
SMTP_USE_STARTTLS = os.getenv("SMTP_USE_STARTTLS", "true").lower() in {"1", "true", "yes", "on"}


def get_admin_emails() -> list[str]:
    raw = os.getenv("ADMIN_EMAILS") or os.getenv("ADMIN_EMAIL", "")
    return [email.strip() for email in re.split(r"[;,\s]+", raw) if email.strip()]


def send_email(subject: str, body: str, recipients: Iterable[str]) -> None:
    recipients_list = [recipient for recipient in recipients if recipient]
    if not recipients_list:
        return
    if not SMTP_HOST:
        raise RuntimeError("SMTP_HOST is not configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_FROM
    message["To"] = ", ".join(recipients_list)
    message.set_content(body)

    if SMTP_USE_SSL:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=30) as server:
            if SMTP_USERNAME and SMTP_PASSWORD:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, recipients_list, message.as_string())
        return

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        if SMTP_USE_STARTTLS:
            server.starttls(context=context)
        if SMTP_USERNAME and SMTP_PASSWORD:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM, recipients_list, message.as_string())


def build_quote_reminder_subject(entry: dict[str, str]) -> str:
    return f"Quote Follow-up Reminder: {entry.get('title') or 'Quotation'}"


def build_quote_reminder_body(entry: dict[str, str]) -> str:
    return "\n".join(
        [
            "A quotation generated one week ago needs your attention.",
            "",
            f"Reference: {entry.get('ref_number') or '-'}",
            f"Title: {entry.get('title') or '-'}",
            f"Customer / Department: {entry.get('department') or entry.get('contact_person') or '-'}",
            f"Date Applied: {entry.get('date_applied') or '-'}",
            f"Deadline: {entry.get('deadline') or '-'}",
            f"Amount: {entry.get('amount') or '-'} {entry.get('currency') or ''}",
            "",
            "Please review the quotation and take any necessary action.",
        ]
    )
