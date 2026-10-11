"""本机 Agent 统一目录：部署检测、本地扫描、运行入口与能力评分共用一份数据。"""

import json
from pathlib import Path

from radar.db import now_iso


AGENT_SPECS = [
    {
        "id": "openclaw",
        "name": "OpenClaw",
        "aliases": ["OpenClaw", "OpenClaw（NVIDIA agent）"],
        "app_name": "OpenClaw",
        "gateway_url": "http://localhost:18790",
        "manual_key": "openclaw",
        "kind": "gateway-agent",
        "computer_control": True,
        "plugin_capable": True,
        "ecosystem_score": 100,
        "deploy_adapter": "openclaw_config_patch",
        "task_runner": True,
        "install_cmd": "npm install -g openclaw@latest",
        "capabilities": ["exec", "browser", "computer", "skills", "plugins"],
    },
    {
        "id": "hermes",
        "name": "Hermes Agent",
        "aliases": ["Hermes Agent（终端版）", "Hermes Agent"],
        "cli": "hermes",
        "manual_key": "hermes",
        "kind": "terminal-agent",
        "computer_control": True,
        "plugin_capable": True,
        "ecosystem_score": 94,
        "deploy_adapter": "manual",
        "task_runner": True,
        "install_cmd": "python3.11 -m pip install --user --upgrade hermes-agent",
        "capabilities": ["terminal", "computer-use", "skills", "plugins"],
    },
    {
        "id": "codex",
        "name": "Codex CLI",
        "aliases": ["Codex CLI"],
        "cli": "codex",
        "manual_key": "codex",
        "kind": "coding-agent",
        "computer_control": True,
        "plugin_capable": True,
        "ecosystem_score": 92,
        "deploy_adapter": "manual",
        "capabilities": ["terminal", "computer-use", "skills", "plugins"],
    },
    {
        "id": "claude-code",
        "name": "Claude Code",
        "aliases": ["Claude Code"],
        "cli": "claude",
        "manual_key": "vscode-claude",
        "kind": "coding-agent",
        "computer_control": True,
        "plugin_capable": True,
        "ecosystem_score": 90,
        "deploy_adapter": "manual",
        "capabilities": ["terminal", "computer-use", "hooks", "plugins"],
    },
    {
        "id": "chatgpt",
        "name": "ChatGPT 桌面版",
        "aliases": ["ChatGPT", "OpenAI（ChatGPT）"],
        "app_name": "ChatGPT",
        "kind": "desktop-assistant",
        "computer_control": True,   # 应用快照：可感知已打开的应用窗口（读屏级，非自主操作）
        "plugin_capable": True,
        "ecosystem_score": 68,      # 实际分以 ecosystem_scores.yaml 六维加权为准
        "deploy_adapter": "manual",
        "capabilities": ["app-snapshot", "gpts", "tasks", "connectors", "voice", "vision"],
    },
    {
        "id": "autoclaw",
        "name": "AutoClaw（GLM）",
        "aliases": ["AutoClaw（GLM 生态 agent）", "AutoClaw"],
        "app_name": "AutoClaw",
        "gateway_url": "http://localhost:18789",
        "open_mode": "app",
        "manual_key": "autoclaw",
        "kind": "gateway-agent",
        "computer_control": True,
        "plugin_capable": True,
        "ecosystem_score": 88,
        "deploy_adapter": "manual",
        "capabilities": ["exec", "browser", "computer", "skills"],
    },
    {
        "id": "workbuddy",
        "name": "WorkBuddy",
        "aliases": ["WorkBuddy"],
        "app_name": "WorkBuddy",
        "kind": "desktop-agent",
        "computer_control": True,
        "plugin_capable": False,
        "ecosystem_score": 86,
        "deploy_adapter": "manual",
        "capabilities": ["desktop", "automation"],
    },
    {
        "id": "dsh",
        "name": "DSH Desktop",
        "aliases": ["DSH Desktop"],
        "app_name": "DSH Desktop",
        "manual_key": "dsh",
        "kind": "desktop-agent",
        "computer_control": False,
        "plugin_capable": False,
        "ecosystem_score": 78,
        "deploy_adapter": "manual",
        "capabilities": ["desktop", "coding"],
    },
    {
        "id": "agent-team",
        "name": "Agent Team 启动器",
        "aliases": ["Agent Team 启动器（本地多 agent）"],
        "app_name": "启动 Agent Team",
        "kind": "orchestrator",
        "computer_control": True,
        "plugin_capable": True,
        "ecosystem_score": 80,
        "deploy_adapter": "manual",
        "capabilities": ["multi-agent", "terminal", "orchestration"],
    },
    {
        "id": "vscode-claude",
        "name": "VS Code + Claude Code",
        "aliases": ["VS Code + Claude Code 插件"],
        "manual_key": "vscode-claude",
        "kind": "ide-agent",
        "computer_control": False,
        "plugin_capable": True,
        "ecosystem_score": 76,
        "deploy_adapter": "manual",
        "capabilities": ["workspace", "terminal", "hooks"],
    },
    {
        "id": "cursor",
        "name": "Cursor",
        "aliases": ["Cursor"],
        "kind": "ide-agent",
        "computer_control": False,
        "plugin_capable": True,
        "ecosystem_score": 74,
        "deploy_adapter": "manual",
        "capabilities": ["workspace", "terminal", "mcp"],
    },
    {
        "id": "zcode",
        "name": "ZCode",
        "aliases": ["ZCode"],
        "kind": "ide-agent",
        "computer_control": False,
        "plugin_capable": True,
        "ecosystem_score": 72,
        "deploy_adapter": "manual",
        "capabilities": ["workspace", "terminal", "skills"],
    },
    {
        "id": "lm-studio",
        "name": "LM Studio",
        "aliases": ["LM Studio（本地模型）"],
        "app_name": "LM Studio",
        "kind": "local-runtime",
        "computer_control": False,
        "plugin_capable": False,
        "ecosystem_score": 68,
        "deploy_adapter": "manual",
        "capabilities": ["local-models", "openai-api"],
    },
]


