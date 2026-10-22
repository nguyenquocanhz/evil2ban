# -*- coding: utf-8 -*-
"""
DdosShield — 5 lop chong DDoS tren may chu, sinh tu MOT cau hinh (dict):

  origin  nftables: cong 80/443 chi nhan ket noi tu dai Cloudflare
  syn     sysctl (hang doi SYN, thu lai SYN-ACK, syncookies) + nftables gioi han SYN moi/IP
  udp     nftables: gioi han goi UDP "moi" (chua co tra loi) moi IP
  icmp    nftables: bo ping qua co + gioi han ping moi IP (kernel da mien nhiem Ping of Death)
  slow    Nginx: timeout header/body ngan + gioi han ket noi va request moi IP (Slowloris)

IP vuot nguong SYN/UDP vao set flood4/flood6 (tu het han sau 1 gio) -> bi bo.
IP Cloudflare, loopback va whitelist luon duoc bo qua.

Moi thay doi deu co "cong tac nguoi chet": ghi lai cau hinh cu, ap cau hinh moi, hen
systemd tu hoan tac sau 60 giay. Nguoi dung bam "Giu thay doi" thi huy hen gio.
Chay `python -m evil2ban.infra.ddos revert` = hoan tac (systemd goi lenh nay).

Chi them bang rieng `inet evil2ban_ddos` (chi DROP, khong bao gio ACCEPT thay ufw),
khong dung toi bang cua ufw / fail2ban.
"""
import os
import sys
import json
import time
import socket
import ipaddress
import subprocess
import threading

from ..detect.cloudflare import CLOUDFLARE_CIDRS, is_cloudflare

TABLE = "evil2ban_ddos"
LAYERS = ("origin", "syn", "udp", "icmp", "slow")
FW_LAYERS = ("origin", "syn", "udp", "icmp")
STATE_DIR = "/var/lib/evil2ban/ddos"
PENDING = os.path.join(STATE_DIR, "pending.json")
REVERTED = os.path.join(STATE_DIR, "reverted.json")
ORIG_SYSCTL = os.path.join(STATE_DIR, "orig-sysctl.json")
SYSCTL_FILE = "/etc/sysctl.d/90-evil2ban-ddos.conf"
NGINX_FILE = "/www/server/panel/vhost/nginx/0.evil2ban-ddos.conf"
VHOST_DIR = "/www/server/panel/vhost/nginx"
UNIT = "evil2ban-ddos-revert"
CONFIRM_SECONDS = 60
MARK = "# Evil2Ban chong DDoS — tu dong tao, dung sua tay."

# nguong mac dinh + mien gia tri cho phep
THRESHOLDS = {
    "syn_rate": (60, 5, 10000),        # SYN moi / giay / IP
    "udp_rate": (200, 10, 100000),     # goi UDP moi / giay / IP
    "icmp_rate": (5, 1, 1000),         # ping / giay / IP
    "conn_per_ip": (30, 2, 10000),     # ket noi dong thoi / IP (Nginx)
    "req_rate": (20, 1, 10000),        # request / giay / IP (Nginx)
    "timeout": (10, 3, 120),           # giay cho header/body (Nginx)
}
TH_LAYER = {"syn_rate": "syn", "udp_rate": "udp", "icmp_rate": "icmp",
            "conn_per_ip": "slow", "req_rate": "slow", "timeout": "slow"}
SYSCTL_REC = {
    "net.ipv4.tcp_max_syn_backlog": 4096,
    "net.ipv4.tcp_synack_retries": 2,
    "net.ipv4.tcp_syncookies": 1,
}
DEFAULT_CONFIG = {k: False for k in LAYERS}


