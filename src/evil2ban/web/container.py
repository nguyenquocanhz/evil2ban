# -*- coding: utf-8 -*-
"""
Composition root — noi (wire) tat ca thanh phan theo Dependency Injection.
Doc cau hinh tu SQLite 1 lan; moi tang tren nhan truu tuong qua ham khoi tao.
"""
from .. import __version__
from ..paths import db_path
from ..data.database import Database
from ..data.repositories import (
    SettingsRepository, WhitelistRepository, SessionRepository,
    EventRepository, MetaRepository, SampleRepository)
from ..detect.cloudflare import CLOUDFLARE_CIDRS
from ..detect.realip import CloudflareRealIpResolver
from ..detect.parser import NginxAccessLogSource, LogParser
from ..detect.rules import DEFAULT_RULES
from ..detect.detector import ScanDetector, TrafficAnalyzer
from ..infra.geo import IpinfoGeoLocator, NullGeoLocator
from ..infra.fail2ban import Fail2banFirewall, JournaldSshReader
from ..infra.notifier import ScriptNotifier
from ..infra.mailer import SmtpMailer
from ..services.ban_service import BanService, BanGuard, AutoBanPolicy
from ..services.auth_service import AuthService
from ..services.analysis_service import AnalysisService
from ..services.stats_service import StatsService


class Container:
    def __init__(self, path=None):
        self.db = Database(path or db_path())

        # --- repositories ---
        self.settings = SettingsRepository(self.db)
        self.whitelist = WhitelistRepository(self.db)
        self.sessions = SessionRepository(self.db)
        self.events = EventRepository(self.db)
        self.meta = MetaRepository(self.db)
        self.samples = SampleRepository(self.db)
        self.settings.seed_defaults()
        self.whitelist.seed(CLOUDFLARE_CIDRS)

        s = self.settings
        self.jail = s.get("detect.jail", "E2B_JAIL", "sshd")
        self.host = s.get("server.host", "E2B_HOST", "127.0.0.1")
        self.port = s.get_int("server.port", "E2B_PORT", 8793)
        self.autoban = s.get_bool("detect.autoban", "E2B_AUTOBAN", False)

        # --- infrastructure ---
        self.geo = (IpinfoGeoLocator() if s.get_bool("detect.geoip", "E2B_GEOIP", True)
                    else NullGeoLocator())
        self.resolver = CloudflareRealIpResolver()
        self.source = NginxAccessLogSource(
            s.get("detect.log_dir", "E2B_LOG_DIR", "/www/wwwlogs"),
            s.get_int("detect.max_files", "E2B_MAXFILES", 16),
            s.get_int("detect.tail_lines", "E2B_TAIL", 4000))
        self.parser = LogParser(self.resolver)
        self.scan_detector = ScanDetector(DEFAULT_RULES)
        self.analyzer = TrafficAnalyzer(
            self.parser, self.source, self.scan_detector, self.resolver,
            is_whitelisted=self.whitelist.matches, geo=self.geo.country)
        self.firewall = Fail2banFirewall(self.geo.country)
        self.ssh = JournaldSshReader(self.geo.country)
        self.notifier = ScriptNotifier(
            s.get("notify.script", default="/usr/local/bin/f2b-notify.sh"))
        self.mailer = SmtpMailer(
            s.get("mail.smtp_host", default="smtp.gmail.com"),
            s.get_int("mail.smtp_port", default=587),
            s.get("mail.smtp_user", default=""),
            s.get("mail.smtp_pass", default=""),
            s.get("mail.admin_email", default=""))

        # --- services ---
        self.guard = BanGuard(self.resolver, self.whitelist.matches)
        self.ban_service = BanService(self.firewall, self.notifier, self.events,
                                      self.guard, self.jail)
        self.auth = AuthService(self.settings, self.sessions, self.mailer)
        self.analysis = AnalysisService(
            self.analyzer, self.firewall, self.ssh, self.jail, __version__,
            ttl=s.get_int("detect.cache_ttl", "E2B_CACHE", 20))
        self.stats = StatsService(self.samples, self.meta, self.analyzer,
                                  self.firewall, self.ssh, self.jail)
        self.autoban_policy = AutoBanPolicy(
            s.get_int("detect.autoban_404", "E2B_AUTOBAN_404", 40))
