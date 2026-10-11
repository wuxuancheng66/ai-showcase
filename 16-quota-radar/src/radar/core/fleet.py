"""已部署 AI 舰队清单：合并渠道/已验证部署/本机应用三路数据，统一出「充值类/免费类」+ 运行管理视图。

billing 分类：free=免费类（免费层/试用/本地），paid=充值类（订阅/充值/按量付费）。
来源优先级：channels.yaml（tier 映射）→ platforms.yaml（billing 字段）→ 默认 free。
diagnose：把探活状态、key 配置、额度预测转成人话诊断 + 修复动作。
"""

import json

from radar.core import ledger
from radar.db import kv_set, now_iso

_STATUS_FACTOR_NOTE = {"ok": "运行正常", "limited": "限流中（免费额度仍在）",
                       "error": "探活异常", "unknown": "尚未探活", "detected": "已检测，未验证额度"}


def _canonical_platform(name: str) -> str | None:
    clean = name.lower().replace(" ", "")
    if "nvidia" in clean and "nim" in clean:
        return "nvidia-nim"
    if "openclaw" in clean:
        return "openclaw"
    return None


def _billing_of_channel(seed: dict) -> str:
    return "free" if seed.get("tier", "free") == "free" else "paid"


def diagnose(entry: dict) -> tuple[str | None, list[str]]:
    """根据条目状态生成（诊断, 修复动作列表）。"""
    status = entry.get("status")
    repairs: list[str] = []
    if entry.get("kind") == "agent":
        if entry.get("status") == "ok":
            return None, ["打开 agent 界面", "重启网关"]
        return "未检测到运行实例，请确认应用已启动", ["启动应用"]
    if status == "error":
        return "探活异常：key 可能失效或服务已变更，建议人工复核", ["重新探活", "检查 .env 中的 key"]
    if status == "limited":
        return "限流中（免费额度仍在），稍后自动恢复", ["稍后重试"]
    if entry.get("requires_key") and not entry.get("has_key"):
        return "未配置 key：先到活动中心领取额度，再把 key 填入 .env 并重启服务", ["查看领取指引", "配置 key 并重启服务"]
    days_left = entry.get("days_left")
    if days_left is not None and days_left < 7:
        return f"⚠️ 按当前消耗约 {days_left} 天后额度耗尽", ["记录每日用量以校准预测", "部署一个免费类模型分流"]
    if status == "detected":
        return "已发现本机应用或登录态，但尚未验证额度与访问状态", ["查看领取指引", "完成记账后可预测额度"]
    if status == "ok":
        return "运行正常", []
    return None, repairs


def _channel_entries(conn, settings, openclaw_channels: set[str],
                     configured_by_channel: dict, metrics: dict) -> list[dict]:
    from radar.core.free_rank import _load_channel_seeds
    entries = []
    for seed in _load_channel_seeds():
        cid = seed["id"]
        row = conn.execute("SELECT * FROM channels WHERE id=?", (cid,)).fetchone()
        row = dict(row) if row else {}
        models = configured_by_channel.get(cid) or []
        has_key = bool(settings.api_key(seed.get("env_key") or ""))
        balance = ledger.balance(conn, cid)
        fc = ledger.forecast(conn, cid)
        entry = {
            "kind": "channel", "id": cid, "name": seed["name"],
            "billing": _billing_of_channel(seed), "type": "api",
            "url": seed.get("url"), "status": row.get("status", "unknown"),
            "last_checked": (row.get("last_checked") or "")[:19],
            "has_key": has_key, "requires_key": bool(seed.get("requires_key")),
            "configured_in_agent": cid in openclaw_channels or bool(seed.get("configured_in_agent")),
            "balance_adapter": cid in {"openrouter-free", "deepseek"},
            "models": [m.get("id") for m in (seed.get("models_offered") or [])],
            "deployed_models": [c["model_id"] for c in models],
            "balance": balance, "days_left": fc.get("days_left"),
            "daily_burn": fc.get("daily_burn"),
        }
        from radar.monitoring import decorate_entry, metric_for
        decorate_entry(entry, metric_for(entry, metrics))
        diag, repairs = diagnose(entry)
        entry["diagnosis"], entry["repairs"] = diag, repairs
        entries.append(entry)
    return entries


