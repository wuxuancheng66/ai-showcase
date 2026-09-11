"""PDF 文本提取工具（pypdf，延迟导入）。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

from core.base import BaseTool, ToolResult
from tools.file_operations import resolve_sandboxed

logger = logging.getLogger("agent_team.tools.pdf")

__all__ = ["PdfReadTool"]

MAX_PAGES = 50
MAX_CHARS = 30000


class PdfReadTool(BaseTool):
    """提取 PDF 文本：前 50 页、最多 30000 字符，防止撑爆上下文。"""

    name = "pdf_read"
    description = "提取 PDF 文本。参数: path=str(相对路径)"

    def __init__(self, base_dir: Union[str, Path]) -> None:
        self.base_dir = Path(base_dir).resolve()

    def run(self, path: str) -> ToolResult:
        try:
            target = resolve_sandboxed(self.base_dir, path)
        except ValueError as exc:
            return ToolResult(ok=False, text=str(exc))
        if not target.is_file():
            return ToolResult(ok=False, text=f"文件不存在: {path}")
        try:
            from pypdf import PdfReader  # 延迟导入，未安装时不影响其他功能

            reader = PdfReader(str(target))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(ok=False, text=f"PDF 解析失败（请确认是有效 PDF 且已安装 pypdf）: {exc}")
        chunks = []
        total = 0
        for page in reader.pages[:MAX_PAGES]:
            chunk = (page.extract_text() or "").strip()
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_CHARS:
                break
        text = "\n\n".join(c for c in chunks if c)
        return ToolResult(ok=True, text=text[:MAX_CHARS] or "（PDF 无可提取文本，可能是扫描件）",
                          meta={"pages": min(len(reader.pages), MAX_PAGES), "chars": len(text)})
