# -*- coding: utf-8 -*-
"""
NginxWebGate — chan IP o TANG WEB (Nginx) va tra trang 403 thuong hieu.

Vi sao: khach di qua Cloudflare thi ket noi TCP toi may chu la IP Cloudflare,
chan bang tuong lua (fail2ban/iptables) theo IP that khong co tac dung. Nginx
khoi phuc IP that (real_ip) roi so voi danh sach `geo` -> tra 403.

Bo cuc:
  /www/server/panel/vhost/nginx/0.evil2ban.conf       geo $e2b_blocked (tang http)
  /www/server/panel/vhost/nginx/evil2ban/blocked.conf danh sach IP (tu dong ghi)
  .../extension/<site>/evil2ban.conf                  moi site: real_ip + tra 403
  /usr/lib/evil2ban/www/__evil2ban_403.html           trang 403 (SSI chen IP, ma)
Chi IP bi Evil2Ban chan moi thay trang nay (ma noi bo 418 -> 403); trang 403
von co cua site giu nguyen.
"""
import os
import shutil
import ipaddress
import subprocess
import threading

VHOST_DIR = "/www/server/panel/vhost/nginx"
GATE_DIR = os.path.join(VHOST_DIR, "evil2ban")
BLOCKED = os.path.join(GATE_DIR, "blocked.conf")
HTTP_CONF = os.path.join(VHOST_DIR, "0.evil2ban.conf")
EXT_DIR = os.path.join(VHOST_DIR, "extension")
REALIP_INC = os.path.join(GATE_DIR, "cloudflare-realip.inc")
WWW_DIR = "/usr/lib/evil2ban/www"
PAGE = "__evil2ban_403.html"
MARK = "# Evil2Ban web gate"

HTTP_CONF_TEXT = f"""{MARK} — tu dong tao, dung sua tay.
geo $e2b_blocked {{
    default 0;
    include {BLOCKED};
}}
# chuyen huong noi bo toi trang 403 chay lai pha rewrite cua server: bo qua chinh trang
# 403, neu khong no cung bi chan -> Nginx tra 418 trang.
map "$e2b_blocked:$uri" $e2b_deny {{
    volatile;          # tinh lai sau chuyen huong noi bo (map mac dinh nho ket qua ca request)
    default 0;
    "~^1:(?!/{PAGE}$)" 1;
}}
"""


def site_block(with_realip: bool) -> str:
    realip = f"include {REALIP_INC};\n" if with_realip else ""
    return f"""{MARK} — tu dong tao boi `evil2ban-setup --web-gate on`, dung sua tay.
{realip}error_page 418 =403 /{PAGE};
if ($e2b_deny) {{ return 418; }}
location = /{PAGE} {{
    internal;
    root {WWW_DIR};
    ssi on;
    add_header Cache-Control "no-store" always;
    add_header X-Robots-Tag "noindex" always;
}}
"""


def _nginx(*args):
    return subprocess.run(["nginx", *args], capture_output=True, text=True, timeout=20)


class NginxWebGate:
    def __init__(self, settings=None, page_src=None):
        self.settings = settings
        self.page_src = page_src or os.path.join(os.path.dirname(os.path.dirname(__file__)), "www", "403.html")
        self._lock = threading.Lock()
        self._last = None

    # ---------- trang thai ----------
    @property
    def installed(self):
        return os.path.exists(HTTP_CONF) and os.path.exists(BLOCKED)

    @property
    def enabled(self):
        return self.settings is None or self.settings.get_bool("web.block", default=True)

    @staticmethod
    def _vhosts():
        """(ten-site, file vhost) cho moi vhost co include thu muc extension."""
        out = []
        for f in sorted(os.listdir(VHOST_DIR)):
            p = os.path.join(VHOST_DIR, f)
            if not f.endswith(".conf") or not os.path.isfile(p):
                continue
            try:
                txt = open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if "vhost/nginx/extension/" in txt:
                out.append((f[:-5], txt))
        return out

    # ---------- dong bo danh sach ----------
    @staticmethod
    def _clean(ips):
        good = set()
        for ip in ips:
            try:
                a = ipaddress.ip_address(str(ip).strip())
            except ValueError:
                continue                   # chong chen cau hinh: chi nhan IP hop le
            if a.is_global:
                good.add(a.compressed)
        return sorted(good)

    def sync(self, ips) -> bool:
        """Ghi danh sach IP bi chan cho Nginx; chi reload khi thay doi. Tra True neu da ap dung."""
        if not self.installed:
            return False
        ips = self._clean(ips) if self.enabled else []
        body = MARK + " — tu dong ghi.\n" + "".join(f"{ip} 1;\n" for ip in ips)
        with self._lock:
            if body == self._last:
                return True
            try:
                old = open(BLOCKED, encoding="utf-8").read()
            except OSError:
                old = ""
            if body == old:
                self._last = body
                return True
            tmp = BLOCKED + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(body)
            os.replace(tmp, BLOCKED)
            if _nginx("-t").returncode != 0:          # loi -> tra lai file cu
                with open(BLOCKED, "w", encoding="utf-8") as f:
                    f.write(old)
                return False
            _nginx("-s", "reload")
            self._last = body
            return True

    # ---------- cai / go ----------
    def install(self):
        """Tao file geo, trang 403, gan vao moi site co thu muc extension. Tra (so site, bao cao)."""
        os.makedirs(GATE_DIR, exist_ok=True)
        os.makedirs(WWW_DIR, exist_ok=True)
        shutil.copyfile(self.page_src, os.path.join(WWW_DIR, PAGE))
        os.chmod(os.path.join(WWW_DIR, PAGE), 0o644)
        if not os.path.exists(BLOCKED):
            with open(BLOCKED, "w", encoding="utf-8") as f:
                f.write(MARK + " — tu dong ghi.\n")
        from ..detect.cloudflare import CLOUDFLARE_CIDRS
        with open(REALIP_INC, "w", encoding="utf-8") as f:
            f.write(MARK + ": khoi phuc IP that sau Cloudflare.\n"
                    + "".join(f"set_real_ip_from {c};\n" for c in CLOUDFLARE_CIDRS)
                    + "real_ip_header CF-Connecting-IP;\n")
        with open(HTTP_CONF, "w", encoding="utf-8") as f:
            f.write(HTTP_CONF_TEXT)
        done = []
        for site, txt in self._vhosts():
            has_realip = "set_real_ip_from" in txt or "cloudflare-ips.inc" in txt or "realip" in txt
            d = os.path.join(EXT_DIR, site)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "evil2ban.conf"), "w", encoding="utf-8") as f:
                f.write(site_block(with_realip=not has_realip))
            done.append((site, not has_realip))
        r = _nginx("-t")
        if r.returncode != 0:
            self.uninstall(reload=False)
            return 0, "nginx -t lỗi, đã gỡ lại: " + r.stderr.strip()[-400:]
        _nginx("-s", "reload")
        return len(done), done

    def uninstall(self, reload=True):
        for site, _ in self._vhosts():
            p = os.path.join(EXT_DIR, site, "evil2ban.conf")
            if os.path.exists(p):
                os.remove(p)
        for p in (HTTP_CONF,):
            if os.path.exists(p):
                os.remove(p)
        if reload and _nginx("-t").returncode == 0:
            _nginx("-s", "reload")
        return True
