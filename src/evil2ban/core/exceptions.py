# -*- coding: utf-8 -*-
"""
Ngoai le nghiep vu (tang web dich sang HTTP).
Moi loi mang `code` on dinh de giao dien dich sang tieng Viet / English,
va `str(e)` la cau tieng Viet co dau (dung cho TUI va log).
"""


class Evil2BanError(Exception):
    """Goc."""
    code = "error"
    status = 400

    def __init__(self, message="", code=None):
        super().__init__(message)
        if code:
            self.code = code


class BanRejected(Evil2BanError):
    """Tu choi ban (whitelist / Cloudflare / IP noi bo)."""
    code = "ban_rejected"


class AuthError(Evil2BanError):
    """Sai tai khoan / mat khau."""
    code = "bad_credentials"
    status = 401


class NotConfigured(Evil2BanError):
    """Chua cau hinh (chua chay setup)."""
    code = "not_configured"
    status = 503


class InvalidInput(Evil2BanError):
    """Du lieu gui len khong hop le."""
    code = "invalid_input"
