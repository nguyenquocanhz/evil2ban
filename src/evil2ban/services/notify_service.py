# -*- coding: utf-8 -*-
"""
ChannelNotifier — gui canh bao toi Telegram / Slack / Discord (webhook).
Doc cau hinh tu SQLite MOI LAN gui (doi tren web la co hieu luc ngay) va
dong bo sang /etc/fail2ban/notify.conf de action cua fail2ban (f2b-notify.sh)
dung cung kenh. Su kien ban/unban do fail2ban tu gui qua f2b-notify.sh, nen
o day khong gui lai (tranh trung tin).
"""
import os
import json
import shlex
import socket
import threading
import urllib.request
from datetime import datetime, timezone

from ..core.interfaces import Notifier

CONF_KEYS = {  # khoa notify.conf -> (khoa SQLite, khoa bat/tat)
    "TELEGRAM_BOT_TOKEN": ("notify.telegram_bot_token", "notify.telegram_on"),
    "TELEGRAM_CHAT_ID": ("notify.telegram_admin_id", "notify.telegram_on"),
    "SLACK_WEBHOOK_URL": ("notify.slack_webhook", "notify.slack_on"),
    "DISCORD_WEBHOOK_URL": ("notify.discord_webhook", "notify.discord_on"),
}
EVENT_FLAG = {"rate": "notify.on_rate", "login_fail": "notify.on_login_fail",
              "settings": "notify.on_settings"}


def _post(url, data: bytes, ctype, timeout=6):
    req = urllib.request.Request(url, data=data, headers={"Content-Type": ctype,
                                                         "User-Agent": "evil2ban"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return 200 <= r.status < 300


class ChannelNotifier(Notifier):
    def __init__(self, settings, meta=None):
        self.settings = settings
        self.meta = meta

    # ---------- cau hinh ----------
    @property
    def conf_path(self):
        return self.settings.get("notify.conf", default="/etc/fail2ban/notify.conf")

    def _channels(self):
        s = self.settings
        out = []
        tok, chat = s.get("notify.telegram_bot_token", default=""), s.get("notify.telegram_admin_id", default="")
        if s.get_bool("notify.telegram_on", default=True) and tok and chat:
            out.append(("telegram", (tok, chat)))
        for name in ("slack", "discord"):
            url = s.get(f"notify.{name}_webhook", default="")
            if s.get_bool(f"notify.{name}_on", default=True) and url:
                out.append((name, url))
        return out

    @staticmethod
    def _send_one(kind, target, text):
        if kind == "telegram":
            tok, chat = target
            data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
            return _post(f"https://api.telegram.org/bot{tok}/sendMessage", data,
                         "application/x-www-form-urlencoded")
        key = "text" if kind == "slack" else "content"
        return _post(target, json.dumps({key: text}).encode(), "application/json")

    @staticmethod
    def _format(head, lines):
        host = socket.gethostname()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return f"[{host}] {head}\n" + "\n".join(lines) + f"\nThời gian: {now}"

    # ---------- gui ----------
    def notify(self, event, head, lines):
        """Gui nen (khong chan request) toi moi kenh dang bat, neu su kien duoc bat."""
        flag = EVENT_FLAG.get(event)
        if flag and not self.settings.get_bool(flag, default=True):
            return False
        text = self._format(head, lines)
        chans = self._channels()

        def run():
            for kind, target in chans:
                try:
                    self._send_one(kind, target, text)
                except Exception:  # noqa: BLE001
                    pass
        threading.Thread(target=run, daemon=True).start()
        return bool(chans)

    def send(self, event, jail, ip, failures="") -> bool:
        # ban/unban: fail2ban da gui qua f2b-notify.sh (action notify-chat)
        return False

    def test(self, channel):
        """Gui tin thu dong bo toi MOT kenh. Tra (ok, code)."""
        s = self.settings
        text = self._format("🧪 Tin thử từ Evil2Ban", ["Kênh thông báo đã cấu hình đúng."])
        try:
            if channel == "telegram":
                tok, chat = s.get("notify.telegram_bot_token", default=""), s.get("notify.telegram_admin_id", default="")
                if not tok or not chat:
                    return False, "channel_not_set"
                return self._send_one("telegram", (tok, chat), text), "sent"
            if channel in ("slack", "discord"):
                url = s.get(f"notify.{channel}_webhook", default="")
                if not url:
                    return False, "channel_not_set"
                return self._send_one(channel, url, text), "sent"
        except Exception:  # noqa: BLE001
            return False, "send_failed"
        return False, "invalid_input"

    # ---------- dong bo notify.conf ----------
    def import_conf(self):
        """Lan dau: chep gia tri san co trong notify.conf vao SQLite (neu SQLite dang trong)."""
        if self.meta and self.meta.get("notify_imported"):
            return
        try:
            with open(self.conf_path, encoding="utf-8") as f:
                for ln in f:
                    k, _, v = ln.strip().partition("=")
                    val = v.strip().strip("\"'")
                    if k in CONF_KEYS and val:
                        skey = CONF_KEYS[k][0]
                        if not self.settings.get(skey, default=""):
                            self.settings.set(skey, val)
        except OSError:
            pass
        if self.meta:
            self.meta.set("notify_imported", "1")

    def sync_conf(self):
        s = self.settings
        want = {}
        for k, (skey, onkey) in CONF_KEYS.items():
            want[k] = s.get(skey, default="") if s.get_bool(onkey, default=True) else ""
        want["NOTIFY_ON_BAN"] = "1" if s.get_bool("notify.on_ban", default=True) else "0"
        try:
            lines = []
            if os.path.exists(self.conf_path):
                with open(self.conf_path, encoding="utf-8") as f:
                    lines = f.read().splitlines()
            done = set()
            for i, ln in enumerate(lines):
                k = ln.strip().partition("=")[0]
                if k in want:
                    lines[i] = f"{k}={shlex.quote(want[k])}"   # notify.conf duoc `source` boi shell
                    done.add(k)
            lines += [f"{k}={shlex.quote(v)}" for k, v in want.items() if k not in done]
            os.makedirs(os.path.dirname(self.conf_path), exist_ok=True)
            with open(self.conf_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            os.chmod(self.conf_path, 0o600)
            return True
        except OSError:
            return False


import urllib.parse  # noqa: E402  (dung trong _send_one)
