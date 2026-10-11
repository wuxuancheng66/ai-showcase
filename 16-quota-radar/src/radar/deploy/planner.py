"""部署规划器：把「渠道+模型」变成一份可执行的部署计划（补丁 + 步骤）。

雷达（容器）负责规划与入队；真正执行在宿主机执行器（executor/host_executor.py），
它调用 openclaw CLI 完成备份→dry-run→写入→重启→验证，结果回写队列文件。
"""

import json
import os
import re
import time
import uuid
from pathlib import Path

import yaml

from radar.config import CONFIG_DIR, DATA_DIR
from radar.db import now_iso

QUEUE_DIR = DATA_DIR / "deploy_queue"
PROVIDER_ALIASES = {"nvidia-nim": "nvidia"}
_PLAN_ID_RE = re.compile(r"^dep_[0-9]+_[a-f0-9]+$")


def load_agents() -> list[dict]:
    with open(CONFIG_DIR / "agents_registry.yaml", encoding="utf-8") as fh:
        return (yaml.safe_load(fh) or {}).get("agents") or []


def get_agent(agent_id: str) -> dict | None:
    return next((a for a in load_agents() if a["id"] == agent_id), None)


def _value(source, key, default=None):
    if isinstance(source, dict):
        return source.get(key, default)
    try:
        return source[key]
    except (KeyError, TypeError):
        return default


def deployment_target(channel, agent_info: dict | None, has_key: bool) -> dict:
    """判断渠道是否具备可执行的 OpenClaw 部署路径。不读取或返回任何密钥值。"""
    channel_id = _value(channel, "id", "")
    provider = PROVIDER_ALIASES.get(channel_id, _value(channel, "provider", ""))
    providers = {str(p).lower() for p in ((agent_info or {}).get("providers") or [])}
    if provider.lower() in providers:
        return {"ready": True, "provider": provider, "base_url": None,
                "reason": "复用 Agent 中已有的 provider"}

    probe = _value(channel, "probe", {}) or {}
    probe_type = _value(channel, "probe_type") or probe.get("type")
    base_url = _value(channel, "probe_base_url") or probe.get("base_url")
    env_key = _value(channel, "env_key") or ""
    if probe_type != "openai_compatible" or not base_url:
        return {"ready": False, "provider": provider, "base_url": None,
                "reason": "该渠道暂未提供 OpenClaw 兼容接口"}
    if not env_key:
        return {"ready": False, "provider": provider, "base_url": base_url,
                "reason": "该渠道缺少可用的凭证变量配置"}
    if not has_key:
        return {"ready": False, "provider": provider, "base_url": base_url,
                "reason": f"请先在 .env 配置 {env_key}"}
    return {"ready": True, "provider": provider, "base_url": base_url,
            "api_key_env": env_key, "reason": "可新增 OpenAI 兼容 provider"}


def _plan_path(plan_id: str) -> Path | None:
    if not plan_id or not _PLAN_ID_RE.fullmatch(plan_id):
        return None
    return QUEUE_DIR / f"{plan_id}.json"


def _write_plan(plan: dict) -> Path:
    path = QUEUE_DIR / f"{plan['id']}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path


def build_patch(provider: str, model_id: str, set_default: bool,
                base_url: str | None = None, context_window: int = 131072,
                max_tokens: int = 8192, requires_allowlist: bool = True) -> dict:
    """构造 openclaw config patch 载荷。

    provider 已存在（如 nvidia）→ 只补 allowlist 与默认模型，绝不改 provider 本体；
    新 provider → 额外写入 provider 定义（openai-completions 兼容、零成本）。
    """
    patch: dict = {}
    if base_url:
        patch["models"] = {"providers": {
            provider: {
                "baseUrl": base_url,
                "api": "openai-completions",
                "models": [{
                    "id": model_id,
                    "name": model_id,
                    "reasoning": False,
                    "input": ["text"],
                    "cost": {"input": 0, "output": 0},
                    "contextWindow": context_window,
                    "maxTokens": max_tokens,
                }],
            }
        }}
    if requires_allowlist:
        patch.setdefault("agents", {})
        patch["agents"].setdefault("defaults", {})
        patch["agents"]["defaults"].setdefault("modelPolicy", {})
        # allow 是数组：patch 语义为整体替换，执行器会先读现有列表做并集（见 host_executor）
        patch["agents"]["defaults"]["modelPolicy"]["allow"] = [model_id]
    if set_default:
        patch.setdefault("agents", {}).setdefault("defaults", {})
        patch["agents"]["defaults"]["model"] = {"primary": f"{provider}/{model_id}"}
    return patch


def enqueue(agent: str, channel_id: str, provider: str, model_id: str, *,
            set_default: bool = False, base_url: str | None = None,
            api_key_env: str | None = None, context_window: int = 131072,
            requires_allowlist: bool = True) -> dict:
    """入队一份部署计划，返回计划文件信息。队列文件即任务单，执行器消费。"""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    plan = {
        "id": f"dep_{int(time.time())}_{uuid.uuid4().hex[:6]}",
        "agent": agent,
        "channel_id": channel_id,
        "provider": provider,
        "model_id": model_id,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "set_default": set_default,
        "requires_allowlist": requires_allowlist,
        "context_window": context_window,
        "status": "queued",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "result": None,
    }
    path = _write_plan(plan)
    plan["queue_file"] = str(path)
    return plan


def read_plan(plan_id: str) -> dict | None:
    p = _plan_path(plan_id)
    if not p or not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def read_result(plan_id: str) -> dict | None:
    plan = read_plan(plan_id)
    return (plan or {}).get("result")


def register_verified(conn) -> int:
    """扫描队列：验证通过的部署入册 configured_models（幂等）。返回新增数。"""
    if not QUEUE_DIR.exists():
        return 0
    added = 0
    for p in QUEUE_DIR.glob("dep_*.json"):
        if ".patch." in p.name:
            continue
        try:
            plan = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        result = plan.get("result") or {}
        if plan.get("status") != "done" or not result.get("verified"):
            continue
        exists = conn.execute(
            "SELECT 1 FROM configured_models WHERE agent=? AND provider=? AND model_id=?",
            (plan["agent"], plan["provider"], plan["model_id"])).fetchone()
        if exists:
            continue
        conn.execute(
            "INSERT INTO configured_models(agent,channel_id,provider,model_id,base_url,"
            "set_default,verified,verify_detail,deployed_at,verified_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (plan["agent"], plan.get("channel_id"), plan["provider"], plan["model_id"],
             plan.get("base_url"), 1 if plan.get("set_default") else 0, 1,
             result.get("detail"), plan.get("created_at"), now_iso()))
        added += 1
    conn.commit()
    return added
