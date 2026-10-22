# -*- coding: utf-8 -*-
"""Tong hop du lieu cho WebUI, co cache TTL (nhe CPU box yeu)."""
import os
import time
from datetime import datetime, timezone

from ..core.interfaces import Firewall, SshLogReader


class TTLCache:
    def __init__(self):
        self._d = {}

    def get(self, key, ttl, fn):
        now = time.time()
        hit = self._d.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
        val = fn()
        self._d[key] = (now, val)
        return val

    def drop(self, key):
        self._d.pop(key, None)


class AnalysisService:
    def __init__(self, analyzer, firewall: Firewall, ssh: SshLogReader,
                 jail, version, ttl=20):
        self.analyzer = analyzer
        self.firewall = firewall
        self.ssh = ssh
        self.jail = jail
        self.version = version
        self.ttl = ttl
        self.cache = TTLCache()

    def traffic(self):
        return self.cache.get("traffic", self.ttl, self.analyzer.analyze)

    def banned(self):
        return self.cache.get("banned", self.ttl,
                              lambda: self.firewall.status(self.jail))

    def ssh_stats(self):
        return self.cache.get("ssh", max(self.ttl, 30), self.ssh.failed_logins)

    def drop_banned(self):
        self.cache.drop("banned")

    def overview(self, auto_ban: bool):
        a = self.traffic()
        b = self.banned()
        s = self.ssh_stats()
        return {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "host": os.uname().nodename, "version": self.version,
                "banned_now": len(b.banned), "total_banned": b.total_banned,
                "ssh_failed_6h": s["total_failed"], "requests": a["requests"],
                "cdn_hidden": a["cdn_hidden"], "unique_ips": a["unique_ips"],
                "suspects": len(a["suspects"]), "auto_ban": auto_ban}
