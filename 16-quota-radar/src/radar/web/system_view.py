"""系统状态与运维页面。"""

import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from radar.backup import BACKUP_DIR, create_backup
from radar.ops import build_status
from radar.web.deps import get_db

router = APIRouter()
api_router = APIRouter(prefix="/api/v1/system", tags=["system"])
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
_backup_lock = threading.Lock()


def _human_bytes(value: int | None) -> str:
    size = float(value or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _human_age(seconds: int | None) -> str:
    if seconds is None:
        return "等待首个数据点"
    if seconds < 60:
        return f"{seconds} 秒前"
    if seconds < 3600:
        return f"{seconds // 60} 分钟前"
    if seconds < 86400:
        return f"{seconds // 3600} 小时前"
    return f"{seconds // 86400} 天前"


def _page_context(conn, scheduler) -> dict:
    status = build_status(conn, scheduler)
    status["database"]["size_human"] = _human_bytes(status["database"]["size_bytes"])
    status["uptime_human"] = _human_age(status["uptime_seconds"])
    status["collection_age_human"] = _human_age(status["checks"]["collection"]["age_seconds"])
    for backup in status["backups"]:
        backup["size_human"] = _human_bytes(backup.get("size_bytes"))
    return status


@router.get("/system", response_class=HTMLResponse)
def system_page(request: Request, conn=Depends(get_db)):
    status = _page_context(conn, getattr(request.app.state, "scheduler", None))
    return templates.TemplateResponse(request, "system.html", {"status": status})


@router.post("/system/backup")
def system_backup_form(conn=Depends(get_db)):
    if not _backup_lock.acquire(blocking=False):
        raise HTTPException(409, "已有备份任务正在执行")
    try:
        create_backup(conn, note="manual")
    except (OSError, RuntimeError) as exc:
        raise HTTPException(500, f"备份失败: {type(exc).__name__}") from exc
    finally:
        _backup_lock.release()
    return RedirectResponse("/system", status_code=303)


@api_router.get("/status")
def system_status(request: Request, conn=Depends(get_db)):
    return _page_context(conn, getattr(request.app.state, "scheduler", None))


@api_router.post("/integrity")
def system_integrity(conn=Depends(get_db)):
    row = conn.execute("PRAGMA integrity_check(1)").fetchone()
    result = row[0] if row else "empty result"
    return {"ok": result == "ok", "integrity": result}


@api_router.post("/backup")
def system_backup(conn=Depends(get_db)):
    if not _backup_lock.acquire(blocking=False):
        raise HTTPException(409, "已有备份任务正在执行")
    try:
        backup = create_backup(conn, note="manual")
    except (OSError, RuntimeError) as exc:
        raise HTTPException(500, f"备份失败: {type(exc).__name__}") from exc
    finally:
        _backup_lock.release()
    return {"ok": True, "backup": backup, "backup_dir": str(BACKUP_DIR)}
