# -*- coding: utf-8 -*-
"""
Repository — moi lop phu trach MOT nhom bang (Single Responsibility,
Interface Segregation). Deu nhan Database (nha cung cap ket noi).
"""
import re
import time
import calendar
import ipaddress
import secrets
from datetime import datetime, timezone

DEFAULT_SETTINGS = {
    "server.host": "127.0.0.1",
    "server.port": "8793",
    "detect.jail": "sshd",
    "detect.log_dir": "/www/wwwlogs",
    "detect.tail_lines": "4000",
    "detect.max_files": "16",
    "detect.cache_ttl": "20",
    "detect.geoip": "1",
    "detect.autoban": "0",
    "detect.autoban_404": "40",
    "auth.username": "",
    "auth.password_hash": "",
    "auth.token": "",
    "mail.smtp_host": "smtp.gmail.com",
    "mail.smtp_port": "587",
    "mail.smtp_user": "",
    "mail.smtp_pass": "",
    "mail.admin_email": "",
    "notify.script": "/usr/local/bin/f2b-notify.sh",
    "notify.conf": "/etc/fail2ban/notify.conf",
    "notify.telegram_bot_token": "",
    "notify.telegram_admin_id": "",
}
_SECRET_HINT = ("password", "token", "smtp_pass", "secret")
ALWAYS_WL = ["127.0.0.1", "::1"]

_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
     "Nov", "Dec"], start=1)}
_TS_RE = re.compile(r"(\d{2})/(\w{3})/(\d{4}):(\d{2}):(\d{2}):(\d{2})")


def minute_epoch(dt: datetime) -> int:
    return int(dt.replace(second=0, microsecond=0,
                          tzinfo=timezone.utc).timestamp())


class SettingsRepository:
    def __init__(self, db):
        self.db = db

    def seed_defaults(self):
        with self.db.conn() as c:
            for k, v in DEFAULT_SETTINGS.items():
                c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
                          (k, v))

    def get(self, key, env=None, default=None):
        import os
        if env and os.environ.get(env) is not None:
            return os.environ[env]
        r = self.db.conn().execute(
            "SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if r is not None:
            return r["value"]
        return DEFAULT_SETTINGS.get(key, default)

    def get_int(self, key, env=None, default=0):
        try:
            return int(self.get(key, env, default))
        except (TypeError, ValueError):
            return default

    def get_bool(self, key, env=None, default=False):
        v = self.get(key, env, "1" if default else "0")
        return str(v).strip().lower() in ("1", "true", "yes", "on")

    def set(self, key, value):
        with self.db.conn() as c:
            c.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                      (key, "" if value is None else str(value)))

    def all(self, redact=True):
        rows = self.db.conn().execute("SELECT key,value FROM settings").fetchall()
        out = {}
        for r in rows:
            v = r["value"]
            if redact and any(h in r["key"] for h in _SECRET_HINT):
                v = "••••••" if v else ""
            out[r["key"]] = v
        return out


class WhitelistRepository:
    def __init__(self, db):
        self.db = db

    def seed(self, cloudflare_cidrs):
        now = int(time.time())
        with self.db.conn() as c:
            for ip in ALWAYS_WL:
                c.execute("INSERT OR IGNORE INTO whitelist"
                          "(entry,is_cidr,source,note,added_at) VALUES(?,?,?,?,?)",
                          (ip, 0, "system", "loopback", now))
            for cidr in cloudflare_cidrs:
                c.execute("INSERT OR IGNORE INTO whitelist"
                          "(entry,is_cidr,source,note,added_at) VALUES(?,?,?,?,?)",
                          (cidr, 1, "cloudflare", "Cloudflare edge", now))

    def add(self, entry, source="owner", note=""):
        entry = entry.strip()
        is_cidr = 1 if "/" in entry else 0
        if is_cidr:
            ipaddress.ip_network(entry, strict=False)  # validate -> ValueError
        else:
            ipaddress.ip_address(entry)
        with self.db.conn() as c:
            c.execute("INSERT OR REPLACE INTO whitelist"
                      "(entry,is_cidr,source,note,added_at) VALUES(?,?,?,?,?)",
                      (entry, is_cidr, source, note, int(time.time())))

    def remove(self, entry):
        with self.db.conn() as c:
            cur = c.execute(
                "DELETE FROM whitelist WHERE entry=? AND source!='system'",
                (entry.strip(),))
            return cur.rowcount

    def all(self):
        return [dict(r) for r in self.db.conn().execute(
            "SELECT entry,is_cidr,source,note,added_at FROM whitelist "
            "ORDER BY source,entry").fetchall()]

    def matches(self, ip) -> bool:
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            return False
        for r in self.db.conn().execute(
                "SELECT entry,is_cidr FROM whitelist").fetchall():
            if r["is_cidr"]:
                try:
                    net = ipaddress.ip_network(r["entry"], strict=False)
                    if a.version == net.version and a in net:
                        return True
                except ValueError:
                    continue
            elif r["entry"] == ip:
                return True
        return False


