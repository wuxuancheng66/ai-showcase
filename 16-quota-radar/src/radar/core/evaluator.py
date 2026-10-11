"""性价比评估与场景化推荐。

核心指标：
- blended_price：按典型用量（75% 输入 / 25% 输出）折算的混合单价（USD/1M tokens）
- value_index：能力分 ÷ 混合单价，即"每美元买到多少能力"
- 免费模型单列免费榜，按能力分排序（价格为零，性价比无意义）

跨源去重：同一模型常同时出现在 litellm 与 openrouter，
以 canonical 名（去 provider 前缀与 :free 后缀的小写名）聚合，保留 value_index 最高者。
"""

import json

SCENARIOS = ("chat", "code", "longctx", "bulk", "free")

_INPUT_WEIGHT = 0.75
_MIN_SCORE = {"chat": 70, "code": 75, "longctx": 70, "bulk": 60}
_LONGCTX_MIN_TOKENS = 128_000


def canonical_name(model_id: str) -> str:
    base = (model_id or "").split("/")[-1].lower().strip()
    return base[:-5] if base.endswith(":free") else base


def blended_price(m: dict) -> float:
    return _INPUT_WEIGHT * (m["input_price"] or 0) + (1 - _INPUT_WEIGHT) * (m["output_price"] or 0)


def _flags(raw) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}


def recommend(conn, scenario: str = "chat", top_n: int = 3) -> list[dict]:
    if scenario not in SCENARIOS:
        raise ValueError(f"未知场景: {scenario}，可选 {SCENARIOS}")

    rows = conn.execute(
        "SELECT * FROM models WHERE capability_score IS NOT NULL"
    ).fetchall()
    models = [dict(r) for r in rows]

    if scenario == "free":
        cands = [m for m in models if m["free"]]
        cands.sort(key=lambda m: (-m["capability_score"], canonical_name(m["model_id"])))
        return [_format(m, m["capability_score"]) for m in cands[:top_n]]

    cands = []
    for m in models:
        if m["free"] or not m["input_price"] or not m["output_price"]:
            continue
        flags = _flags(m.get("scenario_flags"))
        score = m["capability_score"]
        if scenario == "code" and not (flags.get("code") or score >= 85):
            continue
        if scenario == "longctx" and (m["context_len"] or 0) < _LONGCTX_MIN_TOKENS:
            continue
        if score < _MIN_SCORE[scenario]:
            continue
        blended = blended_price(m)
        if blended <= 0:
            continue
        cands.append((m, score / blended))

    # 跨源去重：同 canonical 保留 value_index 最高
    best_by_canon: dict[str, tuple[dict, float]] = {}
    for m, value in cands:
        canon = canonical_name(m["model_id"])
        if canon not in best_by_canon or value > best_by_canon[canon][1]:
            best_by_canon[canon] = (m, value)

    ranked = sorted(best_by_canon.values(), key=lambda pair: (
        blended_price(pair[0]) if scenario == "bulk" else -pair[1],
        canonical_name(pair[0]["model_id"]),
    ))
    return [_format(m, value) for m, value in ranked[:top_n]]


def _format(m: dict, value: float) -> dict:
    return {
        "model_id": m["model_id"],
        "provider": m["provider"],
        "source": m["source"],
        "display_name": m.get("display_name"),
        "input_price": m["input_price"],
        "output_price": m["output_price"],
        "context_len": m["context_len"],
        "capability_score": m["capability_score"],
        "blended_price": round(blended_price(m), 4),
        "value_index": round(value, 1),
        "free": bool(m["free"]),
    }
