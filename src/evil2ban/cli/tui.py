# -*- coding: utf-8 -*-
"""
TUI Evil2Ban — menu chi muc 1/2/3 (Dashboard / Monitor / Blacklist),
cong reset mat khau qua email + xem/sua cau hinh. Dung chung service
voi backend (Container) nen logic nhat quan.

  evil2ban
"""
import sys
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import box

from .. import __version__
from ..core.exceptions import BanRejected, AuthError, NotConfigured
from ..web.container import Container

C = Console()
K = Container()


def header():
    C.print(Panel.fit(f"[bold red]Evil2Ban[/] v{__version__}  ·  phat hien & chan brute-force",
                      border_style="red"))


# ---------------- 1) Dashboard ----------------
def view_dashboard():
    a = K.analyzer.analyze()
    b = K.firewall.status(K.jail)
    s = K.ssh.failed_logins()
    t = Table(box=box.ROUNDED, show_header=False, expand=True)
    t.add_column(style="bold"); t.add_column(justify="right")
    t.add_row("IP dang bi chan", f"[red]{len(b.banned)}[/]")
    t.add_row("Tong da chan (luy ke)", str(b.total_banned))
    t.add_row("SSH brute-force (6h)", f"[yellow]{s['total_failed']}[/]")
    t.add_row("Request (mau)", f"{a['requests']}  ([dim]{a['cdn_hidden']} sau CDN[/])")
    t.add_row("IP that (ngoai Cloudflare)", str(a["unique_ips"]))
    t.add_row("IP nghi van", f"[yellow]{len(a['suspects'])}[/]")
    t.add_row("Auto-ban", "[red]BAT[/]" if K.autoban else "[dim]tat[/]")
    C.print(Panel(t, title="Dashboard", border_style="cyan"))


# ---------------- 2) Monitor ----------------
def view_monitor():
    s = K.ssh.failed_logins()
    tb = Table(title="SSH brute-force (6h)", box=box.SIMPLE, expand=True)
    tb.add_column("IP"); tb.add_column("Nuoc"); tb.add_column("Lan sai", justify="right")
    for r in s["top"]:
        tb.add_row(r["ip"], r.get("country", ""), str(r["n"]))
    C.print(tb)
    a = K.analyzer.analyze()
    tt = Table(title="Top traffic (IP that)", box=box.SIMPLE, expand=True)
    tt.add_column("IP"); tt.add_column("Nuoc"); tt.add_column("Request", justify="right")
    for r in a["top_traffic"]:
        tt.add_row(r["ip"], r.get("country", ""), str(r["total"]))
    C.print(tt)
    te = Table(title="Su kien gan day", box=box.SIMPLE, expand=True)
    te.add_column("Thoi gian"); te.add_column("Loai"); te.add_column("IP"); te.add_column("Ly do")
    for e in K.events.recent(limit=12):
        d = datetime.fromtimestamp(e["ts"], tz=timezone.utc).strftime("%m-%d %H:%M")
        te.add_row(d, e["type"], e["ip"] or "", e["reason"] or "")
    C.print(te)


# ---------------- 3) Blacklist ----------------
def view_blacklist():
    while True:
        b = K.firewall.status(K.jail)
        a = K.analyzer.analyze()
        tb = Table(title=f"IP dang bi chan ({len(b.banned)})", box=box.SIMPLE, expand=True)
        tb.add_column("#", justify="right"); tb.add_column("IP"); tb.add_column("Nuoc")
        for i, r in enumerate(b.banned, 1):
            tb.add_row(str(i), r["ip"], r.get("country", ""))
        C.print(tb)
        ts = Table(title=f"IP nghi van ({len(a['suspects'])})", box=box.SIMPLE, expand=True)
        ts.add_column("IP"); ts.add_column("404", justify="right"); ts.add_column("Scan")
        ts.add_column("Diem", justify="right"); ts.add_column("UA")
        for r in a["suspects"][:15]:
            ts.add_row(r["ip"], str(r["c404"]), "yes" if r["scanner_ua"] else "-",
                       str(r["score"]), (r["ua"] or "")[:40])
        C.print(ts)
        C.print("[dim]b=ban  u=unban  w=whitelist  q=quay lai[/]")
        ch = Prompt.ask("Thao tac", choices=["b", "u", "w", "q"], default="q")
        if ch == "q":
            return
        if ch == "b":
            ip = Prompt.ask("  IP can chan").strip()
            try:
                ok, out = K.ban_service.ban(ip, reason="tui")
                C.print("[green]Da chan[/]" if ok else f"[red]Loi: {out}[/]")
            except BanRejected as e:
                C.print(f"[red]{e}[/]")
        elif ch == "u":
            ip = Prompt.ask("  IP can go chan").strip()
            ok, _ = K.ban_service.unban(ip)
            C.print("[green]Da go chan[/]" if ok else "[red]Loi[/]")
        elif ch == "w":
            manage_whitelist()