class SessionRepository:
    def __init__(self, db):
        self.db = db

    def create(self, username, ttl=12 * 3600) -> str:
        tok = secrets.token_urlsafe(32)
        with self.db.conn() as c:
            c.execute("INSERT INTO sessions(token,username,expiry) VALUES(?,?,?)",
                      (tok, username, int(time.time()) + ttl))
        return tok

    def valid(self, token) -> bool:
        if not token:
            return False
        r = self.db.conn().execute(
            "SELECT expiry FROM sessions WHERE token=?", (token,)).fetchone()
        return bool(r and r["expiry"] > time.time())

    def purge(self):
        with self.db.conn() as c:
            c.execute("DELETE FROM sessions WHERE expiry<?", (int(time.time()),))


class EventRepository:
    def __init__(self, db):
        self.db = db

    def add(self, type_, ip, jail="", reason="", detail=""):
        with self.db.conn() as c:
            c.execute("INSERT INTO events(ts,type,ip,jail,reason,detail) "
                      "VALUES(?,?,?,?,?,?)",
                      (int(time.time()), type_, ip, jail, reason, detail))

    def recent(self, limit=100):
        rows = self.db.conn().execute(
            "SELECT ts,type,ip,jail,reason,detail FROM events "
            "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


class MetaRepository:
    def __init__(self, db):
        self.db = db

    def get(self, key, default=None):
        r = self.db.conn().execute(
            "SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default

    def set(self, key, value):
        with self.db.conn() as c:
            c.execute("INSERT INTO meta(key,value) VALUES(?,?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                      (key, str(value)))


class SampleRepository:
    """Chuoi thoi gian theo phut + tong hop ngay/thang (line/bars/candles)."""
    _COLS = ("requests", "errors404", "scanners", "ssh_failed", "bans")

    def __init__(self, db):
        self.db = db

    def _write(self, minute, cols, mode):
        cols = {k: v for k, v in cols.items() if k in self._COLS}
        if not cols:
            return
        fields = ",".join(cols)
        ph = ",".join("?" for _ in cols)
        if mode == "add":
            upd = ",".join(f"{k}={k}+excluded.{k}" for k in cols)
        else:
            upd = ",".join(f"{k}=excluded.{k}" for k in cols)
        with self.db.conn() as c:
            c.execute(f"INSERT INTO samples(minute,{fields}) VALUES(?,{ph}) "
                      f"ON CONFLICT(minute) DO UPDATE SET {upd}",
                      [minute] + list(cols.values()))

    def add(self, minute, **cols):
        self._write(minute, cols, "add")

    def set(self, minute, **cols):
        self._write(minute, cols, "set")

    def _rows_since(self, since):
        return self.db.conn().execute(
            "SELECT minute,requests,errors404,scanners,ssh_failed,bans "
            "FROM samples WHERE minute>=? ORDER BY minute", (since,)).fetchall()

    def _series(self, since, group_fmt, sub_fmt, metric):
        col = metric if metric in self._COLS else "requests"
        totals, subs = {}, {}
        for row in self._rows_since(since):
            dt = datetime.fromtimestamp(row["minute"], tz=timezone.utc)
            g, s, val = dt.strftime(group_fmt), dt.strftime(sub_fmt), row[col]
            totals[g] = totals.get(g, 0) + val
            subs.setdefault(g, {})
            subs[g][s] = subs[g].get(s, 0) + val
        keys = sorted(totals)
        line = [{"t": k, "v": totals[k]} for k in keys]
        candles = []
        for k in keys:
            seq = [subs[k][s] for s in sorted(subs[k])]
            if seq:
                candles.append({"t": k, "o": seq[0], "h": max(seq),
                                "l": min(seq), "c": seq[-1]})
        return {"metric": metric, "line": line, "bars": line, "candles": candles}

    def daily(self, days=30, metric="requests"):
        return self._series(int(time.time()) - days * 86400,
                            "%Y-%m-%d", "%Y-%m-%d %H", metric)

    def monthly(self, months=12, metric="requests"):
        return self._series(int(time.time()) - months * 31 * 86400,
                            "%Y-%m", "%Y-%m-%d", metric)

    def backfill(self, rows_iter):
        buckets = {}
        for ts, status, is_scanner in rows_iter:
            m = _TS_RE.search(ts)
            if not m:
                continue
            dd, mon, yyyy, HH, MM, _ = m.groups()
            mon_i = _MONTHS.get(mon)
            if not mon_i:
                continue
            epoch = calendar.timegm((int(yyyy), mon_i, int(dd),
                                     int(HH), int(MM), 0, 0, 0, 0))
            b = buckets.setdefault(epoch, [0, 0, 0])
            b[0] += 1
            if status == "404":
                b[1] += 1
            if is_scanner:
                b[2] += 1
        for minute, (req, e404, scan) in buckets.items():
            self.add(minute, requests=req, errors404=e404, scanners=scan)
        return len(buckets)

    def prune(self, keep_days=400):
        cutoff = int(time.time()) - keep_days * 86400
        with self.db.conn() as c:
            c.execute("DELETE FROM samples WHERE minute<?", (cutoff,))
