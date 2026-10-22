# -*- coding: utf-8 -*-
"""
Interface (ABC) — tru cot cho Dependency Inversion.
Service tang tren phu thuoc vao cac truu tuong nay, khong phu thuoc hien thuc
cu the (fail2ban, ipinfo, SMTP...). De thay the / test / mo rong.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterable, Optional, Tuple

from .models import LogEntry, BanStatus, IpStats


class LogSource(ABC):
    """Nguon dong log (nginx access log, ...)."""
    @abstractmethod
    def lines(self) -> Iterable[str]: ...


class IpResolver(ABC):
    """Khoi phuc IP that tu IP edge + header (xu ly Cloudflare)."""
    @abstractmethod
    def resolve(self, edge_ip: str, cf_connecting_ip: str = "",
                x_forwarded_for: str = "") -> Tuple[Optional[str], bool]: ...

    @abstractmethod
    def is_cdn(self, ip: str) -> bool: ...


class DetectionRule(ABC):
    """
    Mot 'case' phat hien nho. Mo rong bang cach them lop moi (Open/Closed) —
    khong sua detector.
    """
    key: str = "rule"
    weight: int = 1
    threshold: int = 1   # so lan khop de rule 'noi len'

    @abstractmethod
    def matches(self, entry: LogEntry) -> bool: ...

    def triggered(self, stats: IpStats) -> bool:
        return stats.rule_hits.get(self.key, 0) >= self.threshold

    def score(self, stats: IpStats) -> int:
        return self.weight * stats.rule_hits.get(self.key, 0)


class Firewall(ABC):
    """Cong cu chan/go chan (fail2ban, nftables, ...)."""
    @abstractmethod
    def ban(self, jail: str, ip: str) -> str: ...
    @abstractmethod
    def unban(self, jail: str, ip: str) -> str: ...
    @abstractmethod
    def status(self, jail: str) -> BanStatus: ...


class Notifier(ABC):
    """Gui thong bao su kien (Telegram/Slack/Discord...)."""
    @abstractmethod
    def send(self, event: str, jail: str, ip: str, failures: str = "") -> bool: ...


class Mailer(ABC):
    """Gui email (reset mat khau)."""
    @abstractmethod
    def send(self, subject: str, body: str, to: Optional[str] = None) -> Tuple[bool, str]: ...


class GeoLocator(ABC):
    """Tra ma quoc gia cho IP."""
    @abstractmethod
    def country(self, ip: str) -> str: ...


class SshLogReader(ABC):
    """Doc journald de dem SSH brute-force."""
    @abstractmethod
    def failed_logins(self, since: str = "6 hours ago") -> dict: ...
