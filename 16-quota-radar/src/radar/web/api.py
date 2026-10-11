"""REST API（/api/v1）。"""

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from radar import __version__
from radar.agent_catalog import get_agent as catalog_get_agent
from radar.agent_catalog import list_agents as catalog_list_agents
from radar.config import get_settings
from radar.core import ledger
from radar.core.evaluator import SCENARIOS, recommend
from radar.claimer.monitor import mark_done
from radar.db import now_iso
from radar.web.deps import get_db

log = logging.getLogger("radar.api")

router = APIRouter(prefix="/api/v1")

_ID_PATTERN = r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}$"
_MODEL_PATTERN = r"^[a-zA-Z0-9][a-zA-Z0-9._:/@+-]{0,199}$"


@router.get("/models")
def list_models(free: bool | None = None, provider: str | None = None,
                q: str | None = None, limit: int = 50, conn=Depends(get_db)):
    sql = "SELECT * FROM models WHERE 1=1"
    args: list = []
    if free is not None:
        sql += " AND free=?"
        args.append(1 if free else 0)
    if provider:
        sql += " AND provider LIKE ?"
        args.append(f"%{provider}%")
    if q:
        sql += " AND (model_id LIKE ? OR display_name LIKE ?)"
        args.extend([f"%{q}%", f"%{q}%"])
    sql += " ORDER BY capability_score DESC, input_price ASC LIMIT ?"
    args.append(min(max(limit, 1), 500))
    rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    return {"count": len(rows), "models": rows}


@router.get("/recommend")
def recommend_api(scenario: str = "chat", top: int = 3, conn=Depends(get_db)):
    if scenario not in SCENARIOS:
        raise HTTPException(400, f"scenario 必须是 {'/'.join(SCENARIOS)}")
    return {"scenario": scenario, "top": recommend(conn, scenario, top_n=min(max(top, 1), 20))}


@router.get("/channels")
def channels_api(conn=Depends(get_db)):
    rows = [dict(r) for r in conn.execute(
        "SELECT id,name,provider,tier,url,kind,status,last_checked,last_ok,free_tier_desc,note "
        "FROM channels ORDER BY status='ok' DESC, tier, name")]
    return {"count": len(rows), "channels": rows}


@router.get("/changes")
def changes_api(limit: int = 50, kind: str | None = None, conn=Depends(get_db)):
    sql = "SELECT * FROM changes"
    args: list = []
    if kind:
        sql += " WHERE kind=?"
        args.append(kind)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(min(max(limit, 1), 500))
    rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    return {"count": len(rows), "changes": rows}


@router.get("/activities")
def activities_api(conn=Depends(get_db)):
    rows = [dict(r) for r in conn.execute("SELECT * FROM activities ORDER BY status, id")]
    return {"count": len(rows), "activities": rows}


@router.post("/activities/{activity_id}/done")
def activity_done(activity_id: str, conn=Depends(get_db)):
    if not mark_done(conn, activity_id):
        raise HTTPException(404, "活动不存在")
    return {"ok": True, "id": activity_id}


@router.get("/usage")
def usage_api(channel_id: str | None = None, conn=Depends(get_db)):
    return {
        "overall": ledger.forecast(conn, None),
        "channel": ledger.forecast(conn, channel_id) if channel_id else None,
        "recent": [dict(r) for r in conn.execute(
            "SELECT * FROM usage_log ORDER BY id DESC LIMIT 20")],
    }


class UsageIn(BaseModel):
    tokens: int = Field(ge=-1_000_000_000_000, le=1_000_000_000_000)
    channel_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    model_key: str | None = Field(default=None, max_length=250)
    note: str | None = Field(default=None, max_length=500)


class DeployIn(BaseModel):
    channel_id: str = Field(pattern=_ID_PATTERN)
    model_id: str = Field(pattern=_MODEL_PATTERN)
    agent: str = Field(default="openclaw", pattern=_ID_PATTERN)
    set_default: bool = False
    allow_install: bool = False
    context_window: int = Field(default=131072, ge=1024, le=2_000_000)


