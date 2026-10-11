"""OpenRouter 模型目录采集器（公开 API，无需鉴权）。"""

import logging

from radar.collectors.http import CollectorError, fetch_json

log = logging.getLogger("radar.collectors.openrouter")

MODELS_URL = "https://openrouter.ai/api/v1/models"
SOURCE = "openrouter"


def _price(value) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v >= 0 else None


def collect() -> list[dict]:
    data = fetch_json(MODELS_URL)
    entries = data.get("data") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise CollectorError("openrouter 返回结构异常")

    models = []
    for m in entries:
        if not isinstance(m, dict) or "id" not in m:
            continue
        pricing = m.get("pricing") or {}
        p_in = _price(pricing.get("prompt"))
        p_out = _price(pricing.get("completion"))
        if p_in is None or p_out is None:
            continue
        model_id = m["id"]
        provider = model_id.split("/", 1)[0]
        free = 1 if (model_id.endswith(":free") or (p_in == 0 and p_out == 0)) else 0
        models.append(
            {
                "key": f"{SOURCE}/{model_id}",
                "provider": provider,
                "model_id": model_id,
                "display_name": m.get("name") or model_id,
                "input_price": round(p_in * 1_000_000, 4),
                "output_price": round(p_out * 1_000_000, 4),
                "context_len": m.get("context_length"),
                "free": free,
                "source": SOURCE,
            }
        )
    if not models:
        raise CollectorError("openrouter 数据源返回为空或全部无法解析")
    log.info("openrouter 采集到 %d 个模型", len(models))
    return models
