"""Agent 基类：封装系统提示词、上下文拼装与工具调用助手。

接口规范：子类实现 ``run(state, step)``，返回 dict，至少包含：
* ``artifact``: 本步骤产出的 Markdown 文本；
* 其余键为元信息（citation_issues / files / tools_used ...），
  会写入 AgentState.artifact_meta 供审校与落盘使用。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.base import ToolRegistry, ToolResult
from core.llm import LLMClient
from core.memory import SharedMemory
from core.state import AgentState

__all__ = ["BaseAgent"]

CONTEXT_ITEM_LIMIT = 8000  # 单个上游产物注入提示词的最大字符数


class BaseAgent:
    """所有 Agent 的基类。"""

    name: str = "base"
    description: str = ""

    def __init__(
        self,
        client: LLMClient,
        tools: ToolRegistry,
        memory: SharedMemory,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.client = client
        self.tools = tools
        self.memory = memory
        self.config = config or {}

    # ---------- 提示词与上下文 ----------
    @property
    def system_prompt(self) -> str:
        """系统提示词：来自 agent_config.yaml，缺失时用兜底文案。"""
        return (self.config.get("system_prompt") or "").strip() or "你是一名严谨的专业助手。"

    def build_context(
        self, artifacts: Dict[str, str], keys: Optional[List[str]] = None
    ) -> str:
        """把上游产物拼装为提示词上下文；keys 为空时取全部产物。"""
        keys = keys or list(artifacts)
        blocks = []
        for key in keys:
            content = artifacts.get(key)
            if content:
                blocks.append(f"### 上游产物 [{key}]\n{content[:CONTEXT_ITEM_LIMIT]}")
        return "\n\n".join(blocks) or "（无上游产物）"

    # ---------- 工具调用 ----------
    def call_tool(self, name: str, **kwargs: Any) -> ToolResult:
        """按名称调用工具；未注册时返回失败结果（不抛异常）。"""
        if not self.tools.has(name):
            return ToolResult(ok=False, text=f"工具未注册: {name}")
        try:
            return self.tools.get(name).run(**kwargs)
        except Exception as exc:  # noqa: BLE001 工具异常绝不打断流水线
            return ToolResult(ok=False, text=f"工具 {name} 执行异常: {exc}")

    # ---------- 核心执行 ----------
    def run(self, state: AgentState, step: Dict[str, Any]) -> Dict[str, Any]:
        """执行本步骤。子类必须实现，返回 {"artifact": str, ...meta}。"""
        raise NotImplementedError
