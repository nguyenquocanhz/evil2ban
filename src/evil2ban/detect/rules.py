# -*- coding: utf-8 -*-
"""
Cac 'case' phat hien nho — moi quy tac mot lop (Open/Closed).
Them quy tac moi = them lop + dang ky, KHONG sua detector.
"""
import re

from ..core.interfaces import DetectionRule
from ..core.models import LogEntry

SCANNER_UA = re.compile(
    r"(sqlmap|nikto|nmap|masscan|zgrab|nuclei|wpscan|dirbuster|gobuster|hydra|"
    r"fuzz|acunetix|netsparker|censys|l9explore|httpx|feroxbuster|zmeu|morfeus|"
    r"softsec|research scan|expanse|internet-measurement)", re.I)
SENSITIVE = re.compile(
    r"(/\.env|/\.git|/wp-login|/xmlrpc\.php|/phpmyadmin|/pma|/\.aws|/\.ssh|"
    r"/vendor/|/actuator|/solr|/boaform|/\.well-known/.*\.php|/shell|/cgi-bin|"
    r"/manager/html|/admin/config|/eval-stdin\.php)", re.I)
BOT_UA = re.compile(
    r"(bot|spider|crawl|slurp|curl|wget|python-requests|go-http|okhttp|java/|"
    r"libwww|scrapy|headless|uptime-kuma)", re.I)
MOBILE_UA = re.compile(r"(android|iphone|ipad|mobile|ipod)", re.I)


class ScannerUaRule(DetectionRule):
    """UA cua cong cu quet (sqlmap, nuclei, l9explore...)."""
    key = "scanner_ua"
    weight = 10
    threshold = 1

    def matches(self, entry: LogEntry) -> bool:
        return bool(SCANNER_UA.search(entry.ua))


class SensitivePathRule(DetectionRule):
    """Do tim duong dan nhay cam (/.env, /.git, wp-login...)."""
    key = "sensitive"
    weight = 6
    threshold = 3

    def matches(self, entry: LogEntry) -> bool:
        return bool(SENSITIVE.search(entry.path))


class Excessive404Rule(DetectionRule):
    """Qua nhieu 404 (do quet thu muc/file)."""
    key = "c404"
    weight = 1
    threshold = 15

    def matches(self, entry: LogEntry) -> bool:
        return entry.status == "404"


# Thu tu = do uu tien hien thi; de mo rong them o day.
DEFAULT_RULES = [ScannerUaRule(), SensitivePathRule(), Excessive404Rule()]


def classify_device(ua: str) -> str:
    if BOT_UA.search(ua):
        return "bot"
    if MOBILE_UA.search(ua):
        return "mobile"
    return "desktop"