def manage_whitelist():
    t = Table(title="Whitelist", box=box.SIMPLE, expand=True)
    t.add_column("Entry"); t.add_column("Nguon"); t.add_column("Ghi chu")
    for r in K.whitelist.all():
        t.add_row(r["entry"], r["source"], r.get("note", ""))
    C.print(t)
    C.print("[dim]a=them  r=xoa  Enter=quay lai[/]")
    ch = Prompt.ask("Whitelist", choices=["a", "r", ""], default="")
    if ch == "a":
        e = Prompt.ask("  IP/CIDR them").strip()
        try:
            K.whitelist.add(e, source="owner", note="tui")
            C.print("[green]Da them[/]")
        except ValueError:
            C.print("[red]IP/CIDR khong hop le[/]")
    elif ch == "r":
        e = Prompt.ask("  IP/CIDR xoa").strip()
        C.print("[green]Da xoa[/]" if K.whitelist.remove(e) else
                "[red]Khong xoa duoc (system/khong ton tai)[/]")


# ---------------- 4) Reset mat khau ----------------
def reset_password():
    user = K.settings.get("auth.username", default="")
    if not user:
        C.print("[red]Chua cau hinh tai khoan (chay evil2ban-setup).[/]"); return
    C.print(f"Tai khoan: [bold]{user}[/]")
    if not Confirm.ask("Sinh mat khau moi va gui qua email?", default=False):
        return
    try:
        ok, msg, newpw = K.auth.reset_password()
    except (NotConfigured, AuthError) as e:
        C.print(f"[red]{e}[/]"); return
    K.events.add("reset-password", "", reason="tui", detail=msg)
    if ok:
        C.print(f"[green]{msg}[/]")
    else:
        C.print(f"[yellow]Da doi mat khau nhung khong gui duoc email:[/] {msg}")
        C.print(f"[bold]Mat khau moi: {newpw}[/]")


# ---------------- 5) Cau hinh ----------------
def view_settings():
    s = K.settings.all(redact=True)
    t = Table(title="Cau hinh (bi mat da an)", box=box.SIMPLE, expand=True)
    t.add_column("Key"); t.add_column("Value")
    for k in sorted(s):
        t.add_row(k, str(s[k]))
    C.print(t)
    if Confirm.ask("Sua mot gia tri?", default=False):
        key = Prompt.ask("  Key (vd detect.autoban)").strip()
        if key not in s:
            C.print("[red]Key khong ton tai[/]"); return
        val = Prompt.ask(f"  Gia tri moi cho {key}").strip()
        K.settings.set(key, val)
        C.print("[green]Da luu. Khoi dong lai: systemctl restart evil2ban[/]")


MENU = """[bold]1[/]) Dashboard      — tong quan
[bold]2[/]) Monitor        — SSH/traffic/su kien
[bold]3[/]) Blacklist      — xem/chan/go chan/whitelist
[bold]4[/]) Reset mat khau — gui qua email
[bold]5[/]) Cau hinh       — xem/sua settings
[bold]0[/]) Thoat"""


def main():
    header()
    actions = {"1": view_dashboard, "2": view_monitor, "3": view_blacklist,
               "4": reset_password, "5": view_settings}
    while True:
        C.print(Panel(MENU, border_style="dim"))
        ch = Prompt.ask("Chon", choices=list(actions) + ["0"], default="1")
        C.print()
        if ch == "0":
            C.print("Tam biet."); sys.exit(0)
        actions[ch]()
        C.print()


if __name__ == "__main__":
    main()
