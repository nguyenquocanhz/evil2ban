# -*- coding: utf-8 -*-
"""
Tang web (mong) — route goi service. Khong chua logic nghiep vu.
Dashboard bind 127.0.0.1; ra Internet chi qua reverse proxy (Nginx + Cloudflare).
"""
import csv
import io
import json
import time
import asyncio
import threading
import subprocess
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import __version__
from ..paths import STATIC_DIR
from ..core.exceptions import Evil2BanError, BanRejected, InvalidInput
from .container import Container

C = Container()
app = FastAPI(title="Evil2Ban", version=__version__, docs_url=None, redoc_url=None)

OPEN_PATHS = ("/api/login", "/api/logout", "/api/reset-password", "/api/health")


def _token(request: Request):
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (request.headers.get("x-e2b-token")
            or request.cookies.get("e2b_token")
            or request.query_params.get("token", ""))


def actor_ip(request: Request) -> str:
    """IP that cua nguoi dung: Nginx da khoi phuc tu CF-Connecting-IP vao X-Real-IP."""
    return (request.headers.get("x-real-ip") or (request.client.host if request.client else "")).strip()


@app.middleware("http")
async def auth_mw(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and path not in OPEN_PATHS:
        if not C.auth.valid_token(_token(request)):
            return JSONResponse({"detail": "Phiên đăng nhập hết hạn.", "code": "unauthorized"}, status_code=401)
    return await call_next(request)


@app.exception_handler(Evil2BanError)
async def domain_error(_request: Request, e: Evil2BanError):
    return JSONResponse({"detail": str(e), "code": e.code}, status_code=e.status)


# ---------------- schemas ----------------
class LoginReq(BaseModel):
    username: str
    password: str


class ResetReq(BaseModel):
    username: str = ""


class IPReq(BaseModel):
    ip: str


class IPsReq(BaseModel):
    ips: list[str]


class WLReq(BaseModel):
    entry: str
    note: str = ""


class PwReq(BaseModel):
    current: str
    new: str


class ChannelReq(BaseModel):
    channel: str


class ModeReq(BaseModel):
    domain: str
    mode: str


class ThresholdReq(BaseModel):
    domain: str
    threshold: int


class DdosReq(BaseModel):
    layers: dict = {}
    th: dict = {}


# ---------------- auth ----------------
_FAILS = defaultdict(deque)        # ip -> thoi diem dang nhap sai (10 phut gan nhat)
_FAIL_LIMIT, _FAIL_WINDOW = 10, 600


@app.post("/api/login")
def login(r: LoginReq, request: Request):
    ip, now = actor_ip(request), time.time()
    q = _FAILS[ip]
    while q and now - q[0] > _FAIL_WINDOW:
        q.popleft()
    if len(q) >= _FAIL_LIMIT:
        return JSONResponse({"detail": "Đăng nhập sai quá nhiều lần. Thử lại sau 10 phút.",
                             "code": "too_many_attempts"}, status_code=429)
    try:
        tok = C.auth.login(r.username, r.password)
    except Evil2BanError as e:
        if e.code == "bad_credentials":
            q.append(now)
            C.events.add("login-fail", "", detail=f"tài khoản: {r.username[:40]}", actor_ip=ip, result="fail")
            if len(q) == 3:
                C.notifier.notify("login_fail", "🔐 Đăng nhập Evil2Ban thất bại",
                                  [f"3 lần sai liên tiếp từ IP: {ip}", f"Tài khoản thử: {r.username[:40]}"])
        raise
    q.clear()
    C.auth.record_login(ip, request.headers.get("user-agent", ""))
    C.events.add("login", "", actor_ip=ip)
    resp = JSONResponse({"ok": True, "token": tok, "username": r.username})
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    # cookie HttpOnly cho luong SSE (EventSource khong gui header Authorization)
    resp.set_cookie("e2b_token", tok, max_age=12 * 3600, httponly=True, samesite="strict", secure=secure)
    return resp


@app.post("/api/logout")
def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("e2b_token")
    return resp


@app.post("/api/reset-password")
def reset_password(r: ResetReq, request: Request):
    ok, msg, _ = C.auth.reset_password(r.username)
    C.events.add("reset-password", "", reason="email" if ok else "email-fail", detail=msg,
                 actor_ip=actor_ip(request), result="ok" if ok else "fail")
    if not ok:
        return JSONResponse({"detail": msg, "code": "email_failed"}, status_code=500)
    return {"ok": True, "detail": msg}


# ---------------- tai khoan ----------------
@app.get("/api/account")
def account():
    from ..cli.wizard import _public_ip
    return {**C.auth.account(), "server_ip": _public_ip(), "port": C.port}


@app.post("/api/account/password")
def change_password(r: PwReq, request: Request):
    C.auth.change_password(r.current, r.new)
    C.events.add("password-change", "", actor_ip=actor_ip(request))
    return {"ok": True}


@app.get("/api/account/link")
def access_link():
    return {"link": C.auth.access_link()}


@app.post("/api/account/token")
def regen_token(request: Request):
    C.auth.regen_token()
    C.events.add("token-regen", "", actor_ip=actor_ip(request))
    return {"ok": True, "link": C.auth.access_link()}


@app.post("/api/account/logout-all")
def logout_all(request: Request):
    C.auth.logout_all()
    C.events.add("logout-all", "", actor_ip=actor_ip(request))
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("e2b_token")
    return resp


# ---------------- tong quan / giam sat ----------------
@app.get("/api/overview")
def overview():
    return C.analysis.overview(C.autoban)


@app.get("/api/banned")
def banned():
    b = C.analysis.banned()
    return {"jail": b.jail, "banned": b.banned,
            "currently_failed": b.currently_failed, "total_banned": b.total_banned}


@app.get("/api/ssh")
def ssh():
    return C.analysis.ssh_stats()


@app.get("/api/traffic")
def traffic():
    return C.analysis.traffic()


@app.get("/api/events")
def events(limit: int = 100):
    return {"events": C.events.recent(limit=min(max(limit, 1), 500))}


@app.get("/api/live")
def live():
    return C.live.snapshot()


@app.get("/api/stream")
async def stream(request: Request):
    """SSE: MOT ket noi, server day so lieu song moi 5 giay (khong goi lap lai)."""
    async def gen():
        yield "retry: 5000\n\n"
        while not await request.is_disconnected():
            data = await run_in_threadpool(C.live.snapshot)
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            await asyncio.sleep(5)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------- cai dat ----------------
@app.get("/api/settings")
def settings():
    return {"settings": C.settings_svc.public(), "web_gate_installed": C.webgate.installed}


@app.post("/api/settings")
async def save_settings(request: Request):
    try:
        data = await request.json()
    except ValueError:
        raise InvalidInput("Dữ liệu gửi lên không hợp lệ.", "invalid_input")
    res = C.settings_svc.update(data, actor_ip(request))
    if "web.block" in res["saved"]:
        C.sync_webgate()
    res["web_gate_installed"] = C.webgate.installed
    return res


@app.post("/api/notify/test")
def notify_test(r: ChannelReq):
    ok, code = C.notifier.test(r.channel)
    if not ok:
        return JSONResponse({"detail": "Gửi thử thất bại.", "code": code}, status_code=400)
    return {"ok": True}


@app.post("/api/restart")
def restart(request: Request):
    C.events.add("settings", "", detail="khởi động lại dịch vụ", actor_ip=actor_ip(request))
    subprocess.Popen(["/bin/sh", "-c", "sleep 1; systemctl restart evil2ban"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {"ok": True}


# ---------------- nhat ky audit ----------------
@app.get("/api/audit")
def audit(group: str = "", days: int = 7, q: str = "", page: int = 1, per: int = 10):
    per = min(max(per, 1), 100)
    page = max(page, 1)
    rows, total = C.events.query(group, days, q.strip()[:80], per, (page - 1) * per)
    return {"items": rows, "total": total, "page": page, "per": per, "counts": C.events.counts(days)}


@app.get("/api/audit.csv")
def audit_csv(group: str = "", days: int = 7, q: str = ""):
    rows, _ = C.events.query(group, days, q.strip()[:80], 5000, 0)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["thoi_gian_utc", "viec", "doi_tuong", "chi_tiet", "ip_nguoi_lam", "ket_qua"])
    for r in rows:
        w.writerow([time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(r["ts"])), r["type"], r["ip"],
                    r["detail"] or r["reason"], r["actor_ip"], r["result"]])
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="evil2ban-audit.csv"'})


# ---------------- ten mien (DomainGate) ----------------
@app.get("/api/domains")
def domains():
    return {"domains": C.domains.list()}


@app.get("/api/domains/detail")
def domain_detail(domain: str):
    return C.domains.detail(domain)


@app.post("/api/domains/mode")
def domain_mode(r: ModeReq, request: Request):
    return {"ok": True, "mode": C.domains.set_mode(r.domain, r.mode, actor_ip(request))}


@app.post("/api/domains/threshold")
def domain_threshold(r: ThresholdReq, request: Request):
    return {"ok": True, "threshold": C.domains.set_threshold(r.domain, r.threshold, actor_ip(request))}


# ---------------- chong DDoS ----------------
@app.get("/api/ddos")
def ddos(request: Request):
    s, me = C.ddos.snapshot(), actor_ip(request)
    s["top"] = [{**t, "me": t["ip"] == me} for t in s["top"]]     # khong de nguoi dung tu chan minh
    return s


@app.post("/api/ddos/apply")
def ddos_apply(r: DdosReq, request: Request):
    changes, errs = C.ddos.apply(r.layers, r.th, actor_ip(request))
    if errs:
        return JSONResponse({"detail": "Áp dụng lỗi, đã trả lại như cũ: " + "; ".join(errs)[:400],
                             "code": "ddos_apply_failed"}, status_code=500)
    return {"ok": True, "changes": changes, "pending": C.shield.pending()}


@app.post("/api/ddos/recommended")
def ddos_recommended(request: Request):
    changes, errs = C.ddos.recommended(actor_ip(request))
    if errs:
        return JSONResponse({"detail": "Áp dụng lỗi, đã trả lại như cũ: " + "; ".join(errs)[:400],
                             "code": "ddos_apply_failed"}, status_code=500)
    return {"ok": True, "changes": changes, "pending": C.shield.pending()}


@app.post("/api/ddos/confirm")
def ddos_confirm(request: Request):
    return {"ok": True, "changes": C.ddos.confirm(actor_ip(request)) or []}


@app.post("/api/ddos/revert")
def ddos_revert(request: Request):
    return {"ok": C.ddos.revert(actor_ip(request))}


# ---------------- whitelist ----------------
@app.get("/api/whitelist")
def whitelist():
    return {"entries": C.whitelist.all()}


@app.post("/api/whitelist/add")
def wl_add(r: WLReq, request: Request):
    try:
        C.whitelist.add(r.entry, source="owner", note=r.note)
    except ValueError:
        raise InvalidInput("IP hoặc CIDR không hợp lệ.", "invalid_ip")
    C.events.add("whitelist-add", r.entry, detail=r.note, actor_ip=actor_ip(request))
    return {"ok": True}


@app.post("/api/whitelist/remove")
def wl_remove(r: WLReq, request: Request):
    if C.whitelist.remove(r.entry) == 0:
        raise InvalidInput("Không xoá được: mục không tồn tại hoặc do hệ thống tạo.", "wl_not_removable")
    C.events.add("whitelist-remove", r.entry, actor_ip=actor_ip(request))
    return {"ok": True}


# ---------------- series ----------------
@app.get("/api/series/daily")
def series_daily(days: int = 30, metric: str = "requests"):
    return C.samples.daily(days=days, metric=metric)


@app.get("/api/series/monthly")
def series_monthly(months: int = 12, metric: str = "requests"):
    return C.samples.monthly(months=months, metric=metric)


# ---------------- ban / unban ----------------
@app.post("/api/ban")
def ban(r: IPReq, request: Request):
    ok, out = C.ban_service.ban(r.ip, actor_ip=actor_ip(request))
    C.sync_webgate()
    return {"ok": ok, "ip": r.ip, "result": out}


@app.post("/api/ban-bulk")
def ban_bulk(r: IPsReq, request: Request):
    res = C.ban_service.ban_many(r.ips, actor_ip=actor_ip(request))
    C.sync_webgate()
    return {"results": res}


@app.post("/api/unban")
def unban(r: IPReq, request: Request):
    ok, out = C.ban_service.unban(r.ip, actor_ip=actor_ip(request))
    C.sync_webgate()
    return {"ok": ok, "ip": r.ip, "result": out}


@app.post("/api/unban-bulk")
def unban_bulk(r: IPsReq, request: Request):
    res = C.ban_service.unban_many(r.ips, actor_ip=actor_ip(request))
    C.sync_webgate()
    return {"results": res}


@app.get("/api/health")
def health():
    return {"ok": True, "version": __version__}


# ---------------- vong nen ----------------
def _sampler_loop():
    try:
        C.stats.backfill_once()
    except Exception:  # noqa: BLE001
        pass
    last_prune = 0
    while True:
        try:
            C.stats.sample_once()
            C.sessions.purge()
            if time.time() - last_prune > 86400:
                C.events.prune(C.settings.get_int("audit.keep_days", default=90))
                last_prune = time.time()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(60)


def _autoban_loop():
    """Luon chay; doc cai dat moi vong nen bat/tat Auto-ban tren WebUI co hieu luc ngay."""
    while True:
        try:
            if C.autoban:
                policy = C.autoban_policy
                for s in C.analyzer.analyze()["suspects"]:
                    if policy.should_ban(s):
                        try:
                            C.ban_service.ban(s["ip"], reason="auto")
                        except BanRejected:
                            pass
            if "chan" in C.domains.modes().values():
                C.domains.enforce(C.ban_service, [b["ip"] for b in C.analysis.banned().banned])
            C.sync_webgate()          # ca IP fail2ban tu chan (sshd) cung bi chan o tang web
        except Exception:  # noqa: BLE001
            pass
        time.sleep(60)


@app.on_event("startup")
def _start():
    threading.Thread(target=_sampler_loop, daemon=True).start()
    threading.Thread(target=_autoban_loop, daemon=True).start()
    threading.Thread(target=C.ratewatch.run_forever, daemon=True).start()
    threading.Thread(target=C.ddos.run_forever, daemon=True).start()


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="ui")