def _run(*cmd, inp=None):
    try:
        return subprocess.run(list(cmd), input=inp, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def _read(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return default


def _write(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def _sysctl_get(key):
    v = _read("/proc/sys/" + key.replace(".", "/"))
    try:
        return int(v.split()[0]) if v else None
    except ValueError:
        return None


def clean_config(cfg, th):
    out = {k: bool((cfg or {}).get(k)) for k in LAYERS}
    t = {}
    for k, (d, lo, hi) in THRESHOLDS.items():
        try:
            v = int((th or {}).get(k, d))
        except (TypeError, ValueError):
            v = d
        t[k] = min(max(v, lo), hi)
    return out, t


# ---------------- sinh cau hinh ----------------
def _split(entries):
    v4, v6 = [], []
    for e in entries:
        try:
            n = ipaddress.ip_network(str(e).strip(), strict=False)
        except ValueError:
            continue
        (v4 if n.version == 4 else v6).append(n.compressed)
    return v4, v6


def _set(name, kind, elems, extra="flags interval; auto-merge;"):
    el = f" elements = {{ {', '.join(elems)} }}" if elems else ""
    return f"  set {name} {{ type {kind}; {extra}{el} }}\n"


def build_nft(cfg, th, allow):
    """Bang nftables cho cac lop dang bat. Khong lop nao bat -> chuoi rong (chi xoa bang)."""
    head = f"table inet {TABLE}\ndelete table inet {TABLE}\n"
    if not any(cfg[k] for k in FW_LAYERS):
        return head
    cf4, cf6 = _split(CLOUDFLARE_CIDRS)
    al4, al6 = _split(allow)
    dyn = "flags dynamic, timeout; timeout 1m; size 65536;"
    s = [head, f"table inet {TABLE} {{\n",
         _set("cf4", "ipv4_addr", cf4), _set("cf6", "ipv6_addr", cf6),
         _set("allow4", "ipv4_addr", al4), _set("allow6", "ipv6_addr", al6),
         _set("flood4", "ipv4_addr", [], "flags dynamic, timeout; timeout 1h; size 65536;"),
         _set("flood6", "ipv6_addr", [], "flags dynamic, timeout; timeout 1h; size 65536;")]
    for m in ("synm4", "udpm4", "icmpm4"):
        s.append(_set(m, "ipv4_addr", [], dyn))
    for m in ("synm6", "udpm6", "icmpm6"):
        s.append(_set(m, "ipv6_addr", [], dyn))
    r = ["iif \"lo\" accept", "ip saddr @allow4 accept", "ip6 saddr @allow6 accept",
         "ip saddr @flood4 drop comment \"e2b:flood\"", "ip6 saddr @flood6 drop comment \"e2b:flood\""]
    if cfg["origin"]:
        r += ['tcp dport { 80, 443 } ip saddr != @cf4 drop comment "e2b:origin"',
              'tcp dport { 80, 443 } ip6 saddr != @cf6 drop comment "e2b:origin"']
    r += ["ip saddr @cf4 accept", "ip6 saddr @cf6 accept"]   # Cloudflare khong bao gio bi dem nguong
    if cfg["syn"]:
        n = th["syn_rate"]
        for v, a in (("4", "ip"), ("6", "ip6")):
            r.append(f"meta nfproto ipv{v} tcp flags & (fin|syn|rst|ack) == syn add @synm{v} {{ {a} saddr limit rate over {n}/second burst {n * 2} packets }} "
                     f"add @flood{v} {{ {a} saddr }} drop comment \"e2b:syn\"")
    if cfg["udp"]:
        n = th["udp_rate"]
        for v, a in (("4", "ip"), ("6", "ip6")):
            r.append(f"meta nfproto ipv{v} meta l4proto udp ct state new add @udpm{v} {{ {a} saddr limit rate over {n}/second burst {n * 2} packets }} "
                     f"add @flood{v} {{ {a} saddr }} drop comment \"e2b:udp\"")
    if cfg["icmp"]:
        n = th["icmp_rate"]
        r += ['icmp type echo-request meta length > 1028 drop comment "e2b:icmp"',
              'icmpv6 type echo-request meta length > 1048 drop comment "e2b:icmp"',
              f'icmp type echo-request add @icmpm4 {{ ip saddr limit rate over {n}/second burst {n * 2} packets }} drop comment "e2b:icmp"',
              f'icmpv6 type echo-request add @icmpm6 {{ ip6 saddr limit rate over {n}/second burst {n * 2} packets }} drop comment "e2b:icmp"']
    s.append("  chain input {\n    type filter hook input priority -5; policy accept;\n")
    s += [f"    {x}\n" for x in r]
    s.append("  }\n}\n")
    return "".join(s)


def build_nginx(th, allow):
    exempt = "".join(f"    {c} 1;\n" for c in list(CLOUDFLARE_CIDRS) + list(allow))
    t = th["timeout"]
    return f"""{MARK}
# Chong Slowloris: ngat ket noi gui header/body qua cham.
client_header_timeout {t}s;
client_body_timeout {t}s;
# Gioi han theo IP that (sau real_ip). Site chua khoi phuc IP that thi IP la Cloudflare
# -> khoa rong -> khong bi gioi han, tranh chan nham ca dai Cloudflare.
geo $e2b_ddos_exempt {{
    default 0;
{exempt}}}
map $e2b_ddos_exempt $e2b_ddos_key {{
    0 $binary_remote_addr;
    default "";
}}
limit_conn_zone $e2b_ddos_key zone=e2b_conn:10m;
limit_req_zone $e2b_ddos_key zone=e2b_req:10m rate={th["req_rate"]}r/s;
limit_conn e2b_conn {th["conn_per_ip"]};
limit_req zone=e2b_req burst={th["req_rate"] * 2} nodelay;
limit_conn_status 429;
limit_req_status 429;
"""


def build_sysctl():
    return MARK + "\n" + "".join(f"{k} = {v}\n" for k, v in SYSCTL_REC.items())


# ---------------- ap cau hinh ----------------
def realize(cfg, th, allow):
    """Dua he thong ve dung cau hinh. Tra danh sach loi (rong = thanh cong)."""
    errs = []
    # sysctl (lop syn)
    if cfg["syn"]:
        if not os.path.exists(ORIG_SYSCTL):
            _write(ORIG_SYSCTL, json.dumps({k: _sysctl_get(k) for k in SYSCTL_REC}), 0o600)
        _write(SYSCTL_FILE, build_sysctl())
        if _run("sysctl", "-q", "-p", SYSCTL_FILE).returncode != 0:
            errs.append("sysctl")
    elif os.path.exists(SYSCTL_FILE):
        os.remove(SYSCTL_FILE)
        orig = json.loads(_read(ORIG_SYSCTL, "{}") or "{}")
        for k, v in orig.items():
            if v is not None:
                _run("sysctl", "-q", "-w", f"{k}={v}")
    # nftables
    r = _run("nft", "-f", "-", inp=build_nft(cfg, th, allow))
    if r.returncode != 0:
        errs.append("nft: " + r.stderr.strip()[-300:])
    # nginx (lop slow)
    old = _read(NGINX_FILE)
    new = build_nginx(th, allow) if cfg["slow"] else None
    if new != old:
        if new is None:
            os.remove(NGINX_FILE)
        else:
            _write(NGINX_FILE, new)
        t = _run("nginx", "-t")
        if t.returncode != 0:
            if old is None:
                os.remove(NGINX_FILE)
            else:
                _write(NGINX_FILE, old)
            errs.append("nginx: " + t.stderr.strip()[-300:])
        else:
            _run("nginx", "-s", "reload")
    return errs


def _stop_timer():
    _run("systemctl", "stop", f"{UNIT}.timer", f"{UNIT}.service")
    _run("systemctl", "reset-failed", f"{UNIT}.timer", f"{UNIT}.service")


def revert_pending(by="timer"):
    """Tra he thong ve cau hinh truoc lan doi dang cho xac nhan."""
    raw = _read(PENDING)
    if not raw:
        return False
    p = json.loads(raw)
    errs = realize(*clean_config(p["prev"], p["prev_th"]), p.get("allow", []))
    os.remove(PENDING)
    _write(REVERTED, json.dumps({"ts": int(time.time()), "by": by, "errors": errs}), 0o600)
    return True


# ---------------- trang thai + so lieu ----------------
_TCP_STATES = {"01": "est", "03": "synrecv"}


def _hex_ip(h):
    if len(h) == 8:
        return socket.inet_ntop(socket.AF_INET, bytes.fromhex(h)[::-1])
    b = bytes.fromhex(h)
    b = b"".join(b[i:i + 4][::-1] for i in range(0, 16, 4))
    ip = ipaddress.ip_address(b)
    return str(ip.ipv4_mapped) if ip.ipv4_mapped else ip.compressed


def read_tcp():
    """(so SYN_RECV, so ESTABLISHED vao, {ip: [so ket noi, cong]})"""
    listen, socks = set(), []
    for f in ("/proc/net/tcp", "/proc/net/tcp6"):
        for ln in (_read(f, "") or "").splitlines()[1:]:
            p = ln.split()
            if len(p) < 4:
                continue
            lport = int(p[1].rsplit(":", 1)[1], 16)
            if p[3] == "0A":
                listen.add(lport)
            elif p[3] in _TCP_STATES:
                socks.append((_TCP_STATES[p[3]], lport, p[2].rsplit(":", 1)[0]))
    syn = est = 0
    per = {}
    for st, lport, rh in socks:
        if lport not in listen:
            continue                     # ket noi di ra (box goi ra ngoai), bo qua
        try:
            ip = _hex_ip(rh)
        except ValueError:
            continue
        if ip.startswith("127.") or ip == "::1":
            continue
        if st == "synrecv":
            syn += 1
        else:
            est += 1
        e = per.setdefault(ip, [0, lport])
        e[0] += 1
    return syn, est, per


def read_packets():
    """Tong goi UDP + ICMP vao tu luc khoi dong (de tinh goi/giay)."""
    total = 0
    lines = (_read("/proc/net/snmp", "") or "").splitlines()
    for i in range(0, len(lines) - 1, 2):
        h, v = lines[i].split(), lines[i + 1].split()
        if h[0] == "Udp:":
            d = dict(zip(h[1:], v[1:]))
            total += int(d.get("InDatagrams", 0)) + int(d.get("NoPorts", 0)) + int(d.get("InErrors", 0))
        elif h[0] == "Icmp:":
            total += int(dict(zip(h[1:], v[1:])).get("InMsgs", 0))
    for ln in (_read("/proc/net/snmp6", "") or "").splitlines():
        k, _, v = ln.partition(" ")
        if k in ("Udp6InDatagrams", "Udp6NoPorts", "Udp6InErrors", "Icmp6InMsgs"):
            total += int(v.strip() or 0)
    return total


def read_conntrack():
    return (_sysctl_get("net.netfilter.nf_conntrack_count") or 0,
            _sysctl_get("net.netfilter.nf_conntrack_max") or 0)


def nft_rules():
    r = _run("nft", "list", "table", "inet", TABLE)
    return r.stdout if r.returncode == 0 else ""


def flood_ips():
    out = []
    for s in ("flood4", "flood6"):
        r = _run("nft", "-j", "list", "set", "inet", TABLE, s)
        if r.returncode != 0:
            continue
        try:
            for o in json.loads(r.stdout).get("nftables", []):
                for e in (o.get("set") or {}).get("elem", []) or []:
                    v = e.get("elem", {}).get("val") if isinstance(e, dict) else e
                    if isinstance(v, str):
                        out.append(v)
        except ValueError:
            pass
    return out


def layer_status(th):
    rules = nft_rules()
    sc = {k: _sysctl_get(k) for k in SYSCTL_REC}
    sys_ok = all(sc[k] is not None and (sc[k] <= v if "retries" in k else sc[k] >= v) for k, v in SYSCTL_REC.items())
    on = {k: f"e2b:{k}" in rules for k in FW_LAYERS}
    ng = _read(NGINX_FILE) or ""
    syn_state = "on" if (sys_ok and on["syn"]) else ("partial" if (sys_ok or on["syn"]) else "off")
    return [
        {"key": "origin", "state": "on" if on["origin"] else "off", "cur": {}},
        {"key": "syn", "state": syn_state, "cur": {"backlog": sc["net.ipv4.tcp_max_syn_backlog"],
                                                   "retries": sc["net.ipv4.tcp_synack_retries"],
                                                   "cookies": sc["net.ipv4.tcp_syncookies"],
                                                   "limit": on["syn"]}},
        {"key": "udp", "state": "on" if on["udp"] else "off", "cur": {}},
        {"key": "icmp", "state": "on" if on["icmp"] else "partial", "cur": {}},
        {"key": "slow", "state": "on" if MARK in ng else "off", "cur": {}},
    ]


def server_names():
    names = set()
    try:
        files = [f for f in os.listdir(VHOST_DIR) if f.endswith(".conf")]
    except OSError:
        return []
    for f in files:
        txt = _read(os.path.join(VHOST_DIR, f), "") or ""
        for ln in txt.splitlines():
            ln = ln.strip()
            if ln.startswith("server_name"):
                for n in ln[len("server_name"):].strip(" ;").split():
                    if "." in n and not n.startswith(("*", "~")) and not n[0].isdigit() and n != "_":
                        names.add(n.lower())
    return sorted(names)


def check_origin():
    """Moi ten mien tro qua Cloudflare chua? Ten mien tro thang ve IP may chu se chet khi khoa IP goc."""
    direct, unresolved, behind = [], [], 0
    for n in server_names():
        try:
            ips = {a[4][0] for a in socket.getaddrinfo(n, 443, proto=socket.IPPROTO_TCP)}
        except OSError:
            unresolved.append(n)
            continue
        if ips and all(is_cloudflare(ip) for ip in ips):
            behind += 1
        else:
            direct.append(n)
    return {"total": behind + len(direct), "behind": behind, "direct": direct, "unresolved": unresolved,
            "ok": not direct, "ts": int(time.time())}


class DdosShield:
    """Cau hinh da xac nhan nam trong SQLite (ddos.config, ddos.th); cau hinh dang cho nam trong pending.json."""

    def __init__(self, settings, allow_fn):
        self.settings = settings
        self.allow_fn = allow_fn          # () -> danh sach IP/CIDR whitelist cua chu (khong gom Cloudflare)
        self._lock = threading.Lock()
        self._origin = None

    # ---------- cau hinh ----------
    def committed(self):
        try:
            cfg = json.loads(self.settings.get("ddos.config", default="{}") or "{}")
            th = json.loads(self.settings.get("ddos.th", default="{}") or "{}")
        except ValueError:
            cfg, th = {}, {}
        return clean_config(cfg, th)

    @staticmethod
    def pending():
        raw = _read(PENDING)
        if not raw:
            return None
        p = json.loads(raw)
        return {"left": max(0, int(p["deadline"] - time.time())), "changes": p.get("changes", []),
                "cfg": p["cfg"], "th": p["th"]}

    def current(self):
        """Cau hinh dang chay: cau hinh cho xac nhan neu co, khong thi cau hinh da xac nhan."""
        p = self.pending()
        return (p["cfg"], p["th"]) if p else self.committed()

    def origin_check(self, fresh=False):
        if fresh or not self._origin or time.time() - self._origin["ts"] > 600:
            self._origin = check_origin()
        return self._origin

    # ---------- doi cau hinh ----------
    def apply(self, cfg, th):
        """Ap cau hinh moi, hen tu hoan tac. Tra (thay doi, loi)."""
        from ..core.exceptions import InvalidInput
        with self._lock:
            if os.path.exists(PENDING):
                raise InvalidInput("Đang chờ xác nhận lần đổi trước. Giữ hoặc hoàn tác trước đã.", "ddos_pending")
            prev, prev_th = self.committed()
            cfg, th = clean_config(cfg, th)
            changes = [k for k in LAYERS if cfg[k] != prev[k]] + [f"th.{k}" for k in THRESHOLDS if th[k] != prev_th[k]]
            if not changes:
                return [], []
            if all(c.startswith("th.") and not cfg[TH_LAYER[c[3:]]] for c in changes):
                self.settings.set("ddos.th", json.dumps(th))     # lop dang tat: chi luu nguong
                return changes, []
            if cfg["origin"] and not prev["origin"]:
                oc = self.origin_check(fresh=True)
                if not oc["ok"]:
                    raise InvalidInput("Còn tên miền trỏ thẳng về IP máy chủ, khoá IP gốc sẽ làm sập: "
                                       + ", ".join(oc["direct"][:6]), "origin_not_ready")
            allow = list(self.allow_fn())
            _write(PENDING, json.dumps({"prev": prev, "prev_th": prev_th, "cfg": cfg, "th": th, "allow": allow,
                                        "changes": changes, "deadline": time.time() + CONFIRM_SECONDS}), 0o600)
            _stop_timer()
            r = _run("systemd-run", "--quiet", f"--unit={UNIT}", f"--on-active={CONFIRM_SECONDS}",
                     "--timer-property=AccuracySec=1s", sys.executable, "-m", "evil2ban.infra.ddos", "revert")
            if r.returncode != 0:          # khong hen duoc systemd -> hen trong tien trinh
                threading.Timer(CONFIRM_SECONDS, revert_pending).start()
            errs = realize(cfg, th, allow)
            if errs:                       # loi thi tra lai ngay, khong de nguoi dung cho
                _stop_timer()
                revert_pending(by="error")
            return changes, errs

    def confirm(self):
        with self._lock:
            raw = _read(PENDING)
            if not raw:
                return None
            _stop_timer()
            p = json.loads(raw)
            self.settings.set("ddos.config", json.dumps(p["cfg"]))
            self.settings.set("ddos.th", json.dumps(p["th"]))
            os.remove(PENDING)
            return p["changes"]

    def revert(self):
        with self._lock:
            _stop_timer()
            return revert_pending(by="user")

    @staticmethod
    def take_reverted():
        """Lan hoan tac do systemd/loi lam (de ghi nhat ky audit trong tien trinh chinh)."""
        raw = _read(REVERTED)
        if not raw:
            return None
        os.remove(REVERTED)
        return json.loads(raw)

    def restore_on_boot(self):
        """Khoi dong lai: dang cho xac nhan ma khong con hen gio -> hoan tac; khong thi dung lai bang nft."""
        p = self.pending()
        if p:
            active = _run("systemctl", "is-active", f"{UNIT}.timer").stdout.strip() == "active"
            if not active:
                revert_pending(by="boot")
            return
        cfg, th = self.committed()
        if any(cfg.values()):
            realize(cfg, th, list(self.allow_fn()))

    def sync_allow(self):
        """Whitelist doi -> cap nhat set allow trong bang nft (khong dung lai luat)."""
        if not nft_rules():
            return
        a4, a6 = _split(self.allow_fn())
        cmds = f"flush set inet {TABLE} allow4\nflush set inet {TABLE} allow6\n"
        if a4:
            cmds += f"add element inet {TABLE} allow4 {{ {', '.join(a4)} }}\n"
        if a6:
            cmds += f"add element inet {TABLE} allow6 {{ {', '.join(a6)} }}\n"
        _run("nft", "-f", "-", inp=cmds)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "revert":
        revert_pending()