def _agent_entries(conn, agent_det: list[dict], metrics: dict) -> list[dict]:
    entries = []
    for a in agent_det:
        balance = ledger.balance(conn, a["id"])
        fc = ledger.forecast(conn, a["id"])
        entry = {
            "kind": "agent", "id": a["id"], "name": a["name"],
            "billing": "free" if a["id"] == "openclaw" else "paid",
            "type": "agent", "url": a.get("gateway_url"),
            "status": "ok" if a.get("detected") else "unknown",
            "balance_adapter": False,
            "last_checked": "", "has_key": a.get("detected", False),
            "requires_key": False, "configured_in_agent": a.get("detected", False),
            "models": a.get("providers", []), "deployed_models": [],
            "balance": balance, "days_left": fc.get("days_left"),
            "daily_burn": fc.get("daily_burn"),
        }
        from radar.monitoring import decorate_entry, metric_for
        decorate_entry(entry, metric_for(entry, metrics))
        diag, repairs = diagnose(entry)
        entry["diagnosis"], entry["repairs"] = diag, repairs
        entries.append(entry)
    return entries


def fleet_inventory(conn, settings) -> dict:
    from radar.core.free_rank import _load_channel_seeds
    from radar.deploy.detect import detect_agents

    agent_det = detect_agents()
    openclaw_channels: set[str] = set()
    for a in agent_det:
        openclaw_channels.update(a.get("configured_channel_ids") or [])

    configured_by_channel: dict[str, list] = {}
    for c in conn.execute("SELECT * FROM configured_models WHERE verified=1").fetchall():
        configured_by_channel.setdefault(dict(c).get("channel_id") or "", []).append(dict(c))

    from radar.monitoring import latest_metrics
    metrics = latest_metrics(conn)
    entries = (_channel_entries(conn, settings, openclaw_channels, configured_by_channel, metrics)
               + _agent_entries(conn, agent_det, metrics))

    # 合并本机扫描层（桌面应用/CLI 登录态），跳过已被渠道覆盖的 env_key，避免重复
    local_raw = conn.execute("SELECT value FROM kv WHERE key='local_scan'").fetchone()
    local = json.loads(local_raw["value"]) if local_raw else {}
    claimed_env = {c.get("env_key", "").upper() for c in _load_channel_seeds() if c.get("env_key")}
    from radar.local_scan import _load_platform_index
    platform_billing = {p["name"]: p.get("billing", "free") for p in _load_platform_index()
                        if p.get("billing")}
    cli_billing = {"Codex CLI": "paid", "Claude Code": "paid", "Cursor": "paid", "ZCode": "paid",
                   "Gemini CLI": "free", "Qwen Code": "free",
                   "gcloud 应用凭证": "free", "VS Code + Claude Code 插件": "paid",
                   "Hermes Agent（终端版）": "free"}
    existing_names = {e["name"] for e in entries}
    existing_ids = {e["id"] for e in entries}
    for name, info in local.items():
        canonical = _canonical_platform(name)
        if name in existing_names or (canonical and canonical in existing_ids):
            continue
        if info.get("env_key") and info["env_key"].upper() in claimed_env:
            continue  # 该平台已有渠道条目，避免重复
        kind = "app" if info.get("vars") == ["<桌面应用>"] else "cli"
        balance = ledger.balance(conn, name)
        fc = ledger.forecast(conn, name)
        entry = {
            "kind": kind, "id": name, "name": name,
            "billing": cli_billing.get(name) or platform_billing.get(name) or "free",
            "type": "app", "url": info.get("claim"), "status": "detected",
            "balance_adapter": False, "last_checked": "", "has_key": info.get("vars") != ["<桌面应用>"], "requires_key": False,
            "configured_in_agent": False, "models": [], "deployed_models": [],
            "balance": balance, "days_left": fc.get("days_left"), "daily_burn": None,
        }
        from radar.monitoring import decorate_entry, metric_for
        decorate_entry(entry, metric_for(entry, metrics))
        diag, repairs = diagnose(entry)
        entry["diagnosis"], entry["repairs"] = diag, repairs
        entries.append(entry)
        existing_names.add(name)

    inventory = {
        "paid": sorted([e for e in entries if e["billing"] == "paid"], key=lambda x: x["name"]),
        "free": sorted([e for e in entries if e["billing"] == "free"], key=lambda x: x["name"]),
        "updated_at": now_iso(),
    }
    kv_set(conn, "fleet", json.dumps(inventory, ensure_ascii=False))
    return inventory
