# -*- coding: utf-8 -*-
"""
GeoLocator — tra ma quoc gia cho IP, TAI CHO (khong goi dich vu ngoai luc tra).

Truoc day dung ipinfo.io theo tung IP -> bi gioi han 429, moi IP deu trong.
Gio dung CSDL DB-IP Lite Country (CC BY 4.0, https://db-ip.com), nen thanh file
nhi phan gon: mang so bat dau dai IPv4 (uint32) + ma quoc gia 2 ky tu, gop cac
dai lien ke cung nuoc. ~1-2 MB RAM, tra bang tim nhi phan.
"""
import os
import gzip
import time
import struct
import bisect
import ipaddress
import threading
import urllib.request
from array import array
from datetime import datetime, timezone

from ..core.interfaces import GeoLocator

MAGIC = b"E2BGEO1\n"
SOURCE = "https://download.db-ip.com/free/dbip-country-lite-{ym}.csv.gz"
ATTRIBUTION = "IP Geolocation by DB-IP (db-ip.com), CC BY 4.0"


class NullGeoLocator(GeoLocator):
    def country(self, ip) -> str:
        return ""


def build_geo_db(csv_gz_path, dest):
    """CSV.gz cua DB-IP -> file nhi phan gon (chi IPv4). Doc tung dong, nhe RAM."""
    starts, ccs = array("I"), bytearray()
    last_end, last_cc = -1, b""
    with gzip.open(csv_gz_path, "rt", encoding="ascii", errors="replace") as f:
        for ln in f:
            a, _, rest = ln.partition(",")
            if ":" in a:
                continue                                  # bo IPv6
            b, _, cc = rest.strip().partition(",")
            try:
                s, e = int(ipaddress.IPv4Address(a)), int(ipaddress.IPv4Address(b))
            except ValueError:
                continue
            code = (cc.strip().strip('"').upper() or "ZZ")[:2].encode("ascii", "replace")
            if s > last_end + 1:                          # khoang trong -> danh dau khong ro
                starts.append(last_end + 1); ccs += b"--"; last_cc = b"--"
            if code == last_cc:                           # gop dai lien ke cung nuoc
                last_end = e
                continue
            starts.append(s); ccs += code; last_cc, last_end = code, e
    tmp = dest + ".tmp"
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(tmp, "wb") as out:
        out.write(MAGIC + struct.pack("<I", len(starts)))
        out.write(starts.tobytes())
        out.write(bytes(ccs))
    os.replace(tmp, dest)
    return len(starts)


def update_geo_db(dest):
    """Tai ban thang nay (lui 1 thang neu chua co), dung lai file. Tra so dai hoac 0."""
    now = datetime.now(timezone.utc)
    months = [now.strftime("%Y-%m"),
              (now.replace(day=1) - __import__("datetime").timedelta(days=1)).strftime("%Y-%m")]
    tmp = dest + ".download.gz"
    for ym in months:
        try:
            req = urllib.request.Request(SOURCE.format(ym=ym), headers={"User-Agent": "evil2ban"})
            with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
            n = build_geo_db(tmp, dest)
            os.remove(tmp)
            return n
        except Exception:  # noqa: BLE001
            continue
    if os.path.exists(tmp):
        os.remove(tmp)
    return 0


class LocalGeoLocator(GeoLocator):
    """Tra tai cho; neu chua co file (hoac qua 35 ngay) thi tai ve o luong nen."""

    MAX_AGE = 35 * 86400

    def __init__(self, path, auto_update=True):
        self.path = path
        self._starts, self._ccs, self._mtime = None, b"", 0
        self._lock = threading.Lock()
        self._load()
        if auto_update and (self._starts is None or time.time() - self._mtime > self.MAX_AGE):
            threading.Thread(target=self._bg_update, daemon=True).start()

    def _load(self):
        try:
            st = os.stat(self.path)
            with open(self.path, "rb") as f:
                if f.read(len(MAGIC)) != MAGIC:
                    return
                (n,) = struct.unpack("<I", f.read(4))
                starts = array("I")
                starts.frombytes(f.read(4 * n))
                ccs = f.read(2 * n)
            with self._lock:
                self._starts, self._ccs, self._mtime = starts, ccs, st.st_mtime
        except (OSError, struct.error):
            pass

    def _bg_update(self):
        if update_geo_db(self.path):
            self._load()

    @property
    def ready(self):
        return self._starts is not None

    def country(self, ip) -> str:
        if self._starts is None:
            return ""
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            return ""
        if a.version != 4 or not a.is_global:
            return ""
        i = bisect.bisect_right(self._starts, int(a)) - 1
        if i < 0:
            return ""
        cc = self._ccs[2 * i:2 * i + 2].decode("ascii", "replace")
        return "" if cc in ("--", "ZZ") else cc
