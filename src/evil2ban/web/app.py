# -*- coding: utf-8 -*-
"""
Tang web (mong) — route goi service. Khong chua logic nghiep vu.
Bind 127.0.0.1 => vao qua SSH tunnel, KHONG phoi ra Internet.
"""
import time
import threading

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import __version__
from ..paths import STATIC_DIR
from ..core.exceptions import BanRejected, AuthError, NotConfigured
from .container import Container

C = Container()
app = FastAPI(title="Evil2Ban", version=__version__, docs_url=None, redoc_url=None)

OPEN_PATHS = ("/api/login", "/api/reset-password", "/api/health")


def _token(request: Request):
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (request.headers.get("x-e2b-token")
            or request.cookies.get("e2b_token")
            or request.query_params.get("token", ""))


@app.middleware("http")
async def auth_mw(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and path not in OPEN_PATHS:
        if not C.auth.valid_token(_token(request)):
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)


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


# ---------------- auth ----------------
@app.post("/api/login")
def login(r: LoginReq):
    try:
        tok = C.auth.login(r.username, r.password)
    except NotConfigured as e:
        raise HTTPException(503, str(e))
    except AuthError as e:
        raise HTTPException(401, str(e))
    return {"ok": True, "token": tok, "username": r.username}


@app.post("/api/reset-password")
def reset_password(r: ResetReq):
    try:
        ok, msg, _ = C.auth.reset_password(r.username)
    except NotConfigured as e:
        raise HTTPException(503, str(e))
    except AuthError as e:
        raise HTTPException(400, str(e))
    C.events.add("reset-password", "", reason="email" if ok else "email-fail", detail=msg)
    if not ok:
        raise HTTPException(500, msg)
    return {"ok": True, "detail": msg}


# ---------------- overview / monitor ----------------
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


@app.get("/api/settings")
def settings():
    return {"settings": C.settings.all(redact=True)}


# ---------------- whitelist ----------------
@app.get("/api/whitelist")
def whitelist():
    return {"entries": C.whitelist.all()}


@app.post("/api/whitelist/add")
def wl_add(r: WLReq):
    try:
        C.whitelist.add(r.entry, source="owner", note=r.note)
    except ValueError:
        raise HTTPException(400, "IP/CIDR khong hop le.")
    C.events.add("whitelist-add", r.entry, detail=r.note)
    return {"ok": True}


@app.post("/api/whitelist/remove")
def wl_remove(r: WLReq):
    if C.whitelist.remove(r.entry) == 0:
        raise HTTPException(400, "Khong xoa duoc (khong ton tai hoac la system).")
    C.events.add("whitelist-remove", r.entry)
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
def ban(r: IPReq):
    try:
        ok, out = C.ban_service.ban(r.ip)
    except BanRejected as e:
        raise HTTPException(400, str(e))
    C.analysis.drop_banned()
    return {"ok": ok, "ip": r.ip, "result": out}


@app.post("/api/ban-bulk")
def ban_bulk(r: IPsReq):
    res = C.ban_service.ban_many(r.ips)
    C.analysis.drop_banned()
    return {"results": res}


@app.post("/api/unban")
def unban(r: IPReq):
    ok, out = C.ban_service.unban(r.ip)
    C.analysis.drop_banned()
    return {"ok": ok, "ip": r.ip, "result": out}


@app.post("/api/unban-bulk")
def unban_bulk(r: IPsReq):
    res = C.ban_service.unban_many(r.ips)
    C.analysis.drop_banned()
    return {"results": res}


@app.get("/api/health")
def health():
    return {"ok": True, "version": __version__}


# ---------------- background loops ----------------
def _sampler_loop():
    try:
        C.stats.backfill_once()
    except Exception:  # noqa: BLE001
        pass
    while True:
        try:
            C.stats.sample_once()
            C.sessions.purge()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(60)


def _autoban_loop():
    while True:
        try:
            a = C.analyzer.analyze()
            for s in a["suspects"]:
                if C.autoban_policy.should_ban(s):
                    try:
                        C.ban_service.ban(s["ip"], reason="auto")
                    except BanRejected:
                        pass
            C.analysis.drop_banned()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(60)


@app.on_event("startup")
def _start():
    threading.Thread(target=_sampler_loop, daemon=True).start()
    if C.autoban:
        threading.Thread(target=_autoban_loop, daemon=True).start()


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="ui")
