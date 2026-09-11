"""本地文件读写工具（带沙箱与敏感文件黑名单）。

安全设计：
* 所有路径必须在 base_dir 沙箱内解析，拒绝绝对路径与 ``..`` 越界；
* 黑名单拦截 .env / 密钥文件 / .git 等敏感路径，防止密钥被读入 LLM 提示词外泄；
* 读文件限制大小，防止把超大文件塞爆上下文。
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Union

from core.base import BaseTool, ToolResult

logger = logging.getLogger("agent_team.tools.file")

__all__ = ["FileReadTool", "FileWriteTool", "resolve_sandboxed"]

MAX_READ_CHARS = 20000
MAX_READ_BYTES = 2 * 1024 * 1024  # 2MB

# 拒绝读写的敏感文件名/后缀
_DENY_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519", "id_ecdsa"}
_DENY_SUFFIX = (".pem", ".key", ".p12", ".pfx", ".ppk", ".kdbx")
_DENY_DIRS = {".git", ".ssh", ".gnupg"}


def resolve_sandboxed(base_dir: Union[str, Path], path: str) -> Path:
    """把用户传入的相对路径解析到沙箱内；越界/敏感路径直接抛 ValueError。

    Args:
        base_dir: 沙箱根目录。
        path: 相对路径（禁止绝对路径）。
    """
    base = Path(base_dir).resolve()
    if not path or Path(path).is_absolute():
        raise ValueError(f"必须使用相对路径，收到: {path!r}")
    target = (base / path).resolve()
    if base != target and base not in target.parents:
        raise ValueError(f"路径越界（沙箱外）: {path}")
    parts = set(target.parts)
    if parts & _DENY_DIRS:
        raise ValueError(f"禁止访问敏感目录: {path}")
    if target.name.lower() in _DENY_NAMES or target.name.lower().endswith(_DENY_SUFFIX):
        raise ValueError(f"禁止访问敏感文件: {path}")
    if re.search(r"\.env\.", target.name.lower()):
        raise ValueError(f"禁止访问敏感文件: {path}")
    return target


class FileReadTool(BaseTool):
    """读取沙箱内文本文件。"""

    name = "file_read"
    description = "读取本地文本文件。参数: path=str(相对路径)"

    def __init__(self, base_dir: Union[str, Path]) -> None:
        self.base_dir = Path(base_dir).resolve()

    def run(self, path: str) -> ToolResult:
        try:
            target = resolve_sandboxed(self.base_dir, path)
        except ValueError as exc:
            return ToolResult(ok=False, text=str(exc))
        if not target.is_file():
            return ToolResult(ok=False, text=f"文件不存在: {path}")
        if target.stat().st_size > MAX_READ_BYTES:
            return ToolResult(ok=False, text=f"文件超过 2MB 读取上限: {path}")
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return ToolResult(ok=False, text=f"读取失败: {exc}")
        return ToolResult(ok=True, text=text[:MAX_READ_CHARS],
                          meta={"path": str(target), "chars": len(text)})


class FileWriteTool(BaseTool):
    """向沙箱内写入文本文件（自动创建父目录）。"""

    name = "file_write"
    description = "写入文本文件（自动建目录）。参数: path=str(相对路径), content=str, overwrite=bool"

    def __init__(self, base_dir: Union[str, Path]) -> None:
        self.base_dir = Path(base_dir).resolve()

    def run(self, path: str, content: str, overwrite: bool = True) -> ToolResult:
        try:
            target = resolve_sandboxed(self.base_dir, path)
        except ValueError as exc:
            return ToolResult(ok=False, text=str(exc))
        if target.exists() and not overwrite:
            return ToolResult(ok=False, text=f"文件已存在且 overwrite=False: {path}")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            return ToolResult(ok=False, text=f"写入失败: {exc}")
        logger.info("file_write: %s (%d chars)", target, len(content))
        return ToolResult(ok=True, text=f"已写入 {path}（{len(content)} 字符）",
                          meta={"path": str(target)})
