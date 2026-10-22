# -*- coding: utf-8 -*-
"""GeoLocator — tra ma quoc gia (ipinfo.io, resolver nen) hoac Null."""
import time
import queue
import ipaddress
import threading
import urllib.request

from ..core.interfaces import GeoLocator


class NullGeoLocator(GeoLocator):
    def country(self, ip) -> str:
        return ""


class IpinfoGeoLocator(GeoLocator):
    """Resolver nen: tra cache ngay, chua co thi day vao hang doi (nhe box yeu)."""

    def __init__(self):
        self._cache = {}
        self._seen = set()
        self._q = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()

    @staticmethod
    def _is_public(ip):
        try:
            a = ipaddress.ip_address(ip)
            return not (a.is_private or a.is_loopback or a.is_link_local)
        except ValueError:
            return False

    def country(self, ip) -> str:
        if not self._is_public(ip):
            return ""
        if ip in self._cache:
            return self._cache[ip]
        if ip not in self._seen:
            self._seen.add(ip)
            self._q.put(ip)
        return ""

    def _worker(self):
        while True:
            ip = self._q.get()
            try:
                req = urllib.request.Request(
                    f"https://ipinfo.io/{ip}/country",
                    headers={"User-Agent": "evil2ban"})
                self._cache[ip] = urllib.request.urlopen(
                    req, timeout=2).read().decode().strip()[:3]
            except Exception:  # noqa: BLE001
                self._cache[ip] = ""
            time.sleep(0.25)
