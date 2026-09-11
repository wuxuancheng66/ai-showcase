"""联网搜索与网页抓取工具。

* 优先 Tavily（REST 直调，无需额外 SDK），回退 SerpAPI；
* 未配置任何密钥时优雅降级：返回提示文本而非抛错，流水线继续运行；
* UrlFetchTool 仅允许公网 http(s) 地址，拒绝 localhost/内网/云元数据地址（SSRF 防护）。
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List

import httpx
from bs4 import BeautifulSoup

from core.base import BaseTool, ToolResult

logger = logging.getLogger("agent_team.tools.web")

__all__ = ["WebSearchTool", "UrlFetchTool"]

MAX_CONTENT_CHARS = 6000
HTTP_TIMEOUT = 15.0
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ai-agent-team/1.0"

# 禁止抓取的地址：本机、内网段、链路本地、云厂商元数据（防 SSRF / 内网探测）
_BLOCKED_HOST_RE = re.compile(
    r"^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.|0\.|\[::1\]|"
    r"metadata\.google\.internal|169\.254\.169\.254)",
    re.IGNORECASE,
)


def _truncate(text: str, limit: int = MAX_CONTENT_CHARS) -> str:
    return text if len(text) <= limit else text[:limit] + f"\n…（已截断，原始长度 {len(text)} 字符）"


def _format_results(items: List[Dict[str, Any]]) -> str:
    """把搜索结果渲染为带编号的来源清单，供 LLM 直接引用。"""
    lines: List[str] = []
    for idx, item in enumerate(items, start=1):
        lines.append(f"[{idx}] {item.get('title', '(无标题)')}")
        lines.append(f"URL: {item.get('url', '')}")
        snippet = (item.get("content") or item.get("snippet") or "").strip()
        if snippet:
            lines.append(f"摘要: {snippet[:500]}")
        lines.append("")
    return "\n".join(lines).strip() or "（搜索无结果）"


class WebSearchTool(BaseTool):
    """联网搜索工具：Tavily 优先，SerpAPI 回退，无密钥时降级提示。"""

    name = "web_search"
    description = "联网搜索最新资料。参数: query=str, max_results=int(默认5)"

    def run(self, query: str, max_results: int = 5) -> ToolResult:
        query = (query or "").strip()
        if not query:
            return ToolResult(ok=False, text="搜索关键词为空")
        tavily_key = os.getenv("TAVILY_API_KEY", "").strip()
        serp_key = os.getenv("SERPAPI_API_KEY", "").strip()
        try:
            if tavily_key:
                return self._tavily(query, max_results, tavily_key)
            if serp_key:
                return self._serpapi(query, max_results, serp_key)
            return ToolResult(
                ok=False,
                text="未配置搜索 API Key（TAVILY_API_KEY / SERPAPI_API_KEY），"
                     "已跳过联网搜索。请基于给定素材与既有知识完成任务，"
                     "并在产出中注明『内容未经联网核实』。",
            )
        except Exception as exc:  # noqa: BLE001 网络/服务异常不阻塞流水线
            logger.warning("搜索失败 query=%r: %s", query, exc)
            return ToolResult(ok=False, text=f"搜索失败：{exc}")

    def _tavily(self, query: str, max_results: int, api_key: str) -> ToolResult:
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": api_key, "query": query, "max_results": max_results,
                  "search_depth": "basic"},
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        return ToolResult(ok=True, text=_format_results(resp.json().get("results") or []),
                          meta={"provider": "tavily"})

    def _serpapi(self, query: str, max_results: int, api_key: str) -> ToolResult:
        resp = httpx.get(
            "https://serpapi.com/search",
            params={"api_key": api_key, "q": query, "num": max_results},
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        organic = [
            {"title": r.get("title", ""), "url": r.get("link", ""),
             "content": r.get("snippet", "")}
            for r in (resp.json().get("organic_results") or [])[:max_results]
        ]
        return ToolResult(ok=True, text=_format_results(organic), meta={"provider": "serpapi"})


class UrlFetchTool(BaseTool):
    """网页正文抓取工具：剥离脚本/样式，输出纯文本。"""

    name = "url_fetch"
    description = "抓取网页正文文本。参数: url=str（仅限公网 http/https）"

    def run(self, url: str) -> ToolResult:
        url = (url or "").strip()
        if not re.match(r"^https?://", url):
            return ToolResult(ok=False, text=f"仅支持 http/https 地址，收到: {url!r}")
        host = httpx.URL(url).host or ""
        if _BLOCKED_HOST_RE.match(host):
            return ToolResult(ok=False, text=f"拒绝访问内网/本机地址: {host}")
        try:
            resp = httpx.get(url, timeout=HTTP_TIMEOUT, follow_redirects=True,
                             headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(ok=False, text=f"抓取失败 {url}: {exc}")
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            tag.decompose()
        text = re.sub(r"\n{3,}", "\n\n", soup.get_text(separator="\n")).strip()
        return ToolResult(ok=True, text=_truncate(text) or "（页面无可提取正文）",
                          meta={"url": url, "chars": len(text)})
