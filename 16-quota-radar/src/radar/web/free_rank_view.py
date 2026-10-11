"""免费渠道综合排行页 + 一键部署入口页（M13 补部署对话框）。"""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from radar.agent_catalog import list_agents, match_channel
from radar.config import get_settings
from radar.core.free_rank import compute_free_rank
from radar.db import connect, init_db, kv_get
from radar.web.deps import get_db

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@router.get("/free-rank", response_class=HTMLResponse)
def free_rank_page(request: Request, conn=Depends(get_db)):
    ranked = compute_free_rank(conn, get_settings())
    return templates.TemplateResponse(request, "free_rank.html", {
        "rows": ranked,
    })


@router.get("/deploy", response_class=HTMLResponse)
def deploy_page(request: Request, channel: str | None = None, conn=Depends(get_db)):
    """部署中心：排行 + 已配置模型列表 + 部署对话框。"""
    from radar.monitoring import refresh_local
    refresh_local(conn)
    from radar.core.free_rank import compute_free_rank
    from radar.deploy import planner
    planner.register_verified(conn)  # 打开页面即同步队列中已验证的部署
    settings = get_settings()
    ranked = compute_free_rank(conn, settings)
    configured = [dict(r) for r in conn.execute(
        "SELECT * FROM configured_models ORDER BY verified_at DESC").fetchall()]
    agents = list_agents(conn)
    for row in ranked:
        match = match_channel(row, agents)
        row["recommended_agent"] = match["agent"]
        row["match_reason"] = match["reason"]
        row["auto_match"] = match["automatic"]
    return templates.TemplateResponse(request, "deploy.html", {
        "rows": ranked, "configured": configured, "agents": agents,
        "task_agents": [a for a in agents if a.get("task_runner")],
        "gateway_urls": {a["id"]: a.get("gateway_url") for a in agents},
        "selected_channel": channel if any(r["id"] == channel and r["deploy_ready"] for r in ranked) else None,
        "allow_web_install": settings.allow_web_install,
    })
