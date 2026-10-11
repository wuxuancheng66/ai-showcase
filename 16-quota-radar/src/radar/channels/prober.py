"""渠道探活：对配置了自有 key 的渠道发最小请求，验证免费额度是否仍可用。

安全设计：
- key 只进请求头（Google 也走 x-goog-api-key 头，避免出现在 URL/日志里）
- 日志与库中永不落 key 明文
- 429 → limited（渠道活着但限流中）；401/403 → error（凭证无效）
- 未配置 key 的渠道保持 unknown，绝不假装可用
"""

import logging
import time

import httpx

from radar.collectors.http import USER_AGENT
from radar.db import now_iso

log = logging.getLogger("radar.prober")

_TIMEOUT = 20.0

_STATUS_SUMMARY = {
    "ok": "免费额度可用",
    "limited": "可达但限流中（额度大概率仍在）",
    "error": "不可用或凭证无效",
    "dead": "服务已下线",
}


def _classify(status_code: int) -> str:
    if status_code == 200:
        return "ok"
    if status_code == 429:
        return "limited"
    return "error"


def probe_openai_compatible(base_url: str, model: str, api_key: str) -> str:
    resp = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"User-Agent": USER_AGENT, "Authorization": f"Bearer {api_key}"},
        json={"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
        timeout=_TIMEOUT,
    )
    return _classify(resp.status_code)


def probe_openai_models(base_url: str, api_key: str) -> str:
    """只读模型目录验证 key 与端点，不触发模型推理，也不携带空 model。"""
    resp = httpx.get(
        f"{base_url.rstrip('/')}/models",
        headers={"User-Agent": USER_AGENT, "Authorization": f"Bearer {api_key}"},
        timeout=_TIMEOUT,
    )
    return _classify(resp.status_code)


def probe_google_list(base_url: str, api_key: str) -> str:
    resp = httpx.get(
        f"{base_url.rstrip('/')}/v1beta/models",
        headers={"User-Agent": USER_AGENT, "x-goog-api-key": api_key},
        timeout=_TIMEOUT,
    )
    return _classify(resp.status_code)


def probe_channel(conn, ch, api_key: str) -> str | None:
    """探测单个渠道并落库。返回新状态；无法探测返回 None。ch 为 sqlite3.Row。"""
    ptype = ch["probe_type"]
    if ptype == "none":
        return None
    if ch["requires_key"] and not api_key:
        return None

    try:
        if ptype == "openai_compatible":
            status = probe_openai_compatible(ch["probe_base_url"], ch["probe_model"], api_key)
        elif ptype == "openai_models":
            status = probe_openai_models(ch["probe_base_url"], api_key)
        elif ptype == "google_list":
            status = probe_google_list(ch["probe_base_url"], api_key)
        else:
            log.warning("未知探活类型 %s（渠道 %s）", ptype, ch["id"])
            return None
    except httpx.HTTPError as exc:
        log.warning("渠道 %s 探活网络异常: %s", ch["id"], type(exc).__name__)
        status = "error"

    now = now_iso()
    old = ch["status"]
    conn.execute(
        "UPDATE channels SET status=?, last_checked=?, last_ok=? WHERE id=?",
        (status, now, now if status == "ok" else ch["last_ok"], ch["id"]),
    )
    if old != status:
        conn.execute(
            "INSERT INTO changes(kind,target,summary,created_at) VALUES(?,?,?,?)",
            ("channel_status", ch["id"],
             f"渠道「{ch['name']}」状态 {old} → {status}（{_STATUS_SUMMARY.get(status, status)}）",
             now),
        )
    conn.commit()
    return status


def probe_all(conn, settings) -> dict:
    """遍历渠道表逐个探测。返回 {channel_id: status}，仅含实际探测的渠道。"""
    results: dict = {}
    rows = conn.execute("SELECT * FROM channels ORDER BY id").fetchall()
    for ch in rows:
        try:
            api_key = settings.api_key(ch["env_key"] or "")
            status = probe_channel(conn, ch, api_key)
        except Exception as exc:  # noqa: BLE001 - 单个坏渠道不能中断整批探活
            log.warning("渠道 %s 探活配置异常: %s", ch["id"], type(exc).__name__)
            status = "error"
            now = now_iso()
            conn.execute(
                "UPDATE channels SET status=?, last_checked=? WHERE id=?",
                (status, now, ch["id"]),
            )
            conn.commit()
        if status is not None:
            results[ch["id"]] = status
        time.sleep(1)  # 礼貌间隔
    log.info("探活完成: %s", results)
    return results
