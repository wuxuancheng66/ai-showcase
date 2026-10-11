"""摘要片段：从正文里挑出最匹配查询的一段，并给命中词打标记。"""

from __future__ import annotations

import re
from html import escape

_SENT_SPLIT = re.compile(r"(?<=[.:;!?])\s+|\n+")


def best_snippet(text: str, query_terms: list[str], width: int = 240) -> str:
    """在正文里找命中词最密集的窗口，返回纯文本片段（已折叠空白）。"""
    if not text:
        return ""
    flat = re.sub(r"\s+", " ", text).strip()
    if not query_terms:
        return flat[:width]
    low = flat.lower()
    # 记录每个查询词第一次出现的位置
    positions = [low.find(t) for t in query_terms]
    hits = [p for p in positions if p >= 0]
    if not hits:
        return flat[:width]
    center = min(hits)
    start = max(0, center - width // 3)
    end = min(len(flat), start + width)
    if start > 0:
        start = flat.rfind(" ", 0, start + 1) + 1
    snip = flat[start:end].strip()
    if start > 0:
        snip = "…" + snip
    if end < len(flat):
        snip = snip + "…"
    return snip


def highlight(text: str, query_terms: list[str]) -> str:
    """把片段里的命中词包成 <mark>，返回已转义的 HTML 片段。"""
    out = escape(text)
    terms = sorted({t for t in query_terms if t and len(t) > 1}, key=len, reverse=True)
    for t in terms:
        try:
            pat = re.compile(re.escape(escape(t)), re.IGNORECASE)
        except re.error:
            continue
        out = pat.sub(lambda m: f"<mark>{m.group(0)}</mark>", out)
    return out
