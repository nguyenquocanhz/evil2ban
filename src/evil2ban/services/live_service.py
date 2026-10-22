# -*- coding: utf-8 -*-
"""
LiveService — so lieu song cho WebUI (SSE moi 5 giay).
Chi doc gia tri da co san (RateWatcher, cache phan tich, bang samples),
khong tu quet log, nen goi lien tuc van nhe.
"""
import time
from collections import deque


class LiveService:
    def __init__(self, ratewatch, analysis, samples, settings):
        self.rate = ratewatch
        self.analysis = analysis
        self.samples = samples
        self.settings = settings
        self._suspects_hist = deque(maxlen=14)
        self._hist_min = None

    def _recent_samples(self, col, n=14):
        since = int(time.time()) - n * 60 - 60
        rows = self.samples.db.conn().execute(
            f"SELECT minute,{col} FROM samples WHERE minute>=? ORDER BY minute", (since,)).fetchall()
        return [r[1] or 0 for r in rows][-n:]

    def snapshot(self):
        r = self.rate.snapshot()
        try:
            banned = len(self.analysis.banned().banned)
        except Exception:  # noqa: BLE001
            banned = None
        try:
            suspects = len(self.analysis.traffic()["suspects"])
        except Exception:  # noqa: BLE001
            suspects = None
        minute = int(time.time() // 60)
        if suspects is not None and minute != self._hist_min:
            self._suspects_hist.append(suspects)
            self._hist_min = minute
        ssh_hist = self._recent_samples("ssh_failed")
        return {
            "ts": int(time.time()),
            "rpm": r["rpm"], "warming": r["warming"],
            "ssh_pm": ssh_hist[-1] if ssh_hist else 0,
            "banned": banned, "suspects": suspects,
            "auto_ban": self.settings.get_bool("detect.autoban", default=False),
            "rate_alert": self.settings.get_int("detect.rate_alert", default=120),
            "spark": {"req": r["history"], "ssh": ssh_hist,
                      "banned": self._recent_samples("bans"),
                      "suspects": list(self._suspects_hist)},
            "alerts": r["alerts"],
        }
