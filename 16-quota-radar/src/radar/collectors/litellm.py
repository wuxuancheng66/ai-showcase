"""LiteLLM 社区定价表采集器。

结构化优先策略：jsDelivr CDN 为主源（对国内网络友好、与 GitHub 同步），
raw.githubusercontent 为备源。返回统一模型字典列表。
"""

import logging

from radar.collectors.http import CollectorError, fetch_json

log = logging.getLogger("radar.collectors.litellm")

PRIMARY_URL = (
    "https://cdn.jsdelivr.net/gh/BerriAI/litellm@main/model_prices_and_context_window.json"
)
FALLBACK_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
)

SOURCE = "litellm"


def _normalize_entry(name: str, spec: dict) -> dict | None:
    if spec.get("mode") != "chat":  # 只收对话模型，过滤 embedding/image/audio 等
        return None
    in_tok = spec.get("input_cost_per_token")
    out_tok = spec.get("output_cost_per_token")
    if not isinstance(in_tok, (int, float)) or not isinstance(out_tok, (int, float)):
        return None
    if in_tok < 0 or out_tok < 0:
        return None
    provider = spec.get("litellm_provider") or "unknown"
    context = spec.get("max_input_tokens") or spec.get("max_tokens")
    return {
        "key": f"{provider}/{name}",
        "provider": str(provider),
        "model_id": name,
        "display_name": name,
        "input_price": round(in_tok * 1_000_000, 4),
        "output_price": round(out_tok * 1_000_000, 4),
        "context_len": int(context) if isinstance(context, (int, float)) else None,
        "free": 1 if in_tok == 0 and out_tok == 0 else 0,
        "source": SOURCE,
    }


def collect() -> list[dict]:
    errors: list[str] = []
    data = None
    for url in (PRIMARY_URL, FALLBACK_URL):
        try:
            data = fetch_json(url)
            break
        except CollectorError as exc:
            errors.append(str(exc))
            log.warning("litellm 源失败，尝试备源: %s", exc)
    if not isinstance(data, dict):
        raise CollectorError("litellm 全部源不可达: " + "; ".join(errors))

    models = []
    for name, spec in data.items():
        if not isinstance(spec, dict) or name.startswith("$"):
            continue
        normalized = _normalize_entry(name, spec)
        if normalized:
            models.append(normalized)
    if not models:
        raise CollectorError("litellm 数据源返回为空或全部无法解析")
    log.info("litellm 采集到 %d 个对话模型", len(models))
    return models
