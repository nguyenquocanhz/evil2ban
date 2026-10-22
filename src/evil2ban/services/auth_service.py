# -*- coding: utf-8 -*-
"""Nghiep vu xac thuc: dang nhap, kiem token, reset mat khau qua email."""
import secrets

from ..core.exceptions import AuthError, NotConfigured
from ..core.interfaces import Mailer
from ..security import PasswordHasher, SecretGenerator


class AuthService:
    def __init__(self, settings, sessions, mailer: Mailer,
                 hasher: PasswordHasher = None):
        self.settings = settings
        self.sessions = sessions
        self.mailer = mailer
        self.hasher = hasher or PasswordHasher()

    def login(self, username, password) -> str:
        user = self.settings.get("auth.username", default="")
        phash = self.settings.get("auth.password_hash", default="")
        if not user or not phash:
            raise NotConfigured("Chua cau hinh dang nhap (chay evil2ban-setup).")
        if username != user or not self.hasher.verify(password, phash):
            raise AuthError("Sai tai khoan hoac mat khau.")
        return self.sessions.create(user)

    def valid_token(self, token) -> bool:
        if not token:
            return False
        access = self.settings.get("auth.token", default="")
        if access and secrets.compare_digest(token, access):
            return True
        return self.sessions.valid(token)

    def reset_password(self, username=""):
        """Sinh mat khau moi, luu hash, gui email. Tra (ok, msg, newpw)."""
        user = self.settings.get("auth.username", default="")
        if not user:
            raise NotConfigured("Chua cau hinh dang nhap.")
        if username and username != user:
            raise AuthError("Tai khoan khong dung.")
        newpw = SecretGenerator.password(16)
        self.settings.set("auth.password_hash", self.hasher.hash(newpw))
        ok, msg = self.mailer.send(
            "[Evil2Ban] Mat khau moi",
            f"Tai khoan: {user}\nMat khau moi: {newpw}\n\nDang nhap va doi lai neu can.\n")
        return ok, msg, newpw
