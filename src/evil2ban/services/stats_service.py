# -*- coding: utf-8 -*-
"""Lay mau chuoi thoi gian (sampler nen) + backfill tu log."""
import time
from datetime import datetime, timezone

from ..data.repositories import minute_epoch


class StatsService:
    def __init__(self, samples, meta, analyzer, firewall, ssh, jail):
        self.samples = samples
        self.meta = meta
        self.analyzer = analyzer
        self.firewall = firewall
        self.ssh = ssh
        self.jail = jail
        self.rate = None   # RateWatcher (gan tu container): so request THAT trong phut

    def backfill_once(self):
        if self.meta.get("backfilled"):
            return 0
        n = self.samples.backfill(self.analyzer.entries_for_backfill())
        self.meta.set("backfilled", str(int(time.time())))
        self.meta.set("backfill_minutes", str(n))
        return n

    def sample_once(self):
        a = self.analyzer.analyze()
        minute = minute_epoch(datetime.now(timezone.utc))
        scanners = sum(1 for s in a["suspects"] if s["scanner_ua"])
        e404 = sum(s["c404"] for s in a["suspects"])
        # truoc day ghi a["requests"] = TONG ca doan log mau (~29k) moi phut -> cong
        # theo ngay ra so ao hang trieu. Gio ghi so request that trong phut vua qua.
        per_min = self.rate.snapshot()["last_minute"] if self.rate else 0
        self.samples.set(minute, requests=per_min,
                         errors404=e404, scanners=scanners)
        self.samples.set(minute, bans=len(self.firewall.status(self.jail).banned))
        s = self.ssh.failed_logins(since="2 minutes ago")
        if s["total_failed"]:
            self.samples.add(minute, ssh_failed=s["total_failed"])
