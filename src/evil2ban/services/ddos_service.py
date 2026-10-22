# -*- coding: utf-8 -*-
"""
DdosService — so lieu song (moi 5 giay), phat hien dot flood, canh bao IP bi tu chan,
va doi lop bao ve qua DdosShield kem nhat ky audit.
"""
import time
import threading
from collections import deque

from ..detect.cloudflare import is_cloudflare
from ..infra import ddos as D

TICK = 5
HISTORY = 30                       # 30 diem x 5 giay = 2,5 phut cho do thi nho


class DdosService:
    def __init__(self, shield, settings, events, notifier, whitelisted):
        self.shield, self.settings, self.events, self.notifier = shield, settings, events, notifier
        self.whitelisted = whitelisted
        self._hist = {k: deque(maxlen=HISTORY) for k in ("syn", "est", "ct", "pps")}
        self._snap = None
        self._last_pk = None
        self._attack = None            # dot flood dang dien ra
        self._seen_flood = set()
        self._lock = threading.Lock()

    # ---------- lay mau ----------
    def sample(self):
        now = time.time()
        syn, est, per = D.read_tcp()
        ct, ct_max = D.read_conntrack()
        pk = D.read_packets()
        pps = 0
        if self._last_pk:
            dt = max(1e-3, now - self._last_pk[0])
            pps = max(0, round((pk - self._last_pk[1]) / dt))
        self._last_pk = (now, pk)
        for k, v in (("syn", syn), ("est", est), ("ct", ct), ("pps", pps)):
            self._hist[k].append(v)
        top = sorted(per.items(), key=lambda x: -x[1][0])[:8]
        snap = {
            "ts": int(now), "syn_recv": syn, "established": est, "ips": len(per),
            "conntrack": ct, "conntrack_max": ct_max, "pps": pps,
            "spark": {k: list(v) for k, v in self._hist.items()},
            "top": [{"ip": ip, "n": n, "port": port, "cf": is_cloudflare(ip),
                     "wl": self.whitelisted(ip)} for ip, (n, port) in top],
        }
        self._detect(snap)
        snap["attack"] = self._attack and {k: v for k, v in self._attack.items() if k != "quiet"}
        with self._lock:
            self._snap = snap
        return snap

    def _detect(self, s):
        syn_th = self.settings.get_int("ddos.alert_synrecv", default=200)
        pps_th = self.settings.get_int("ddos.alert_pps", default=5000)
        kind = "syn" if s["syn_recv"] >= syn_th else ("udp" if s["pps"] >= pps_th else None)
        a = self._attack
        if kind and not a:
            self._attack = a = {"kind": kind, "since": s["ts"], "peak": 0, "ips": 0, "quiet": 0}
            self.notifier.notify("ddos", "🌊 Máy chủ đang bị flood",
                                 [f"Kiểu: {self._kind_vi(kind)}",
                                  f"Kết nối dở dang: {s['syn_recv']}", f"Gói UDP + ICMP/giây: {s['pps']}"])
        if a:
            val = s["syn_recv"] if a["kind"] == "syn" else s["pps"]
            if val > a["peak"]:
                a["peak"], a["ips"] = val, s["ips"]
            th = syn_th if a["kind"] == "syn" else pps_th
            a["quiet"] = a["quiet"] + 1 if val < th / 2 else 0
            if a["quiet"] >= 6:                 # 30 giay yen -> dong dot flood
                unit = "kết nối dở dang" if a["kind"] == "syn" else "gói/giây"
                self.events.add("ddos-flood", "", reason=a["kind"],
                                detail=f"{self._kind_vi(a['kind'])} · đỉnh {a['peak']} {unit} · {a['ips']} IP · "
                                       f"{max(1, round((s['ts'] - a['since']) / 60))} phút")
                self._attack = None

    @staticmethod
    def _kind_vi(k):
        return {"syn": "SYN Flood", "udp": "UDP/ICMP Flood"}.get(k, k)

    def _check_floodset(self):
        ips = set(D.flood_ips())
        new = ips - self._seen_flood
        self._seen_flood = ips
        if new:
            sample = ", ".join(sorted(new)[:5])
            self.events.add("ddos-block", sample if len(new) == 1 else "", reason="auto",
                            detail=f"tự chặn {len(new)} IP vượt ngưỡng trong 1 giờ: {sample}")
            self.notifier.notify("ddos", "🛡️ Tự chặn IP flood",
                                 [f"{len(new)} IP vượt ngưỡng, chặn 1 giờ", sample])

    def run_forever(self):
        try:
            self.shield.restore_on_boot()
        except Exception:  # noqa: BLE001
            pass
        self._seen_flood = set(D.flood_ips())
        n = 0
        while True:
            try:
                self.sample()
                r = self.shield.take_reverted()
                if r:
                    self.events.add("ddos-revert", "", reason=r.get("by", "timer"),
                                    detail="tự hoàn tác sau 60 giây" if r.get("by") == "timer" else "hoàn tác",
                                    result="fail" if r.get("errors") else "ok")
                if n % 3 == 0:
                    self._check_floodset()
                if n % 12 == 0:
                    self.shield.sync_allow()
            except Exception:  # noqa: BLE001
                pass
            n += 1
            time.sleep(TICK)

    # ---------- doc ----------
    def snapshot(self):
        with self._lock:
            s = self._snap
        if not s:
            s = self.sample()
        cfg, th = self.shield.current()
        return {**s, "layers": D.layer_status(th), "cfg": cfg, "th": th,
                "pending": self.shield.pending(), "origin": self.shield.origin_check(),
                "blocked": len(self._seen_flood),
                "events": [e for e in self.events.query("ddos", 30, "", 40, 0)[0]
                           if e["type"] in ("ddos-flood", "ddos-block")][:5]}

    # ---------- doi ----------
    def apply(self, cfg, th, actor_ip=""):
        cur_cfg, cur_th = self.shield.current()
        changes, errs = self.shield.apply({**cur_cfg, **(cfg or {})}, {**cur_th, **(th or {})})
        if changes:
            self.events.add("ddos-apply", "", detail=", ".join(changes) + (" · lỗi: " + "; ".join(errs) if errs else ""),
                            actor_ip=actor_ip, result="fail" if errs else "ok")
        return changes, errs

    def recommended(self, actor_ip=""):
        oc = self.shield.origin_check(fresh=True)
        cfg = {k: True for k in D.LAYERS}
        if not oc["ok"]:
            cfg["origin"] = False             # con ten mien tro thang -> bat 4 lop con lai
        return self.apply(cfg, {k: v[0] for k, v in D.THRESHOLDS.items()}, actor_ip)

    def confirm(self, actor_ip=""):
        ch = self.shield.confirm()
        if ch:
            self.events.add("ddos-confirm", "", detail=", ".join(ch), actor_ip=actor_ip)
        return ch

    def revert(self, actor_ip=""):
        ok = self.shield.revert()
        if ok:
            self.shield.take_reverted()
            self.events.add("ddos-revert", "", reason="user", detail="hoàn tác ngay", actor_ip=actor_ip)
        return ok
