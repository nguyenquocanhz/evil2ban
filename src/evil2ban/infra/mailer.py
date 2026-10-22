# -*- coding: utf-8 -*-
"""SmtpMailer — gui email qua SMTP Gmail (App Password)."""
import ssl
import smtplib
from email.message import EmailMessage
from typing import Optional, Tuple

from ..core.interfaces import Mailer


class SmtpMailer(Mailer):
    def __init__(self, host, port, user, password, default_to=""):
        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password
        self.default_to = default_to or user

    def send(self, subject, body, to: Optional[str] = None) -> Tuple[bool, str]:
        to = to or self.default_to
        if not (self.user and self.password and to):
            return False, "Chưa cấu hình email (tài khoản Gmail, App Password, email nhận)."
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.user, to, subject
        msg.set_content(body)
        try:
            ctx = ssl.create_default_context()
            if self.port == 465:
                with smtplib.SMTP_SSL(self.host, self.port, timeout=15, context=ctx) as s:
                    s.login(self.user, self.password)
                    s.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=15) as s:
                    s.ehlo()
                    s.starttls(context=ctx)
                    s.login(self.user, self.password)
                    s.send_message(msg)
            return True, f"Đã gửi email tới {to}."
        except Exception as e:  # noqa: BLE001
            return False, f"Lỗi gửi email: {e}"


class SettingsMailer(Mailer):
    """Doc cau hinh SMTP tu SQLite moi lan gui: doi tren WebUI co hieu luc ngay."""

    def __init__(self, settings):
        self.settings = settings

    def send(self, subject, body, to: Optional[str] = None) -> Tuple[bool, str]:
        s = self.settings
        return SmtpMailer(s.get("mail.smtp_host", default="smtp.gmail.com"),
                          s.get_int("mail.smtp_port", default=587),
                          s.get("mail.smtp_user", default=""),
                          s.get("mail.smtp_pass", default=""),
                          s.get("mail.admin_email", default="")).send(subject, body, to)
