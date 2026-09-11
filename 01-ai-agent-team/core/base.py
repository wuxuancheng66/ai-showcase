"""工具调用接口规范（Tools Interface）。

所有工具继承 :class:`BaseTool`，通过 :class:`ToolRegistry` 统一注册与调用。
接口约定：

* 工具输入：``run(**kwargs)``，参数均为基本类型（str/int/bool）；
* 工具输出：:class:`ToolResult`，``ok=True/False`` 表示成败，
  ``text`` 为可直接拼入 LLM 提示词的文本，``meta`` 携带结构化附加信息；
* 工具**永不抛出异常**给 Agent：失败以 ``ok=False`` 返回，保证流水线稳定。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

__all__ = ["ToolResult", "BaseTool", "ToolRegistry"]


@dataclass
class ToolResult:
    """工具执行的统一返回结构。"""

    ok: bool
    text: str
    meta: Dict[str, Any] = field(default_factory=dict)


class BaseTool:
    """工具基类：子类设置 name/description 并实现 run()。"""

    name: str = "base"
    description: str = ""

    def run(self, **kwargs: Any) -> ToolResult:
        """执行工具。子类必须实现。"""
        raise NotImplementedError

    def spec(self) -> str:
        """返回给 LLM 看的工具说明（用于提示词）。"""
        return f"- {self.name}: {self.description}"


class ToolRegistry:
    """工具注册表：按名称注册、查找与执行工具。"""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册工具；重名视为配置错误，直接抛错防止误覆盖。"""
        if tool.name in self._tools:
            raise ValueError(f"工具重名: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        """按名称取工具，未注册时抛 KeyError。"""
        return self._tools[name]

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> List[str]:
        return sorted(self._tools)

    def describe(self) -> str:
        """渲染全部工具说明，供提示词注入。"""
        return "\n".join(t.spec() for t in self._tools.values())
