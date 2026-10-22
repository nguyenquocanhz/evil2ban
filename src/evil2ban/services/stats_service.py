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
        self.samples.set(minute, requests=a["requests"],
                         errors404=e404, scanners=scanners)
        self.samples.set(minute, bans=len(self.firewall.status(self.jail).banned))
        s = self.ssh.failed_logins(since="2 minutes ago")
        if s["total_failed"]:
            self.samples.add(minute, ssh_failed=s["total_failed"])
