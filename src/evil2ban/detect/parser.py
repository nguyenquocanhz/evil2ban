# -*- coding: utf-8 -*-
"""Doc + phan tich dong nginx access log thanh LogEntry (da khoi phuc real-IP)."""
import os
import re
import glob

from ..core.interfaces import LogSource, IpResolver
from ..core.models import LogEntry

LOG_RE = re.compile(
    r'(?P<ip>[0-9a-fA-F:.]+)\s+\S+\s+\S+\s+\[(?P<t>[^\]]+)\]\s+'
    r'"(?P<method>[A-Z]+)?\s*(?P<path>[^"\s]*)[^"]*"\s+(?P<status>\d{3})\s+'
    r'(?P<bytes>\d+|-)\s+"(?P<ref>[^"]*)"\s+"(?P<ua>[^"]*)"'
    r'(?:\s+"(?P<xff>[^"]*)")?')
CF_JSON_RE = re.compile(
    r'cf[_-]connecting[_-]ip"?\s*[:=]\s*"?([0-9a-fA-F:.]+)', re.I)


class NginxAccessLogSource(LogSource):
    """Nguon log: tail cac file *.log moi nhat trong thu muc (bo error/tcp log)."""

    def __init__(self, log_dir, max_files=16, tail_lines=4000):
        self.log_dir = log_dir
        self.max_files = max_files
        self.tail_lines = tail_lines

    def _files(self):
        files = [f for f in glob.glob(os.path.join(self.log_dir, "*.log"))
                 if "error" not in os.path.basename(f)
                 and "tcp-" not in os.path.basename(f)]
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return files[:self.max_files]

    @staticmethod
    def _tail(path, n):
        try:
            with open(path, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                block = min(size, n * 240)
                f.seek(size - block)
                return f.read().decode("utf-8", "replace").splitlines()[-n:]
        except OSError:
            return []

    def lines(self):
        for f in self._files():
            for ln in self._tail(f, self.tail_lines):
                yield ln


class LogParser:
    """Chuyen dong raw -> LogEntry, dung IpResolver de khoi phuc real-IP."""

    def __init__(self, resolver: IpResolver):
        self.resolver = resolver

    def parse(self, line: str):
        m = LOG_RE.search(line)
        if not m:
            return None
        d = m.groupdict()
        cf = ""
        jm = CF_JSON_RE.search(line)
        if jm:
            cf = jm.group(1)
        client, behind = self.resolver.resolve(
            d["ip"], cf_connecting_ip=cf, x_forwarded_for=d.get("xff") or "")
        return LogEntry(edge_ip=d["ip"], client_ip=client, behind_cdn=behind,
                        ts=d["t"], method=d.get("method") or "", path=d["path"],
                        status=d["status"], ua=d["ua"], referer=d.get("ref") or "")

    def entries(self, source: LogSource):
        for ln in source.lines():
            e = self.parse(ln)
            if e:
                yield e
