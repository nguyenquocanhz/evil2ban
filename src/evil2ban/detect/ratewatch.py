# -*- coding: utf-8 -*-
"""
RateWatcher — theo doi toc do request gan thoi gian thuc.
Moi `interval` giay chi doc PHAN MOI cua cac access log (nho offset tung file),
dem request trong cua so 60 giay theo IP that, va bao canh bao khi mot IP
vuot nguong (bo qua Cloudflare, whitelist, IP noi bo). Nhe cho box yeu:
khong doc lai ca file, gioi han so byte moi luot.
"""
import os
import time
import threading
from collections import Counter, deque

from .detector import is_public


class RateWatcher:
    WINDOW = 60          # giay
    COOLDOWN = 600       # khong canh bao lai cung IP trong 10 phut

    def __init__(self, source, parser, resolver, is_whitelisted, threshold_fn,
                 on_alert=None, interval=5, max_bytes=2_000_000):
        self.source = source
        self.parser = parser
        self.resolver = resolver
        self.is_whitelisted = is_whitelisted
        self.threshold_fn = threshold_fn
        self.on_alert = on_alert
        self.interval = interval
        self.max_bytes = max_bytes
        self._offsets = {}
        self._window = deque()            # (ts, so_dong, Counter ip)
        self._minutes = deque(maxlen=30)  # (phut_epoch, so request)
        self._cur_min, self._cur_cnt = None, 0
        self._alerts = deque(maxlen=30)
        self._last_alert = {}
        self._lock = threading.Lock()
        self.started = time.time()

    # ---------- doc phan moi ----------
    def _read_new(self, path):
        try:
            size = os.path.getsize(path)
        except OSError:
            return []
        pos = self._offsets.get(path)
        if pos is None:                  # lan dau thay file: bo qua lich su
            self._offsets[path] = size
            return []
        if size < pos:                   # file bi xoay vong (logrotate)
            pos = 0
        if size == pos:
            return []
        try:
            with open(path, "rb") as f:
                f.seek(pos)
                chunk = f.read(min(size - pos, self.max_bytes))
        except OSError:
            return []
        cut = chunk.rfind(b"\n")
        if cut < 0:
            return []
        self._offsets[path] = pos + cut + 1   # chi tien toi dong hoan chinh
        return chunk[:cut].decode("utf-8", "replace").splitlines()

    def tick(self):
        now = time.time()
        total, per_ip = 0, Counter()
        for path in self.source.files_all():
            for ln in self._read_new(path):
                total += 1
                e = self.parser.parse(ln)
                if e and e.client_ip:
                    per_ip[e.client_ip] += 1
        with self._lock:
            self._window.append((now, total, per_ip))
            while self._window and now - self._window[0][0] > self.WINDOW:
                self._window.popleft()
            minute = int(now // 60)
            if self._cur_min is None:
                self._cur_min = minute
            if minute != self._cur_min:
                self._minutes.append((self._cur_min * 60, self._cur_cnt))
                self._cur_min, self._cur_cnt = minute, 0
            self._cur_cnt += total
        self._check_alerts(now)

    def _check_alerts(self, now):
        threshold = max(1, int(self.threshold_fn() or 120))
        counts = Counter()
        with self._lock:
            for _, _, c in self._window:
                counts.update(c)
        for ip, n in counts.most_common(20):
            if n < threshold:
                break
            if (not is_public(ip) or self.resolver.is_cdn(ip) or self.is_whitelisted(ip)
                    or now - self._last_alert.get(ip, 0) < self.COOLDOWN):
                continue
            self._last_alert[ip] = now
            alert = {"ip": ip, "rpm": n, "threshold": threshold, "ts": int(now)}
            with self._lock:
                self._alerts.appendleft(alert)
            if self.on_alert:
                try:
                    self.on_alert(alert)
                except Exception:  # noqa: BLE001
                    pass

    # ---------- doc ket qua ----------
    def snapshot(self):
        with self._lock:
            rpm = sum(n for _, n, _ in self._window)
            history = [n for _, n in self._minutes][-14:]
            return {"rpm": rpm, "warming": time.time() - self.started < self.WINDOW,
                    "history": history, "last_minute": history[-1] if history else 0,
                    "alerts": list(self._alerts)[:10]}

    def run_forever(self):
        while True:
            try:
                self.tick()
            except Exception:  # noqa: BLE001
                pass
            time.sleep(self.interval)
