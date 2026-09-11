"""tools 包：联网搜索、文件读写、PDF 解析等工具与默认注册表。"""
from __future__ import annotations

import os
from pathlib import Path

from core.base import ToolRegistry

from .file_operations import FileReadTool, FileWriteTool
from .pdf_reader import PdfReadTool
from .web_search import UrlFetchTool, WebSearchTool

__all__ = ["build_default_tools", "WebSearchTool", "UrlFetchTool",
           "FileReadTool", "FileWriteTool", "PdfReadTool"]


def _sandbox_root() -> Path:
    """文件工具沙箱根目录：WORKSPACE_ROOT 环境变量（支持 ~），默认项目当前目录。"""
    return Path(os.getenv("WORKSPACE_ROOT", ".")).expanduser().resolve()


def build_default_tools() -> ToolRegistry:
    """构建默认工具注册表（文件工具以 WORKSPACE_ROOT 为沙箱）。"""
    registry = ToolRegistry()
    root = _sandbox_root()
    for tool in (
        WebSearchTool(),
        UrlFetchTool(),
        FileReadTool(base_dir=root),
        FileWriteTool(base_dir=root),
        PdfReadTool(base_dir=root),
    ):
        registry.register(tool)
    return registry