def _local_scan(conn=None) -> dict:
    if conn is not None:
        row = conn.execute("SELECT value FROM kv WHERE key='local_scan'").fetchone()
        if row:
            try:
                return json.loads(row["value"])
            except (TypeError, ValueError):
                pass
    from radar.local_scan import scan
    return scan()


def _detected(local_names: set[str], aliases: list[str]) -> bool:
    for alias in aliases:
        if alias in local_names:
            return True
        if any(alias.lower() in name.lower() or name.lower() in alias.lower()
               for name in local_names):
            return True
    return False


def _score_overrides() -> dict[str, dict]:
    """从 config/ecosystem_scores.yaml 读取透明评分卡（六维加权），覆盖硬编码分。"""
    import yaml

    from radar.config import CONFIG_DIR

    path = CONFIG_DIR / "ecosystem_scores.yaml"
    try:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    rubric = cfg.get("rubric") or {}
    overrides = {}
    for a in cfg.get("agents") or []:
        dims = a.get("dims") or {}
        score = round(sum(dims.get(k, 0) * w for k, w in rubric.items()))
        overrides[a["id"]] = {
            "ecosystem_score": max(1, min(100, score)),
            "score_dims": dims,
            "score_evidence": a.get("evidence", ""),
        }
    return overrides


_SCORES = None


def _apply_scores(spec: dict) -> dict:
    global _SCORES
    if _SCORES is None:
        _SCORES = _score_overrides()
    override = _SCORES.get(spec["id"])
    if override:
        spec.update(override)
    return spec


def list_agents(conn=None) -> list[dict]:
    """返回所有已登记 Agent；检测结果只使用存在性/登录态，不读取密钥。"""
    local = _local_scan(conn)
    names = set(local)
    cards = []
    for base in AGENT_SPECS:
        spec = _apply_scores(dict(base))
        item = spec
        item["detected"] = _detected(names, spec.get("aliases", []))
        item["status"] = "detected" if item["detected"] else "missing"
        item["open_mode"] = item.get("open_mode") or (
            "gateway" if item.get("gateway_url") else
            "app" if item.get("app_name") else
            "cli" if item.get("cli") else "manual"
        )
        cards.append(item)
    cards.sort(key=lambda x: (not x["detected"], -x["ecosystem_score"], x["name"]))
    return cards


def get_agent(agent_id: str, conn=None) -> dict | None:
    return next((a for a in list_agents(conn) if a["id"] == agent_id), None)


def preferred_agent(conn=None) -> dict:
    """自动部署优先选择生态最完整且能控制电脑的已安装 Agent。"""
    agents = list_agents(conn)
    for agent in agents:
        if agent["detected"] and agent.get("deploy_adapter") == "openclaw_config_patch":
            return agent
    return next((a for a in agents if a["detected"] and a["computer_control"]), agents[0])


def match_channel(channel: dict, agents: list[dict] | None = None) -> dict:
    """为一个渠道生成推荐 Agent 与安全说明，不虚构可自动部署能力。"""
    agents = agents or list_agents()
    openclaw = next((a for a in agents if a["id"] == "openclaw"), agents[0])
    if channel.get("deploy_ready") and openclaw.get("detected"):
        return {
            "agent": openclaw,
            "automatic": True,
            "reason": "OpenClaw 已安装且支持配置补丁、真实推理验证和失败回滚",
        }
    if channel.get("deploy_reason"):
        reason = channel["deploy_reason"]
        if "配置" in reason or ".env" in reason or "key" in reason.lower():
            return {
                "agent": openclaw,
                "automatic": False,
                "reason": f"OpenClaw 可自动部署；{reason}",
            }
        provider = str(channel.get("provider") or "")
        preferred_id = "autoclaw" if provider in {"zhipu", "bigmodel"} else "hermes"
        best = next((a for a in agents if a["detected"] and a["id"] == preferred_id),
                    next((a for a in agents if a["detected"] and a["computer_control"]), openclaw))
        return {
            "agent": best,
            "automatic": False,
            "reason": f"建议交给 {best['name']} 人工配置；当前渠道没有可直接写入的 OpenClaw 适配器",
        }
    best = next((a for a in agents if a["detected"] and a["computer_control"]), openclaw)
    return {
        "agent": best,
        "automatic": False,
        "reason": f"建议交给 {best['name']} 配置；当前渠道缺少可直接写入的适配器",
    }


def monitor_subject_for_agent(agent_id: str) -> str:
    return agent_id


def cache_agents(conn, agents: list[dict]) -> None:
    conn.execute(
        "INSERT INTO kv(key,value) VALUES('agent_catalog',?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (json.dumps(agents, ensure_ascii=False),),
    )
    conn.execute(
        "INSERT INTO kv(key,value) VALUES('agent_catalog_at',?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (now_iso(),),
    )
    conn.commit()
