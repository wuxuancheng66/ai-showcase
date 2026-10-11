"""agent 探测：检测本机可部署的 agent 空壳（容器内经 /host 只读挂载探测）。"""

import json
import os
from pathlib import Path

import yaml

from radar.config import CONFIG_DIR

_PROVIDER_TARGETS = {  # openclaw provider 名 → 渠道 id
    "nvidia": "nvidia-nim",
}


def _config_candidates(agent: dict) -> list[Path]:
    raw = agent.get("config_path", "~/.openclaw/openclaw.json")
    base = Path(os.path.expanduser(raw))
    host_variant = Path("/host") / raw.replace("~/", "")
    return [base, host_variant]


def detect_agents() -> list[dict]:
    with open(CONFIG_DIR / "agents_registry.yaml", encoding="utf-8") as fh:
        agents = (yaml.safe_load(fh) or {}).get("agents") or []
    out = []
    for a in agents:
        detected, providers, channel_ids = False, [], []
        for cand in _config_candidates(a):
            if not cand.exists():
                continue
            detected = True
            try:
                cfg = json.loads(cand.read_text(encoding="utf-8"))
                providers = list((cfg.get("models") or {}).get("providers") or {})
            except (OSError, ValueError):
                providers = []
            for p in providers:
                cid = _PROVIDER_TARGETS.get(str(p).lower())
                if cid and cid not in channel_ids:
                    channel_ids.append(cid)
            break
        out.append({
            "id": a["id"],
            "name": a["name"],
            "detected": detected,
            "gateway_url": a.get("gateway_url"),
            "capabilities": a.get("capabilities", []),
            "install_cmd": a.get("install_cmd"),
            "providers": providers,
            "configured_channel_ids": channel_ids,
        })
    return out
