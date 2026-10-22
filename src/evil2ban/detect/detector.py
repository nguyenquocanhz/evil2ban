# -*- coding: utf-8 -*-
"""
Gom quy tac phat hien + tong hop traffic. Phu thuoc vao truu tuong
(rules, resolver, whitelist-predicate, geo) -> Dependency Inversion.
"""
import ipaddress
from collections import Counter, defaultdict
from typing import Callable, Iterable

from ..core.models import IpStats, Suspect
from ..core.interfaces import DetectionRule, LogSource, IpResolver
from .parser import LogParser
from .rules import classify_device


def is_public(ip) -> bool:
    try:
        a = ipaddress.ip_address(ip)
        return not (a.is_private or a.is_loopback or a.is_link_local)
    except (ValueError, TypeError):
        return False


class ScanDetector:
    """Cham diem IP theo tap quy tac. Mo rong = them rule, khong sua lop nay."""

    def __init__(self, rules: Iterable[DetectionRule]):
        self.rules = list(rules)

    def accumulate(self, stats: IpStats, entry):
        for rule in self.rules:
            if rule.matches(entry):
                stats.rule_hits[rule.key] += 1

    def score(self, stats: IpStats) -> int:
        return sum(r.score(stats) for r in self.rules)

    def is_suspect(self, stats: IpStats) -> bool:
        return any(r.triggered(stats) for r in self.rules)

    def to_suspect(self, stats: IpStats, country: str = "") -> Suspect:
        return Suspect(
            ip=stats.ip, score=self.score(stats), total=stats.total,
            c404=stats.rule_hits.get("c404", 0),
            scanner_ua=stats.rule_hits.get("scanner_ua", 0) > 0,
            sensitive=stats.rule_hits.get("sensitive", 0),
            ua=(stats.ua.most_common(1)[0][0][:70] if stats.ua else ""),
            country=country)


class TrafficAnalyzer:
    """Duyet log -> bao cao traffic + danh sach IP nghi van."""

    def __init__(self, parser: LogParser, source: LogSource,
                 detector: ScanDetector, resolver: IpResolver,
                 is_whitelisted: Callable[[str], bool],
                 geo: Callable[[str], str] = lambda ip: ""):
        self.parser = parser
        self.source = source
        self.detector = detector
        self.resolver = resolver
        self.is_whitelisted = is_whitelisted
        self.geo = geo

    def analyze(self) -> dict:
        per_ip = {}
        status_cls = Counter()
        ua_dev = Counter()
        ua_top = Counter()
        timeline = Counter()
        cdn_hidden = 0
        total = 0

        for e in self.parser.entries(self.source):
            total += 1
            status_cls[e.status[0] + "xx"] += 1
            ua_top[(e.ua[:60] or "-")] += 1
            ua_dev[classify_device(e.ua)] += 1
            try:
                timeline[e.ts.split(":")[1]] += 1
            except IndexError:
                pass
            if e.client_ip is None:
                cdn_hidden += 1
                continue
            st = per_ip.get(e.client_ip)
            if st is None:
                st = per_ip[e.client_ip] = IpStats(ip=e.client_ip)
            st.total += 1
            st.last = e.ts
            st.ua[e.ua] += 1
            self.detector.accumulate(st, e)

        suspects = []
        for ip, st in per_ip.items():
            if (self.is_whitelisted(ip) or self.resolver.is_cdn(ip)
                    or not is_public(ip)):
                continue
            if self.detector.is_suspect(st):
                suspects.append(self.detector.to_suspect(st, self.geo(ip)))
        suspects.sort(key=lambda s: -s.score)

        top_traffic = sorted(
            ({"ip": ip, "total": st.total, "country": self.geo(ip)}
             for ip, st in per_ip.items()
             if is_public(ip) and not self.resolver.is_cdn(ip)),
            key=lambda x: -x["total"])[:10]

        return {
            "requests": total,
            "cdn_hidden": cdn_hidden,
            "unique_ips": sum(1 for ip in per_ip
                              if is_public(ip) and not self.resolver.is_cdn(ip)),
            "status": dict(sorted(status_cls.items())),
            "devices": dict(ua_dev),
            "timeline": [{"h": h, "n": n} for h, n in sorted(timeline.items())],
            "top_ua": [{"ua": u, "n": n} for u, n in ua_top.most_common(8)],
            "top_traffic": top_traffic,
            "suspects": [s.as_dict() for s in suspects[:50]],
        }

    def entries_for_backfill(self):
        """(ts, status, is_scanner) phuc vu backfill chuoi thoi gian."""
        from .rules import SCANNER_UA
        for e in self.parser.entries(self.source):
            yield e.ts, e.status, bool(SCANNER_UA.search(e.ua))
