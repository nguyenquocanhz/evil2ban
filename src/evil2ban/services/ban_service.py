# -*- coding: utf-8 -*-
"""Nghiep vu chan/go chan — phoi hop Firewall + Notifier + EventRepository."""
from ..core.exceptions import BanRejected
from ..core.interfaces import Firewall, Notifier, IpResolver
from ..detect.detector import is_public


class BanGuard:
    """Lop bao ve: khong bao gio chan IP noi bo / Cloudflare / whitelist."""

    def __init__(self, resolver: IpResolver, is_whitelisted):
        self.resolver = resolver
        self.is_whitelisted = is_whitelisted

    def check(self, ip):
        if not is_public(ip):
            raise BanRejected("IP khong hop le hoac noi bo.")
        if self.resolver.is_cdn(ip):
            raise BanRejected("IP thuoc dai Cloudflare — tu choi (tranh sap site).")
        if self.is_whitelisted(ip):
            raise BanRejected("IP nam trong whitelist — tu choi ban.")


class AutoBanPolicy:
    """Quyet dinh auto-ban tu mot suspect (Single Responsibility)."""

    def __init__(self, c404_threshold=40):
        self.c404_threshold = c404_threshold

    def should_ban(self, suspect: dict) -> bool:
        return (suspect.get("scanner_ua")
                or suspect.get("sensitive", 0) >= 3
                or suspect.get("c404", 0) >= self.c404_threshold)


class BanService:
    def __init__(self, firewall: Firewall, notifier: Notifier, events,
                 guard: BanGuard, jail: str):
        self.firewall = firewall
        self.notifier = notifier
        self.events = events
        self.guard = guard
        self.jail = jail

    def ban(self, ip, reason="manual"):
        self.guard.check(ip)                       # co the raise BanRejected
        out = self.firewall.ban(self.jail, ip)
        ok = "error" not in out.lower()
        if ok:
            self.notifier.send("ban", self.jail, ip, reason)
            self.events.add("ban", ip, jail=self.jail, reason=reason, detail=out.strip())
        return ok, out.strip()

    def unban(self, ip):
        out = self.firewall.unban(self.jail, ip)
        self.events.add("unban", ip, jail=self.jail, detail=out.strip())
        return "error" not in out.lower(), out.strip()

    def ban_many(self, ips, reason="manual"):
        results = []
        for ip in ips:
            try:
                ok, out = self.ban(ip, reason)
                results.append({"ip": ip, "ok": ok, "result": out})
            except BanRejected as e:
                results.append({"ip": ip, "ok": False, "result": str(e)})
        return results

    def unban_many(self, ips):
        return [dict(ip=ip, ok=(r := self.unban(ip))[0], result=r[1]) for ip in ips]

    def status(self):
        return self.firewall.status(self.jail)
