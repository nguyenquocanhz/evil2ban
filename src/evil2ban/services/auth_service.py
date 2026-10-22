# -*- coding: utf-8 -*-
"""Nghiep vu xac thuc: dang nhap, kiem token, doi mat khau, token, phien, reset qua email."""
import json
import time
import secrets

from ..core.exceptions import AuthError, NotConfigured, InvalidInput
from ..core.interfaces import Mailer
from ..security import PasswordHasher, SecretGenerator


class AuthService:
    def __init__(self, settings, sessions, mailer: Mailer,
                 hasher: PasswordHasher = None, meta=None):
        self.settings = settings
        self.sessions = sessions
        self.mailer = mailer
        self.hasher = hasher or PasswordHasher()
        self.meta = meta

    def login(self, username, password) -> str:
        user = self.settings.get("auth.username", default="")
        phash = self.settings.get("auth.password_hash", default="")
        if not user or not phash:
            raise NotConfigured("Chưa cấu hình đăng nhập (chạy evil2ban-setup).")
        if username != user or not self.hasher.verify(password, phash):
            raise AuthError("Sai tài khoản hoặc mật khẩu.")
        return self.sessions.create(user)

    def valid_token(self, token) -> bool:
        if not token:
            return False
        access = self.settings.get("auth.token", default="")
        if access and secrets.compare_digest(token, access):
            return True
        return self.sessions.valid(token)

    # ---------- tai khoan ----------
    def record_login(self, ip, ua):
        if self.meta:
            self.meta.set("auth.last_login", json.dumps({"ts": int(time.time()), "ip": ip, "ua": ua[:200]}))

    def account(self):
        def meta_json(k):
            try:
                return json.loads(self.meta.get(k) or "null") if self.meta else None
            except ValueError:
                return None
        token = self.settings.get("auth.token", default="")
        return {"username": self.settings.get("auth.username", default=""),
                "last_login": meta_json("auth.last_login"),
                "password_changed": int(self.meta.get("auth.password_changed") or 0) if self.meta else 0,
                "token_hint": token[-4:] if token else "",
                "email": self.settings.get("mail.admin_email", default=""),
                "public_url": self.settings.get("server.public_url", default="")}

    def change_password(self, current, new):
        phash = self.settings.get("auth.password_hash", default="")
        if not self.hasher.verify(current or "", phash):
            raise AuthError("Mật khẩu hiện tại không đúng.", "bad_password")
        if len(new or "") < 12:
            raise InvalidInput("Mật khẩu mới cần ít nhất 12 ký tự.", "password_too_short")
        self.settings.set("auth.password_hash", self.hasher.hash(new))
        if self.meta:
            self.meta.set("auth.password_changed", str(int(time.time())))

    def regen_token(self) -> str:
        token = SecretGenerator.token(32)
        self.settings.set("auth.token", token)
        return token

    def access_link(self, base=""):
        token = self.settings.get("auth.token", default="")
        base = (base or self.settings.get("server.public_url", default="")).rstrip("/")
        return f"{base}/?token={token}" if token else ""

    def logout_all(self):
        self.sessions.purge_all()

    def reset_password(self, username=""):
        """Sinh mat khau moi, luu hash, gui email. Tra (ok, msg, newpw)."""
        user = self.settings.get("auth.username", default="")
        if not user:
            raise NotConfigured("Chưa cấu hình đăng nhập.")
        if username and username != user:
            raise AuthError("Tài khoản không đúng.", "wrong_user")
        newpw = SecretGenerator.password(16)
        self.settings.set("auth.password_hash", self.hasher.hash(newpw))
        if self.meta:
            self.meta.set("auth.password_changed", str(int(time.time())))
        ok, msg = self.mailer.send(
            "[Evil2Ban] Mật khẩu mới",
            f"Tài khoản: {user}\nMật khẩu mới: {newpw}\n\nĐăng nhập và đổi lại nếu cần.\n")
        return ok, msg, newpw
