# -*- coding: utf-8 -*-
"""
DomainService (DomainGate) — so lieu va cong chan theo TUNG TEN MIEN.
Moi site co mot file access log rieng trong /www/wwwlogs; dich vu tach request,
loi 404, IP nghi van theo site, va moi site co che do cong:
  tat       — khong ap cong cho site nay
  giam-sat  — chi hien so lieu (mac dinh)
  chan      — tu chan IP nghi van cua site theo nguong 404 rieng
Cache 60 giay de nhe CPU box yeu.
"""
import json
import time
import threading

from ..core.exceptions import InvalidInput, BanRejected
from ..core.models import IpStats
from ..detect.detector import is_public

MODES = ("tat", "giam-sat", "chan")


class DomainService:
    def __init__(self, source, parser, detector, resolver, is_whitelisted,
                 settings, events, ttl=60, tail=2000):
        self.source = source
        self.parser = parser
        self.detector = detector
        self.resolver = resolver
        self.is_whitelisted = is_whitelisted
        self.settings = settings
        self.events = events
        self.ttl = ttl
        self.tail = tail
        self._cache = (0, None)
        self._lock = threading.Lock()
        self._lines = {}   # path -> (size, so dong): dem dan theo phan moi, khong doc lai ca file

    # ---------- cau hinh cong ----------
    def _json(self, key):
        try:
            v = json.loads(self.settings.get(key, default="{}") or "{}")
            return v if isinstance(v, dict) else {}
        except ValueError:
            return {}

    def modes(self):
        return self._json("gate.modes")

    def thresholds(self):
        return self._json("gate.thresholds")

    def set_mode(self, domain, mode, actor_ip=""):
        if mode not in MODES:
            raise InvalidInput("Chế độ cổng không hợp lệ.", "invalid_mode")
        if domain not in {d["domain"] for d in self.stats()}:
            raise InvalidInput("Không có tên miền này trong log.", "unknown_domain")
        m = self.modes()
        m[domain] = mode
        self.settings.set("gate.modes", json.dumps(m))
        self.events.add("gate-mode", "", detail=f"{domain}: {mode}", actor_ip=actor_ip)
        return mode

    def set_threshold(self, domain, value, actor_ip=""):
        try:
            n = int(value)
        except (TypeError, ValueError):
            raise InvalidInput("Ngưỡng phải là số nguyên.", "invalid_number")
        if not 1 <= n <= 100000:
            raise InvalidInput("Ngưỡng phải trong khoảng 1–100000.", "out_of_range")
        t = self.thresholds()
        t[domain] = n
        self.settings.set("gate.thresholds", json.dumps(t))
        self.events.add("gate-mode", "", detail=f"{domain}: ngưỡng 404 = {n}", actor_ip=actor_ip)
        return n

    # ---------- so lieu ----------
    def _count_lines(self, path):
        import os
        try:
            size = os.path.getsize(path)
        except OSError:
            return 0
        old_size, n = self._lines.get(path, (0, 0))
        if size < old_size:                 # logrotate: dem lai tu dau
            old_size, n = 0, 0
        if size > old_size:
            with open(path, "rb") as f:
                f.seek(old_size)
                while True:
                    chunk = f.read(1 << 20)
                    if not chunk:
                        break
                    n += chunk.count(b"\n")
        self._lines[path] = (size, n)
        return n

    def _compute(self):
        per = {}
        for domain, ln in self.source.lines_by_file(self.tail):
            d = per.setdefault(domain, {"requests": 0, "c404": 0, "ips": {}})
            d["requests"] += 1
            e = self.parser.parse(ln)
            if not e:
                continue
            if e.status == "404":
                d["c404"] += 1
            if not e.client_ip:
                continue
            st = d["ips"].get(e.client_ip)
            if st is None:
                st = d["ips"][e.client_ip] = IpStats(ip=e.client_ip)
            st.total += 1
            st.ua[e.ua] += 1
            self.detector.accumulate(st, e)
        totals = {self.source.domain_of(p): self._count_lines(p) for p in self.source.files_all()}
        out = []
        for domain, d in per.items():
            sus = []
            for ip, st in d["ips"].items():
                if (not is_public(ip) or self.resolver.is_cdn(ip) or self.is_whitelisted(ip)
                        or not self.detector.is_suspect(st)):
                    continue
                sus.append(self.detector.to_suspect(st).as_dict())
            sus.sort(key=lambda s: -s["score"])
            out.append({"domain": domain, "requests": totals.get(domain, d["requests"]),
                        "sample": d["requests"], "c404": d["c404"],
                        "suspects": len(sus), "top": sus[:10]})
        out.sort(key=lambda x: -x["requests"])
        return out

    def stats(self):
        with self._lock:
            ts, val = self._cache
            if val is None or time.time() - ts > self.ttl:
                val = self._compute()
                self._cache = (time.time(), val)
            return val

    def list(self):
        modes, th = self.modes(), self.thresholds()
        default_th = self.settings.get_int("detect.autoban_404", default=40)
        return [{**{k: v for k, v in d.items() if k != "top"},
                 "mode": modes.get(d["domain"], "giam-sat"),
                 "threshold": int(th.get(d["domain"], default_th))} for d in self.stats()]

    def detail(self, domain):
        for d in self.stats():
            if d["domain"] == domain:
                item = next(x for x in self.list() if x["domain"] == domain)
                return {**item, "top": d["top"]}
        raise InvalidInput("Không có tên miền này trong log.", "unknown_domain")

    # ---------- thuc thi cong (goi tu vong nen moi phut) ----------
    def enforce(self, ban_service, already_banned):
        modes, th = self.modes(), self.thresholds()
        default_th = self.settings.get_int("detect.autoban_404", default=40)
        banned = set(already_banned)
        n = 0
        for d in self.stats():
            if modes.get(d["domain"]) != "chan":
                continue
            limit = int(th.get(d["domain"], default_th))
            for s in d["top"]:
                if s["ip"] in banned:
                    continue
                if s["scanner_ua"] or s["sensitive"] >= 3 or s["c404"] >= limit:
                    try:
                        ok, _ = ban_service.ban(s["ip"], reason=f"gate:{d['domain']}")
                        if ok:
                            banned.add(s["ip"])
                            n += 1
                    except BanRejected:
                        pass
        return n
