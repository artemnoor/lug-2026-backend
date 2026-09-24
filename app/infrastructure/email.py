"""Email port with local log and SMTP implementations."""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from typing import Protocol

from ..core.config import EmailSettings
from ..core.logging import JsonLogger


class EmailSender(Protocol):
    async def send(self, recipient: str, subject: str, text: str, html: str = "") -> None: ...


class EmailService:
    def __init__(self, settings: EmailSettings, logger: JsonLogger) -> None:
        self.settings = settings
        self.logger = logger

    async def send(self, recipient: str, subject: str, text: str, html: str = "") -> None:
        self.logger.info(
            "email.send.start", recipient=recipient, subject=subject, mode=self.settings.mode
        )
        if self.settings.mode == "log":
            self.logger.info(
                "email.send.log", recipient=recipient, subject=subject, body_length=len(text)
            )
            return
        await asyncio.to_thread(self._send_smtp, recipient, subject, text, html)
        self.logger.info("email.send.success", recipient=recipient, subject=subject)

    def _send_smtp(self, recipient: str, subject: str, text: str, html: str) -> None:
        message = EmailMessage()
        message["From"] = self.settings.smtp_from
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(text)
        if html:
            message.add_alternative(html, subtype="html")
        if self.settings.smtp_ssl:
            with smtplib.SMTP_SSL(
                self.settings.smtp_host, self.settings.smtp_port, timeout=10
            ) as client:
                if self.settings.smtp_user:
                    client.login(self.settings.smtp_user, self.settings.smtp_password)
                client.send_message(message)
            return
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as client:
            if self.settings.smtp_starttls:
                client.starttls()
            if self.settings.smtp_user:
                client.login(self.settings.smtp_user, self.settings.smtp_password)
            client.send_message(message)
