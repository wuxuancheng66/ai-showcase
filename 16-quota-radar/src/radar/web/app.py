"""FastAPI 应用入口。健康检查 + 生命周期管理（种子同步、调度器启停）。"""

import base64
import binascii
import logging
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from radar import __version__
from radar.config import get_settings
from radar.db import connect, init_db, now_iso

log = logging.getLogger("radar.web")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    conn = connect()
    try:
        from radar.core.seeder import run_seeders
        run_seeders(conn)
        conn.execute(
            "INSERT INTO kv(key,value) VALUES('startup_at',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (now_iso(),),
        )
        conn.commit()
    finally:
        conn.close()

    from radar.scheduler.jobs import start_scheduler, stop_scheduler
    scheduler = start_scheduler()
    _app.state.scheduler = scheduler
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(title="QuotaRadar", version=__version__, lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(get_settings().allowed_hosts))

from fastapi.staticfiles import StaticFiles

from radar.web.api import router as api_router
from radar.web.views import router as views_router
from radar.web.free_rank_view import router as free_rank_router
from radar.web.manage_view import router as manage_router
from radar.web.agents_view import router as agents_router
from radar.web.daily_view import router as daily_router
from radar.web.system_view import api_router as system_api_router
from radar.web.system_view import router as system_router

app.include_router(api_router)
app.include_router(views_router)
app.include_router(free_rank_router)
app.include_router(manage_router)
app.include_router(agents_router)
app.include_router(daily_router)
app.include_router(system_api_router)
app.include_router(system_router)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

_PUBLIC_PATHS = {"/health", "/health/live", "/health/ready"}


def _authorized(request: Request) -> bool:
    settings = get_settings()
    if not settings.auth_enabled:
        return True
    raw = request.headers.get("authorization", "")
    if not raw.lower().startswith("basic "):
        return False
    try:
        decoded = base64.b64decode(raw.split(" ", 1)[1], validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return False
    username, separator, password = decoded.partition(":")
    if not separator:
        return False
    return secrets.compare_digest(username, settings.admin_username) and secrets.compare_digest(
        password, settings.admin_password
    )


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", "")[:128] or uuid.uuid4().hex
    started = time.monotonic()
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 1_048_576:
                response = JSONResponse({"detail": "请求体超过 1 MiB 限制"}, status_code=413)
            else:
                response = None
        except ValueError:
            response = JSONResponse({"detail": "无效的 Content-Length"}, status_code=400)
    else:
        response = None

    if response is None and request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        host = request.headers.get("host", "")
        fetch_site = request.headers.get("sec-fetch-site", "")
        if fetch_site == "cross-site" or (origin and urlsplit(origin).netloc != host):
            response = JSONResponse({"detail": "拒绝跨站状态变更请求"}, status_code=403)

    if response is None and request.url.path not in _PUBLIC_PATHS and not request.url.path.startswith("/static/"):
        if not _authorized(request):
            response = JSONResponse(
                {"detail": "需要管理员认证"},
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="QuotaRadar", charset="UTF-8"'},
            )
        else:
            response = await call_next(request)
    elif response is None:
        response = await call_next(request)

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'; "
        "img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; connect-src 'self'"
    )
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    log.info(
        "request_id=%s method=%s path=%s status=%d duration_ms=%d",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        int((time.monotonic() - started) * 1000),
    )
    return response


@app.get("/health/live")
def health_live():
    return {"status": "ok", "version": __version__}


@app.get("/health/ready")
def health_ready(request: Request):
    conn = connect()
    try:
        from radar.ops import build_status
        payload = build_status(conn, getattr(request.app.state, "scheduler", None))
    finally:
        conn.close()
    return JSONResponse(payload, status_code=200 if payload["ready"] else 503)


@app.get("/health")
def health(request: Request):
    settings = get_settings()
    conn = connect()
    try:
        from radar.ops import build_status
        status = build_status(conn, getattr(request.app.state, "scheduler", None))
        from radar.monitoring import summary
        monitor = summary(conn)
    finally:
        conn.close()
    payload = {
        **status,
        "status": "ok" if status["ready"] else "error",
        "notify_mode": settings.notify_mode,
        "version": __version__,
        "models": status["checks"]["models"]["count"],
        "channels": status["checks"]["channels"]["count"],
        "last_collect_at": status["checks"]["collection"]["last_at"],
        "last_jobs": {
            f"last_job_{job['job_name']}": (
                f"{job.get('last_finished_at') or job.get('last_started_at') or ''} "
                f"{'ERROR' if job.get('status') == 'error' else job.get('status') or 'unknown'}"
            ).strip()
            for job in status["jobs"]
        },
        "monitor": monitor,
    }
    return JSONResponse(payload, status_code=200 if status["ready"] else 503)
