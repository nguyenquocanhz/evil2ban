# -*- coding: utf-8 -*-
"""Mo hinh du lieu thuan (dataclass) — khong logic, khong I/O."""
from __future__ import annotations
from dataclasses import dataclass, field
from collections import Counter
from typing import Optional


@dataclass
class LogEntry:
    """Mot dong access log da khoi phuc real-IP."""
    edge_ip: str                  # IP o $remote_addr (co the la edge Cloudflare)
    client_ip: Optional[str]      # IP that; None => sau CDN, khong quy duoc
    behind_cdn: bool
    ts: str
    method: str
    path: str
    status: str
    ua: str
    referer: str = ""


@dataclass
class IpStats:
    """Tich luy so lieu cho mot IP (dem theo tung rule)."""
    ip: str
    total: int = 0
    last: str = ""
    ua: Counter = field(default_factory=Counter)
    rule_hits: Counter = field(default_factory=Counter)  # key rule -> so lan


@dataclass
class Suspect:
    ip: str
    score: int
    total: int
    c404: int
    scanner_ua: bool
    sensitive: int
    ua: str
    country: str = ""

    def as_dict(self) -> dict:
        return {"ip": self.ip, "score": self.score, "total": self.total,
                "c404": self.c404, "scanner_ua": self.scanner_ua,
                "sensitive": self.sensitive, "ua": self.ua, "country": self.country}


@dataclass
class BanStatus:
    jail: str
    banned: list          # [{ip, country}]
    currently_failed: int
    total_banned: int


@dataclass
class SeriesPoint:
    t: str
    v: int


@dataclass
class Candle:
    t: str
    o: int
    h: int
    l: int
    c: int
