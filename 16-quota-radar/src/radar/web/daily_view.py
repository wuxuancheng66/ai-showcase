"""AI 日报页：列出已生成的日报 + 最新一期预览。"""

import os
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from radar.config import OUTPUTS_DIR, get_settings
from radar.db import connect
from radar.web.deps import get_db

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def _report_dir() -> Path:
    return Path(os.environ.get("QR_REPORT_DIR", str(Path.home() / "Documents" / "AI_Daily_Reports")))


def _safe_report_path(path: Path) -> Path | None:
    try:
        base = _report_dir().resolve(strict=True)
        candidate = path.resolve(strict=True)
    except OSError:
        return None
    if candidate.parent != base or candidate.suffix.lower() != ".html" or not candidate.is_file():
        return None
    return candidate


def _latest_report() -> Path | None:
    d = _report_dir()
    if d.is_dir():
        files = sorted(d.glob("AI日报_*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in files:
            safe = _safe_report_path(path)
            if safe:
                return safe
    fallback = OUTPUTS_DIR / "ai_daily_latest.html"
    return fallback if fallback.exists() and not fallback.is_symlink() else None


@router.get("/daily", response_class=HTMLResponse)
def daily_page(request: Request, conn=Depends(get_db)):
    files = []
    d = _report_dir()
    if d.is_dir():
        files = sorted({f.name for f in d.glob("AI日报_*.html")}, reverse=True)[:30]
    latest = _latest_report()
    items = conn.execute("SELECT value FROM kv WHERE key='ai_daily_items'").fetchone()
    return templates.TemplateResponse(request, "daily.html", {
        "files": files, "latest_exists": bool(latest and latest.exists()),
        "items": items["value"] if items else None,
        "generated_at": (conn.execute("SELECT value FROM kv WHERE key='ai_daily_at'").fetchone() or {"value": ""})["value"],
        "report_version": int(time.time()),
    })


@router.get("/daily/latest")
def daily_latest():
    latest = _latest_report()
    if latest:
        return HTMLResponse(
            latest.read_text(encoding="utf-8"),
            headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"},
        )
    return RedirectResponse("/daily")


@router.get("/daily/file/{name}")
def daily_file(name: str):
    # 防路径穿越：只允许白名单文件名
    if not name.startswith("AI日报_") or not name.endswith(".html") or Path(name).name != name:
        return RedirectResponse("/daily")
    f = _safe_report_path(_report_dir() / name)
    if not f:
        return RedirectResponse("/daily")
    return HTMLResponse(
        f.read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"},
    )
