# -*- coding: utf-8 -*-
"""Khoi phuc IP that khi di qua Cloudflare (hien thuc IpResolver)."""
import ipaddress
from typing import Optional, Tuple

from ..core.interfaces import IpResolver
from .cloudflare import is_cloudflare


class CloudflareRealIpResolver(IpResolver):
    """
    Neu edge la Cloudflare: uu tien CF-Connecting-IP / X-Forwarded-For.
    Khong khoi phuc duoc => tra (None, True) de caller BO QUA (khong ban),
    tuyet doi khong ban dai Cloudflare (tranh sap site).
    """

    def is_cdn(self, ip: str) -> bool:
        return is_cloudflare(ip)

    def _first_public(self, xff: str) -> Optional[str]:
        if not xff:
            return None
        for part in xff.replace(" ", "").split(","):
            if not part:
                continue
            try:
                a = ipaddress.ip_address(part)
            except ValueError:
                continue
            if (not (a.is_private or a.is_loopback or a.is_link_local)
                    and not is_cloudflare(part)):
                return part
        return None

    def resolve(self, edge_ip: str, cf_connecting_ip: str = "",
                x_forwarded_for: str = "") -> Tuple[Optional[str], bool]:
        if edge_ip and is_cloudflare(edge_ip):
            cand = (cf_connecting_ip or "").strip()
            if cand and not is_cloudflare(cand):
                return cand, True
            cand = self._first_public(x_forwarded_for)
            if cand:
                return cand, True
            return None, True
        return (edge_ip or None), False