class ProbeIn(BaseModel):
    channel_id: str = Field(pattern=_ID_PATTERN)


class RestartIn(BaseModel):
    agent: str | None = Field(default=None, pattern=_ID_PATTERN)


class AgentTaskIn(BaseModel):
    agent_id: str = Field(pattern=_ID_PATTERN)
    channel_id: str = Field(pattern=_ID_PATTERN)
    model_id: str = Field(pattern=_MODEL_PATTERN)
    allow_install: bool = False


@router.post("/usage")
def usage_record(body: UsageIn, conn=Depends(get_db)):
    try:
        row_id = ledger.record(conn, body.tokens, body.channel_id, body.model_key, body.note)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return {"ok": True, "id": row_id, "balance": ledger.balance(conn, body.channel_id)}


@router.post("/run/collect")
def run_collect(background: BackgroundTasks):
    def _run():
        from radar.collectors.runner import run_collection
        from radar.db import connect as _c
        conn = _c()
        try:
            run_collection(conn)
        finally:
            conn.close()

    background.add_task(_run)
    return {"ok": True, "message": "采集任务已在后台启动，约 10-30 秒后刷新查看"}


@router.get("/free-rank")
def free_rank_api(conn=Depends(get_db)):
    """免费渠道综合排行（能力/可达/限速/稳定/上手 五维加权）。"""
    from radar.config import get_settings
    from radar.core.free_rank import compute_free_rank
    ranked = compute_free_rank(conn, get_settings())
    return {"count": len(ranked), "ranking": ranked}


@router.get("/local")
def local_api(conn=Depends(get_db)):
    """本机平台发现结果（只含变量名与文件位置，永不含密钥值）。"""
    import json

    row = conn.execute("SELECT value FROM kv WHERE key='local_scan'").fetchone()
    scanned_at = conn.execute("SELECT value FROM kv WHERE key='local_scan_at'").fetchone()
    result = json.loads(row["value"]) if row else {}
    return {
        "scanned_at": scanned_at["value"] if scanned_at else None,
        "platforms": [
            {"name": name, **{k: v for k, v in info.items()}}
            for name, info in sorted(result.items())
        ],
    }


@router.get("/deploy/agents")
def deploy_agents(conn=Depends(get_db)):
    """返回统一的本机 Agent 目录与检测状态。"""
    return {"agents": catalog_list_agents(conn)}


@router.post("/agents/{agent_id}/open")
def open_agent(agent_id: str, conn=Depends(get_db)):
    """返回网关地址，或下发仅允许目录内应用打开的安全动作。"""
    from radar.deploy import planner
    agent = catalog_get_agent(agent_id, conn)
    if not agent:
        raise HTTPException(404, "未知 Agent")
    if not agent.get("detected"):
        raise HTTPException(409, f"未检测到 {agent['name']}")
    mode = agent.get("open_mode")
    if mode == "gateway" and agent.get("gateway_url"):
        return {"ok": True, "mode": "url", "url": agent["gateway_url"]}
    if mode == "app" and agent.get("app_name"):
        plan = planner.enqueue(agent_id, "system", "system", "open-app",
                               requires_allowlist=False)
        p = planner.QUEUE_DIR / f"{plan['id']}.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data.update({"action": "open_app", "app_name": agent["app_name"]})
        planner._write_plan(data)
        return {"ok": True, "mode": "queued", "plan_id": plan["id"],
                "message": f"已下发启动 {agent['name']} 的指令，约 15 秒内打开"}
    if mode == "cli" and agent.get("cli"):
        return {"ok": True, "mode": "command", "command": agent["cli"],
                "message": f"请在终端运行：{agent['cli']}"}
    return {"ok": True, "mode": "manual", "detail_url": f"/agents/{agent_id}"}


