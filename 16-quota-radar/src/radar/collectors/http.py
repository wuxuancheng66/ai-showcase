"""共享 HTTP 抓取：重试 + 指数退避 + 统一 UA。低频礼貌采集。"""

import logging
import time

import httpx

log = logging.getLogger("radar.collectors")

USER_AGENT = "QuotaRadar/0.1 (+self-hosted quota monitor; polite; 1req/30min)"


class CollectorError(RuntimeError):
    """数据源最终不可达。"""


def fetch_json(url: str, *, retries: int = 3, timeout: float = 30.0) -> dict:
    """GET JSON，失败指数退避重试。全部失败抛 CollectorError。"""
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = httpx.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=timeout,
                follow_redirects=True,
            )
            if resp.status_code >= 500:
                raise httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}", request=resp.request, response=resp
                )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:  # ValueError: JSON 解码失败
            last_err = exc
            log.warning("抓取失败(%d/%d) %s: %s", attempt, retries, url, exc)
            if attempt < retries:
                time.sleep(2 * attempt)
    raise CollectorError(f"数据源不可达: {url} ({last_err})") from last_err
