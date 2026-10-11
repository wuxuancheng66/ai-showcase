"""AI 日报新闻抓取：多 RSS 源 + 36h 窗口 + AI 关键词过滤 + 信源分级。"""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx
import yaml

from radar.collectors.http import USER_AGENT
from radar.config import CONFIG_DIR

log = logging.getLogger("radar.daily")

_AI_KEYWORDS = re.compile(
    r"AI|人工智能|大模型|LLM|GPT|GPT-|Claude|Gemini|DeepSeek|深度求索|OpenAI|Anthropic|"
    "智能体|Agent|芯片|GPU|算力|通义|千问|文心|混元|豆包|Kimi|月之暗面|智谱|GLM|"
    "机器学习|神经网络|多模态|推理模型|Sora|Midjourney", re.I)


def load_sources() -> list[dict]:
    with open(CONFIG_DIR / "news_sources.yaml", encoding="utf-8") as fh:
        return (yaml.safe_load(fh) or {}).get("sources") or []


def _parse_date(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw.strip())
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _fetch_one(client: httpx.Client, source: dict) -> list[dict]:
    resp = client.get(source["url"], headers={"User-Agent": USER_AGENT}, timeout=20,
                      follow_redirects=True)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    items = []
    for item in root.iter():
        tag = item.tag.rsplit("}", 1)[-1]
        if tag not in ("item", "entry"):
            continue
        fields = {}
        for child in item:
            ctag = child.tag.rsplit("}", 1)[-1]
            if ctag in ("title", "link", "pubDate", "published", "updated", "description"):
                if ctag == "link":
                    fields[ctag] = child.get("href") or (child.text or "").strip()
                else:
                    fields[ctag] = (child.text or "").strip()
        title = fields.get("title", "")
        if not title:
            continue
        items.append({
            "title": title,
            "url": fields.get("link", ""),
            "date": _parse_date(fields.get("pubDate") or fields.get("published")
                                or fields.get("updated")),
            "summary": re.sub(r"<[^>]+>", "", fields.get("description", ""))[:180],
        })
    return items


def fetch_news(hours: int = 36, limit: int = 40) -> dict:
    """抓取全部源，返回 {items: 按信源分级+时间排序的新闻, sources: 各源状态}。"""
    sources = load_sources()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    all_items: list[dict] = []
    status: list[dict] = []

    with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
        for src in sources:
            try:
                raw = _fetch_one(client, src)
            except Exception as exc:  # noqa: BLE001 — 单源失败不拖垮日报
                log.warning("新闻源失败 %s: %s", src["name"], type(exc).__name__)
                status.append({"name": src["name"], "grade": src["grade"], "ok": False,
                               "count": 0})
                continue
            fresh = []
            for it in raw:
                dt = it.get("date")
                if dt and dt.tzinfo is None:
                    dt = dt.astimezone()
                if dt and dt < cutoff:
                    continue
                if not _AI_KEYWORDS.search(it["title"]):
                    continue
                it["source"], it["grade"] = src["name"], src["grade"]
                fresh.append(it)
            status.append({"name": src["name"], "grade": src["grade"], "ok": True,
                           "count": len(fresh)})
            all_items.extend(fresh)

    # 去重（标题前 30 字）+ 排序：信源分级 → 时间新在前
    seen: set[str] = set()
    uniq = []
    for it in sorted(all_items, key=lambda x: x.get("date") or datetime.min.replace(tzinfo=timezone.utc),
                     reverse=True):
        key = it["title"][:30]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)

    grade_rank = {"🟢": 0, "🔵": 1, "🟡": 2, "⚪": 3}
    uniq.sort(key=lambda x: (grade_rank.get(x["grade"], 2),
                             -(x.get("date") or datetime.min.replace(tzinfo=timezone.utc)).timestamp()))
    return {"items": uniq[:limit], "sources": status}
