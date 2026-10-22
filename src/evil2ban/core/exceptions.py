# -*- coding: utf-8 -*-
"""Ngoai le nghiep vu (tang web se dich sang HTTP)."""


class Evil2BanError(Exception):
    """Goc."""


class BanRejected(Evil2BanError):
    """Tu choi ban (whitelist / Cloudflare / IP noi bo)."""


class AuthError(Evil2BanError):
    """Sai tai khoan / mat khau."""


class NotConfigured(Evil2BanError):
    """Chua cau hinh (chua chay setup)."""
