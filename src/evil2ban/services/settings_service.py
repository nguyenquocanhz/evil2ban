# -*- coding: utf-8 -*-
"""
SettingsService — doc/ghi cau hinh tu WebUI an toan: chi cac khoa trong SCHEMA,
kiem kieu + mien gia tri, che gia tri bi mat, dong bo notify.conf khi doi kenh.
"""
import os
import ipaddress

from ..core.exceptions import InvalidInput

# khoa -> (kieu, bi_mat, can_khoi_dong_lai)
SCHEMA = {
    "detect.autoban": ("bool", False, False),
    "detect.autoban_404": ("int:1:100000", False, False),
    "detect.rate_alert": ("int:10:100000", False, False),
    "detect.jail": ("name", False, True),
    "detect.log_dir": ("dir", False, True),
    "detect.tail_lines": ("int:500:50000", False, True),
    "detect.geoip": ("bool", False, True),
    "web.block": ("bool", False, False),
    "notify.telegram_on": ("bool", False, False),
    "notify.slack_on": ("bool", False, False),
    "notify.discord_on": ("bool", False, False),
    "notify.telegram_bot_token": ("str", True, False),
    "notify.telegram_admin_id": ("str", False, False),
    "notify.slack_webhook": ("url", True, False),
    "notify.discord_webhook": ("url", True, False),
    "notify.on_ban": ("bool", False, False),
    "notify.on_rate": ("bool", False, False),
    "notify.on_login_fail": ("bool", False, False),
    "notify.on_settings": ("bool", False, False),
    "mail.smtp_host": ("str", False, False),
    "mail.smtp_port": ("int:1:65535", False, False),
    "mail.smtp_user": ("str", False, False),
    "mail.smtp_pass": ("str", True, False),
    "mail.admin_email": ("email", False, False),
    "server.public_url": ("url", False, False),
    "server.host": ("ip", False, True),
    "server.port": ("int:1:65535", False, True),
}


class SettingsService:
    def __init__(self, settings, notifier, events):
        self.settings = settings
        self.notifier = notifier
        self.events = events

    def public(self):
        out = {}
        for k, (_, secret, restart) in SCHEMA.items():
            v = self.settings.get(k, default="")
            out[k] = {"value": "" if secret else v, "set": bool(v), "secret": secret, "restart": restart}
        return out

    @staticmethod
    def _clean(key, kind, raw):
        v = "" if raw is None else str(raw).strip()
        if kind == "bool":
            return "1" if v.lower() in ("1", "true", "yes", "on") else "0"
        if kind.startswith("int:"):
            _, lo, hi = kind.split(":")
            try:
                n = int(v)
            except ValueError:
                raise InvalidInput(f"{key}: phải là số nguyên.", "invalid_number")
            if not int(lo) <= n <= int(hi):
                raise InvalidInput(f"{key}: phải trong khoảng {lo}–{hi}.", "out_of_range")
            return str(n)
        if kind == "url" and v and not v.startswith(("http://", "https://")):
            raise InvalidInput(f"{key}: link phải bắt đầu bằng http:// hoặc https://.", "invalid_url")
        if kind == "url":
            return v.rstrip("/") if key == "server.public_url" else v
        if kind == "email" and v and ("@" not in v or " " in v):
            raise InvalidInput(f"{key}: email không hợp lệ.", "invalid_email")
        if kind == "ip":
            try:
                ipaddress.ip_address(v)
            except ValueError:
                raise InvalidInput(f"{key}: địa chỉ IP không hợp lệ.", "invalid_ip")
        if kind == "dir" and not os.path.isdir(v):
            raise InvalidInput(f"{key}: thư mục không tồn tại.", "invalid_dir")
        if kind == "name" and (not v or not v.replace("-", "").replace("_", "").isalnum()):
            raise InvalidInput(f"{key}: tên không hợp lệ.", "invalid_name")
        return v

    def update(self, data: dict, actor_ip=""):
        if not isinstance(data, dict) or not data:
            raise InvalidInput("Không có gì để lưu.", "invalid_input")
        clean = {}
        for k, raw in data.items():
            if k not in SCHEMA:
                raise InvalidInput(f"Khoá cài đặt không được phép: {k}", "unknown_setting")
            kind, secret, _ = SCHEMA[k]
            if secret and (raw is None or str(raw) == ""):
                continue                      # o bi mat de trong = giu nguyen
            clean[k] = self._clean(k, kind, raw)
        for k, v in clean.items():
            self.settings.set(k, v)
        if any(k.startswith("notify.") for k in clean):
            self.notifier.sync_conf()
        restart = any(SCHEMA[k][2] for k in clean)
        if clean:
            self.events.add("settings", "", detail=", ".join(sorted(clean)), actor_ip=actor_ip)
            self.notifier.notify("settings", "⚙️ Đổi cài đặt Evil2Ban",
                                 [f"Khoá: {', '.join(sorted(clean))}", f"Từ IP: {actor_ip or '?'}"])
        return {"saved": sorted(clean), "restart": restart}
