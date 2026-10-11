"""能力评分：种子表精确匹配 → 家族修饰词启发式 → 兜底 50。

评分是相对参考值（0-100），非官方基准分；种子表可随时手动修订。
"""

import functools

import yaml

from radar.config import CONFIG_DIR


@functools.lru_cache(maxsize=1)
def _load_config() -> tuple[dict, dict, dict]:
    with open(CONFIG_DIR / "capability_scores.yaml", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    return cfg.get("scores") or {}, cfg.get("family_modifiers") or {}, cfg.get("scenario_keywords") or {}


def score_model(name: str) -> float:
    low = (name or "").lower()
    scores, modifiers, _ = _load_config()

    best: tuple[str, float] | None = None
    for keyword, value in scores.items():
        if keyword.lower() in low and (best is None or len(keyword) > len(best[0])):
            best = (keyword, float(value))
    if best:
        return best[1]

    base = float(modifiers.get("base", 60))
    result = base
    for token, delta in modifiers.items():
        if token == "base":
            continue
        if token.lower() in low:
            result += float(delta)
    return max(1.0, min(99.0, result))


def scenario_flags(name: str) -> dict:
    low = (name or "").lower()
    _, _, keywords = _load_config()
    return {
        "reasoning": any(kw in low for kw in keywords.get("reasoning", [])),
        "code": any(kw in low for kw in keywords.get("code", [])),
    }


def enrich(models: list[dict]) -> list[dict]:
    """为归一化模型补充 capability_score 与 scenario_flags。"""
    import json

    for m in models:
        m["capability_score"] = score_model(m.get("model_id", "") or m.get("display_name", ""))
        m["scenario_flags"] = json.dumps(scenario_flags(m.get("model_id", "")), ensure_ascii=False)
    return models
