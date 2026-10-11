"""免费渠道综合排行：模型能力 × 国内可达 × 限速宽松 × 稳定性 × 上手门槛。

维度权重（可在此调整）：
- capability 35%：该渠道免费可用的最强模型能力（种子或动态采集）
- access_cn  25%：国内网络直连可达性
- limits     20%：限速/次数宽松度
- stability  10%：成熟度种子 × 探活状态修正（error 大幅降分）
- onboarding 10%：上手门槛（已配 key / 已部署进 agent 加分）
"""

import json
import logging
import os
from pathlib import Path

import yaml

from radar.config import CONFIG_DIR
from radar.db import kv_set, now_iso

log = logging.getLogger("radar.free_rank")

WEIGHTS = {"capability": 0.35, "access": 0.25, "limits": 0.20, "stability": 0.10, "onboarding": 0.10}

_STATUS_FACTOR = {"ok": 1.0, "limited": 0.7, "error": 0.3, "dead": 0.0, "unknown": 0.85}

# OpenClaw provider 名 → 渠道 id（检测已部署渠道）
_OPENCLAW_PROVIDER_MAP = {"nvidia": "nvidia-nim"}
_OPENCLAW_CONFIGS = ["~/.openclaw/openclaw.json", "/host/.openclaw/openclaw.json"]


def _load_channel_seeds() -> list[dict]:
    with open(CONFIG_DIR / "channels.yaml", encoding="utf-8") as fh:
        return (yaml.safe_load(fh) or {}).get("channels") or []


def detect_agent_channels() -> dict[str, list[str]]:
    """检测本机 OpenClaw 已配置的 provider，返回 {渠道id: [provider名]}。读不到返回空。"""
    found: dict[str, list[str]] = {}
    for raw in _OPENCLAW_CONFIGS:
        p = Path(os.path.expanduser(raw))
        if not p.exists():
            continue
        try:
            cfg = json.loads(p.read_text(encoding="utf-8"))
            providers = list(((cfg.get("models") or {}).get("providers") or {}).keys())
        except (OSError, ValueError):
            continue
        for provider in providers:
            channel_id = _OPENCLAW_PROVIDER_MAP.get(str(provider).lower())
            if channel_id:
                found.setdefault(channel_id, []).append(str(provider))
    return found


def _dynamic_capability(conn, channel_id: str) -> float | None:
    """openrouter 免费模型能力动态取自采集库；其他渠道走种子。"""
    if channel_id != "openrouter-free":
        return None
    row = conn.execute(
        "SELECT MAX(capability_score) m FROM models WHERE source='openrouter' AND free=1"
    ).fetchone()
    return row["m"] if row and row["m"] else None


def compute_free_rank(conn, settings) -> list[dict]:
    agent_channels = detect_agent_channels()
    results = []
    for ch in _load_channel_seeds():
        if ch.get("tier") != "free":
            continue
        cid = ch["id"]
        offered = ch.get("models_offered") or []
        seed_cap = max((m.get("capability", 50) for m in offered), default=50)
        dyn_cap = _dynamic_capability(conn, cid)
        capability = max(seed_cap, dyn_cap) if dyn_cap else seed_cap
        best_model = max(offered, key=lambda m: m.get("capability", 0))["id"] if offered else \
            (dyn_cap and "（动态：采集库免费模型）" or "—")

        status_row = conn.execute("SELECT status FROM channels WHERE id=?", (cid,)).fetchone()
        status = status_row["status"] if status_row else "unknown"
        stability = round(ch.get("stability_seed", 75) * _STATUS_FACTOR.get(status, 0.85))

        has_key = bool(settings.api_key(ch.get("env_key") or ""))
        configured = cid in agent_channels or bool(ch.get("configured_in_agent"))
        onboarding = min(100, 55 + (25 if has_key else 0) + (20 if configured else 0))
        from radar.deploy.planner import deployment_target
        providers = agent_channels.get(cid) or ([ch.get("provider")] if configured else [])
        target = deployment_target(ch, {"providers": providers}, has_key)

        breakdown = {
            "capability": round(capability),
            "access": ch.get("access_cn", 50),
            "limits": ch.get("limits", 60),
            "stability": stability,
            "onboarding": onboarding,
        }
        score = round(sum(breakdown[k] * w for k, w in WEIGHTS.items()))

        reasons = []
        if capability >= 85:
            reasons.append(f"旗下免费模型能力强（{best_model}，{capability:.0f} 分）")
        if ch.get("access_cn", 0) >= 90:
            reasons.append("国内直连无需代理")
        if (ch.get("limits", 0)) >= 75:
            reasons.append("限速宽松")
        if configured:
            reasons.append("已部署进本机 agent，零上手成本")
        elif has_key:
            reasons.append("已配置 key，即开即用")
        if status == "limited":
            reasons.append("当前限流中（额度仍在）")
        if status == "error":
            reasons.append("⚠️ 最近探活异常，建议人工复核")

        results.append({
            "id": cid,
            "name": ch["name"],
            "provider": ch.get("provider"),
            "url": ch.get("url"),
            "free_tier_desc": ch.get("free_tier_desc"),
            "score": score,
            "breakdown": breakdown,
            "best_model": best_model,
            "status": status,
            "has_key": has_key,
            "configured_in_agent": configured,
            "deploy_ready": target["ready"],
            "deploy_reason": target["reason"],
            "reasons": reasons,
        })

    results.sort(key=lambda x: (-x["score"], x["name"]))
    kv_set(conn, "free_rank", json.dumps(results, ensure_ascii=False))
    kv_set(conn, "free_rank_at", now_iso())
    log.info("免费渠道排行: %s", [(r["name"], r["score"]) for r in results[:5]])
    return results
