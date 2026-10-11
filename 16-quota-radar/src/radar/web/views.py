"""页面视图（Jinja2 服务端渲染）。"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from radar.claimer.monitor import mark_done
from radar.core.evaluator import recommend
from radar.web.deps import get_db

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

_KIND_BADGE = {
    "price_drop": "降价", "price_rise": "涨价", "new_model": "新模型",
    "new_free_model": "新免费", "free_removed": "免费取消", "context_change": "上下文",
    "price_unknown": "价格未知", "price_available": "价格恢复",
    "channel_status": "渠道", "source_error": "源故障", "source_recovered": "源恢复",
    "activity": "活动", "claim_blocked": "转人工",
}


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, conn=Depends(get_db)):
    from radar.monitoring import refresh_local, summary
    refresh_local(conn)
    monitor = summary(conn)
    stats = {
        "models": conn.execute("SELECT COUNT(*) c FROM models").fetchone()["c"],
        "free": conn.execute("SELECT COUNT(*) c FROM models WHERE free=1").fetchone()["c"],
        "channels_ok": conn.execute(
            "SELECT COUNT(*) c FROM channels WHERE status='ok'").fetchone()["c"],
        "changes_today": conn.execute(
            "SELECT COUNT(*) c FROM changes WHERE created_at>=?",
            ((datetime.now().astimezone() - timedelta(days=1)).isoformat(timespec="seconds"),),
        ).fetchone()["c"],
        "last_collect": conn.execute(
            "SELECT value FROM kv WHERE key='last_collect_at'").fetchone(),
    }
    recs = {s: recommend(conn, s, top_n=5 if s != "bulk" else 3) for s in ("free", "chat", "bulk")}
    local_row = conn.execute("SELECT value FROM kv WHERE key='local_scan'").fetchone()
    local_platforms = list(json.loads(local_row["value"]).keys()) if local_row else []
    recent_changes = conn.execute(
        "SELECT * FROM changes ORDER BY id DESC LIMIT 8").fetchall()
    pending = conn.execute(
        "SELECT * FROM activities WHERE status='pending' ORDER BY id LIMIT 8").fetchall()
    pending_count = conn.execute(
        "SELECT COUNT(*) c FROM activities WHERE status='pending'").fetchone()["c"]
    return templates.TemplateResponse(request, "dashboard.html", {
        "stats": stats, "recs": recs, "recent_changes": recent_changes,
        "pending": pending, "badge": _KIND_BADGE, "now": time.strftime("%Y-%m-%d %H:%M"),
        "local_platforms": local_platforms, "monitor": monitor, "pending_count": pending_count,
    })


@router.get("/recommend", response_class=HTMLResponse)
def recommend_page(request: Request, scenario: str = "chat", conn=Depends(get_db)):
    from radar.core.evaluator import SCENARIOS
    if scenario not in SCENARIOS:
        scenario = "chat"
    rows = recommend(conn, scenario, top_n=15)
    return templates.TemplateResponse(request, "recommend.html", {
        "scenario": scenario, "scenarios": SCENARIOS, "rows": rows,
    })


@router.get("/channels", response_class=HTMLResponse)
def channels_page(request: Request, conn=Depends(get_db)):
    rows = conn.execute(
        "SELECT * FROM channels ORDER BY status='ok' DESC, status='limited' DESC, tier, name").fetchall()
    return templates.TemplateResponse(request, "channels.html", {"rows": rows})


@router.get("/activities", response_class=HTMLResponse)
def activities_page(request: Request, conn=Depends(get_db)):
    pending = conn.execute("SELECT * FROM activities WHERE status='pending' ORDER BY id").fetchall()
    done = conn.execute(
        "SELECT * FROM activities WHERE status='done' ORDER BY done_at DESC LIMIT 20").fetchall()
    return templates.TemplateResponse(request, "activities.html", {"pending": pending, "done": done})


@router.post("/activities/{activity_id}/done")
def activity_done_form(activity_id: str, conn=Depends(get_db)):
    mark_done(conn, activity_id)
    return RedirectResponse("/activities", status_code=303)


@router.post("/run/collect")
def run_collect_form(background: BackgroundTasks):
    """页面上的「立即采集」按钮：后台跑一轮后回看板。"""
    def _run():
        from radar.collectors.runner import run_collection
        from radar.db import connect as _c
        conn = _c()
        try:
            run_collection(conn)
        finally:
            conn.close()

    background.add_task(_run)
    return RedirectResponse("/", status_code=303)


@router.get("/changes", response_class=HTMLResponse)
def changes_page(request: Request, conn=Depends(get_db)):
    rows = conn.execute("SELECT * FROM changes ORDER BY id DESC LIMIT 100").fetchall()
    return templates.TemplateResponse(request, "changes.html", {
        "rows": rows, "badge": _KIND_BADGE,
    })
