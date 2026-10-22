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
from ..infra.geo import LocalGeoLocator, NullGeoLocator
from ..paths import state_dir
from ..infra.fail2ban import Fail2banFirewall, JournaldSshReader
from ..infra.mailer import SettingsMailer
from ..infra.webblock import NginxWebGate
from ..detect.ratewatch import RateWatcher
from ..services.notify_service import ChannelNotifier
from ..services.live_service import LiveService
from ..services.settings_service import SettingsService
from ..services.domain_service import DomainService
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

        # --- infrastructure ---
        # GeoIP tai cho (DB-IP Lite): khong goi dich vu ngoai, tu cap nhat moi thang
        self.geo = (LocalGeoLocator(str(state_dir() / "geoip-country.bin"))
                    if s.get_bool("detect.geoip", "E2B_GEOIP", True) else NullGeoLocator())
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
        self.notifier = ChannelNotifier(self.settings, self.meta)
        self.notifier.import_conf()          # lay kenh da co san trong notify.conf
        self.mailer = SettingsMailer(self.settings)

        # --- services ---
        self.guard = BanGuard(self.resolver, self.whitelist.matches)
        self.ban_service = BanService(self.firewall, self.notifier, self.events,
                                      self.guard, self.jail)
        self.auth = AuthService(self.settings, self.sessions, self.mailer, meta=self.meta)
        self.analysis = AnalysisService(
            self.analyzer, self.firewall, self.ssh, self.jail, __version__,
            ttl=s.get_int("detect.cache_ttl", "E2B_CACHE", 20))
        self.stats = StatsService(self.samples, self.meta, self.analyzer,
                                  self.firewall, self.ssh, self.jail)
        self.settings_svc = SettingsService(self.settings, self.notifier, self.events)
        self.domains = DomainService(self.source, self.parser, self.scan_detector,
                                     self.resolver, self.whitelist.matches,
                                     self.settings, self.events)
        self.ratewatch = RateWatcher(
            self.source, self.parser, self.resolver, self.whitelist.matches,
            threshold_fn=lambda: self.settings.get_int("detect.rate_alert", default=120),
            on_alert=self._on_rate_alert)
        self.live = LiveService(self.ratewatch, self.analysis, self.samples, self.settings)
        self.stats.rate = self.ratewatch
        self.webgate = NginxWebGate(self.settings)

    def sync_webgate(self):
        """Dong bo danh sach IP dang bi fail2ban chan sang Nginx (tra 403 o tang web)."""
        try:
            self.analysis.drop_banned()
            return self.webgate.sync([b["ip"] for b in self.analysis.banned().banned])
        except Exception:  # noqa: BLE001
            return False

    # --- doc dong (doi tren WebUI co hieu luc ngay, khong can khoi dong lai) ---
    @property
    def autoban(self):
        return self.settings.get_bool("detect.autoban", "E2B_AUTOBAN", False)

    @property
    def autoban_policy(self):
        return AutoBanPolicy(self.settings.get_int("detect.autoban_404", "E2B_AUTOBAN_404", 40))

    def _on_rate_alert(self, a):
        self.events.add("rate-alert", a["ip"], reason="auto",
                        detail=f"{a['rpm']} request/phút (ngưỡng {a['threshold']})")
        self.notifier.notify("rate", "⚡ IP đang cào quá nhanh",
                             [f"IP: {a['ip']}", f"Tốc độ: {a['rpm']} request/phút (ngưỡng {a['threshold']})"])
