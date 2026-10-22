# -*- coding: utf-8 -*-
"""Hien thuc Firewall + SshLogReader qua fail2ban-client / journald."""
import re
import subprocess
from collections import Counter

from ..core.interfaces import Firewall, SshLogReader
from ..core.models import BanStatus


def _run(cmd, timeout=10):
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout).stdout
    except Exception as e:  # noqa: BLE001
        return f"error: {e}"


class Fail2banFirewall(Firewall):
    def __init__(self, geo=lambda ip: ""):
        self.geo = geo

    def ban(self, jail, ip) -> str:
        return _run(["fail2ban-client", "set", jail, "banip", ip])

    def unban(self, jail, ip) -> str:
        return _run(["fail2ban-client", "set", jail, "unbanip", ip])

    def status(self, jail) -> BanStatus:
        out = _run(["fail2ban-client", "status", jail])
        m = re.search(r"Banned IP list:\s*(.*)", out)
        ips = m.group(1).split() if m else []
        cf = re.search(r"Currently failed:\s*(\d+)", out)
        tb = re.search(r"Total banned:\s*(\d+)", out)
        return BanStatus(
            jail=jail,
            banned=[{"ip": i, "country": self.geo(i)} for i in ips],
            currently_failed=int(cf.group(1)) if cf else 0,
            total_banned=int(tb.group(1)) if tb else 0)


class JournaldSshReader(SshLogReader):
    def __init__(self, geo=lambda ip: ""):
        self.geo = geo

    def failed_logins(self, since="6 hours ago") -> dict:
        out = ""
        for unit in ("ssh.service", "sshd.service"):
            out += _run(["journalctl", "-u", unit, "--since", since,
                         "--no-pager", "-q"])
        ips = re.findall(
            r"Failed password for (?:invalid user )?\S+ from (\d+\.\d+\.\d+\.\d+)", out)
        users = re.findall(r"Failed password for (?:invalid user )?(\S+) from", out)
        c = Counter(ips)
        return {"total_failed": len(ips),
                "top": [{"ip": ip, "n": n, "country": self.geo(ip)}
                        for ip, n in c.most_common(12)],
                "top_users": [{"u": u, "n": n}
                              for u, n in Counter(users).most_common(8)]}