@router.post("/deploy/agent-task")
def deploy_agent_task(body: AgentTaskIn, conn=Depends(get_db)):
    """把无法直接配置的渠道交给具备电脑操作能力的 Agent 接管。"""
    from radar.deploy import planner
    if body.allow_install and not get_settings().allow_web_install:
        raise HTTPException(403, "Web 端自动安装默认关闭；请显式设置 QR_ALLOW_WEB_INSTALL=1")
    agent = catalog_get_agent(body.agent_id, conn)
    if not agent or not agent.get("task_runner"):
        raise HTTPException(422, "该 Agent 不支持安全的接管任务")
    if not agent.get("detected") and not body.allow_install:
        raise HTTPException(409, "Agent 未安装；请勾选允许自动安装或先手动安装")
    if not agent.get("computer_control") or not agent.get("plugin_capable"):
        raise HTTPException(422, "该 Agent 不具备电脑操作与插件扩展能力")
    row = conn.execute("SELECT * FROM channels WHERE id=?", (body.channel_id,)).fetchone()
    if not row:
        raise HTTPException(404, "渠道不存在")
    channel = dict(row)
    model_id = body.model_id.strip()
    if not model_id:
        raise HTTPException(422, "模型 ID 不能为空")
    prompt = (
        "你是 QuotaRadar 的本地部署代理。请在用户自己的电脑上完成以下安全任务。\n"
        f"1. 打开官方页面：{channel.get('url') or '未提供'}\n"
        f"2. 检查渠道 {channel.get('name')} 当前已有登录状态、免费额度与可用于电脑操作的模型。\n"
        f"3. 优先把模型 {model_id} 配置到 {agent['name']}，使其可用于本机电脑操作与插件技能。\n"
        "4. 只使用已有登录态或用户主动提供的官方配置；不要索取、打印、保存密码、验证码、API Key 或付款信息。\n"
        "5. 遇到验证码、风控、付款、订阅、条款确认或权限提升时立即停止，并明确告诉用户需要手动完成什么。\n"
        "6. 不要绕过任何平台限制或安全机制。完成后简要报告配置结果、验证方式和仍需用户处理的事项。"
    )
    plan = planner.enqueue(
        agent=body.agent_id,
        channel_id=body.channel_id,
        provider=channel.get("provider") or "custom",
        model_id=model_id,
        requires_allowlist=False,
    )
    plan.update({
        "action": "agent_deploy_task",
        "prompt": prompt,
        "allow_install": body.allow_install,
    })
    planner._write_plan(plan)
    return {"ok": True, "plan_id": plan["id"], "agent": agent["name"],
            "message": f"已交给 {agent['name']}，执行进度会在部署状态中更新"}


@router.post("/deploy")
def deploy_enqueue(body: DeployIn, conn=Depends(get_db)):
    """入队一份部署计划；仅接受具备 provider 或完整兼容接口的渠道。"""
    from radar.core.seeder import sync_channels
    from radar.deploy import planner

    if body.allow_install and not get_settings().allow_web_install:
        raise HTTPException(403, "Web 端自动安装默认关闭；请显式设置 QR_ALLOW_WEB_INSTALL=1")
    if body.agent != "openclaw":
        raise HTTPException(422, "直接部署当前仅支持 OpenClaw；其他 Agent 请使用安全接管")

    channel_id = body.channel_id.strip()
    model_id = body.model_id.strip()
    if not channel_id or not model_id:
        raise HTTPException(422, "channel_id 与 model_id 必填")

    sync_channels(conn)  # 确保 yaml 最新（含 base_url 等部署字段）
    row = conn.execute("SELECT * FROM channels WHERE id=?", (channel_id,)).fetchone()
    if not row:
        raise HTTPException(404, f"渠道不存在: {channel_id}")
    ch = dict(row)

    agent_id = body.agent
    agent = planner.get_agent(agent_id)
    if not agent or not agent.get("enabled"):
        raise HTTPException(400, f"agent 不可用: {agent_id}")

    from radar.deploy.detect import detect_agents
    info = next((a for a in detect_agents() if a["id"] == agent_id), {})
    has_key = bool(get_settings().api_key(ch.get("env_key") or ""))
    target = planner.deployment_target(ch, info, has_key)
    if not target["ready"]:
        raise HTTPException(422, target["reason"])

    plan = planner.enqueue(
        agent=agent_id,
        channel_id=channel_id,
        provider=target["provider"],
        model_id=model_id,
        set_default=body.set_default,
        base_url=target["base_url"],
        api_key_env=target.get("api_key_env"),
        context_window=max(1024, min(body.context_window, 2_000_000)),
        requires_allowlist=bool(agent.get("deploy", {}).get("requires_allowlist", True)),
    )
    if body.allow_install:
        plan["allow_install"] = True
        planner._write_plan(plan)
    return {"ok": True, "plan_id": plan["id"], "queue_file": plan["queue_file"],
            "agent": {"id": agent_id, "detected": info.get("detected", False)}}


