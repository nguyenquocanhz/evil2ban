# -*- coding: utf-8 -*-
"""
Installer / first-run wizard.
Sinh username(5)/password(>=12)/token, hoi Gmail App Password + Telegram
(co xac nhan y/n), luu vao SQLite (file 600), dong bo Telegram sang notify.conf,
in link WebUI kem token.

  evil2ban-setup                 wizard day du
  evil2ban-setup --print         chi in link + token
  evil2ban-setup --non-interactive   chi sinh creds (dung trong postinst)
  evil2ban-setup --reset-creds   sinh lai tai khoan
"""
import os
import sys
import getpass

from ..paths import db_path
from ..data.database import Database
from ..data.repositories import SettingsRepository, WhitelistRepository
from ..detect.cloudflare import CLOUDFLARE_CIDRS
from ..security import PasswordHasher, SecretGenerator

BANNER = r"""
  ___       _ _ ___  ___
 | __|_ __ (_) |_  )| _ ) __ _ _ _
 | _|\ V / | | |/ / | _ \/ _` | ' \
 |___|\_/  |_|_/___||___/\__,_|_||_|   phat hien & chan brute-force
"""


def ask_secret(label, current=""):
    while True:
        cur = " (hien tai: da dat)" if current else " (hien tai: trong)"
        val = getpass.getpass(f"  {label}{cur} [Enter=giu nguyen]: ").strip()
        if not val:
            return current
        masked = val[:3] + "…" + val[-2:] if len(val) > 6 else "•" * len(val)
        if input(f"    Xac nhan '{masked}'? [y/N]: ").strip().lower() == "y":
            return val


def ask_plain(label, current=""):
    return input(f"  {label} [{current or 'trong'}]: ").strip() or current


def main():
    args = sys.argv[1:]
    db = Database(db_path())
    s = SettingsRepository(db)
    wl = WhitelistRepository(db)
    s.seed_defaults()
    wl.seed(CLOUDFLARE_CIDRS)
    hasher = PasswordHasher()
    host = s.get("server.host", default="127.0.0.1")
    port = s.get_int("server.port", default=8793)

    if "--print" in args:
        _print_link(s, host, port)
        return

    print(BANNER)
    print(f"  DB: {db_path()}")

    user = s.get("auth.username", default="")
    regen = not user or "--reset-creds" in args
    if user and "--reset-creds" not in args and "--non-interactive" not in args:
        regen = input(f"  Da co tai khoan '{user}'. Sinh lai moi? [y/N]: ").strip().lower() == "y"

    if regen:
        user = SecretGenerator.username(5)
        pw = SecretGenerator.password(16)
        token = SecretGenerator.token(32)
        s.set("auth.username", user)
        s.set("auth.password_hash", hasher.hash(pw))
        s.set("auth.token", token)
        print("\n  === TAI KHOAN WEBUI (luu lai ngay) ===")
        print(f"    Tai khoan : {user}")
        print(f"    Mat khau  : {pw}")
        print(f"    Token     : {token}")
    else:
        print(f"  Giu tai khoan hien tai: {user}")

    if "--non-interactive" not in args:
        print("\n  --- Email reset mat khau (Gmail App Password) ---")
        print("  Tao tai: https://myaccount.google.com/apppasswords")
        gmail_user = ask_plain("Gmail address", s.get("mail.smtp_user", default=""))
        gmail_pass = ask_secret("Gmail App Password", s.get("mail.smtp_pass", default=""))
        admin_email = ask_plain("Email nhan reset",
                                s.get("mail.admin_email", default="") or gmail_user)
        s.set("mail.smtp_user", gmail_user)
        s.set("mail.smtp_pass", gmail_pass)
        s.set("mail.admin_email", admin_email)

        print("\n  --- Thong bao Telegram (tuy chon) ---")
        bot = ask_secret("Telegram Bot TOKEN", s.get("notify.telegram_bot_token", default=""))
        admin_id = ask_plain("Telegram ADMIN_ID (chat_id)",
                             s.get("notify.telegram_admin_id", default=""))
        s.set("notify.telegram_bot_token", bot)
        s.set("notify.telegram_admin_id", admin_id)
        _sync_notify_conf(s, bot, admin_id)

        print("\n  --- Whitelist IP cua ban (khong bao gio bi chan) ---")
        print("  Nhap tung IP/CIDR, de trong de ket thuc.")
        while True:
            e = input("    + IP/CIDR: ").strip()
            if not e:
                break
            try:
                wl.add(e, source="owner", note="setup")
                print(f"      da them {e}")
            except ValueError:
                print("      (bo qua — IP/CIDR khong hop le)")

    _print_link(s, host, port)


def _sync_notify_conf(settings, bot, admin_id):
    conf = settings.get("notify.conf", default="/etc/fail2ban/notify.conf")
    if not bot and not admin_id:
        return
    try:
        lines = []
        if os.path.exists(conf):
            with open(conf, encoding="utf-8") as f:
                lines = f.read().splitlines()

        def upsert(key, val):
            found = False
            for i, ln in enumerate(lines):
                if ln.strip().startswith(key + "="):
                    lines[i] = f"{key}={val}"
                    found = True
            if not found:
                lines.append(f"{key}={val}")

        if bot:
            upsert("TELEGRAM_BOT_TOKEN", bot)
        if admin_id:
            upsert("TELEGRAM_CHAT_ID", admin_id)
        os.makedirs(os.path.dirname(conf), exist_ok=True)
        with open(conf, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        os.chmod(conf, 0o600)
        print(f"    Da dong bo Telegram sang {conf}")
    except OSError as e:
        print(f"    (khong ghi duoc {conf}: {e})")


def _print_link(settings, host, port):
    token = settings.get("auth.token", default="")
    print("\n  === TRUY CAP WEBUI ===")
    print(f"  Dashboard bind {host}:{port} (chi localhost).")
    print("  Mo SSH tunnel tu may ban:")
    print(f"     ssh -N -L {port}:127.0.0.1:{port} <user>@<server-ip>")
    print("  Roi mo trinh duyet:")
    print(f"     http://127.0.0.1:{port}/?token={token}" if token
          else f"     http://127.0.0.1:{port}/")
    print()


if __name__ == "__main__":
    main()
