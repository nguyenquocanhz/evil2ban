# -*- coding: utf-8 -*-
"""Bam mat khau + sinh bi mat ngau nhien (Single Responsibility)."""
import secrets
import hashlib
import string


class PasswordHasher:
    """pbkdf2_sha256: pbkdf2$<iter>$<salt>$<hex>."""

    def __init__(self, iterations: int = 120_000):
        self.iterations = iterations

    def hash(self, password: str, salt: str = None) -> str:
        salt = salt or secrets.token_hex(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                 bytes.fromhex(salt), self.iterations)
        return f"pbkdf2${self.iterations}${salt}${dk.hex()}"

    def verify(self, password: str, stored: str) -> bool:
        try:
            scheme, iters, salt, hexd = stored.split("$")
            if scheme != "pbkdf2":
                return False
            dk = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                     bytes.fromhex(salt), int(iters))
            return secrets.compare_digest(dk.hex(), hexd)
        except (ValueError, AttributeError):
            return False


class SecretGenerator:
    """Sinh username / password / token."""
    _PW_ALPHA = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    @staticmethod
    def username(n: int = 5) -> str:
        alpha = string.ascii_lowercase + string.digits
        return "".join(secrets.choice(alpha) for _ in range(n))

    @classmethod
    def password(cls, n: int = 16) -> str:
        n = max(12, n)   # toi thieu 12 ky tu
        return "".join(secrets.choice(cls._PW_ALPHA) for _ in range(n))

    @staticmethod
    def token(n: int = 32) -> str:
        return secrets.token_urlsafe(n)