@router.get("/deploy/status/{plan_id}")
def deploy_status(plan_id: str, conn=Depends(get_db)):
    from radar.deploy import planner
    plan = planner.read_plan(plan_id)
    if not plan:
        raise HTTPException(404, "计划不存在")
    result = plan.get("result") or {}
    # 验证通过 → 自动入册 configured_models（幂等）
    if result.get("verified"):
        exists = conn.execute(
            "SELECT 1 FROM configured_models WHERE agent=? AND provider=? AND model_id=?",
            (plan["agent"], plan["provider"], plan["model_id"])).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO configured_models(agent,channel_id,provider,model_id,base_url,"
                "set_default,verified,verify_detail,deployed_at,verified_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (plan["agent"], plan.get("channel_id"), plan["provider"], plan["model_id"],
                 plan.get("base_url"), 1 if plan.get("set_default") else 0, 1,
                 result.get("detail"), plan.get("created_at"), now_iso()))
            conn.commit()
    return {"id": plan_id, "status": plan["status"], "result": result}


@router.get("/deploy/configured")
def deploy_configured(conn=Depends(get_db)):
    from radar.deploy import planner
    planner.register_verified(conn)  # 打开页面即同步队列中已验证的部署
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM configured_models ORDER BY verified_at DESC")]
    return {"count": len(rows), "configured": rows}


@router.get("/manage")
def manage_api(conn=Depends(get_db)):
    """已部署 AI 舰队清单（充值类/免费类）+ 运行管理数据。"""
    from radar.config import get_settings
    from radar.core.fleet import fleet_inventory
    return fleet_inventory(conn, get_settings())


@router.post("/manage/probe")
def manage_probe(body: ProbeIn, conn=Depends(get_db)):
    """单渠道立即探活。"""
    from radar.channels.prober import probe_channel
    from radar.config import get_settings
    cid = body.channel_id
    ch = conn.execute("SELECT * FROM channels WHERE id=?", (cid,)).fetchone()
    if not ch:
        raise HTTPException(404, f"渠道不存在: {cid}")
    status = probe_channel(conn, ch, get_settings().api_key(ch["env_key"] or ""))
    if status is None:
        return {"ok": False, "reason": "该渠道需要 key（未配置）或无探活方式"}
    return {"ok": True, "channel_id": cid, "status": status}


@router.post("/manage/restart")
def manage_restart(body: RestartIn, conn=Depends(get_db)):
    """通过宿主执行器重启 OpenClaw 网关。"""
    from radar.deploy import planner
    if body.agent not in (None, "openclaw"):
        raise HTTPException(400, "仅支持 openclaw")
    plan = planner.enqueue("openclaw", "nvidia-nim", "nvidia", "-", set_default=False)
    # 转成运维动作
    p = planner.QUEUE_DIR / f"{plan['id']}.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data["action"] = "restart_gateway"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "plan_id": plan["id"], "message": "重启指令已下发宿主执行器"}


@router.post("/daily/generate")
def daily_generate(conn=Depends(get_db)):
    """立即生成一期 AI 日报（新闻源 + 本机雷达数据）。"""
    from radar.daily.report import generate_daily
    result = generate_daily(conn)
    return {"ok": True, **result}


@router.get("/meta")
def meta():
    return {"name": "QuotaRadar", "version": __version__, "scenarios": list(SCENARIOS)}
