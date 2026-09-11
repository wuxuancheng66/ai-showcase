"""LLM 客户端封装：OpenAI 兼容接口 + Token 计量与预算控制。

安全设计：
* API Key 只从环境变量/.env 读取，永不写入代码或日志；
* :class:`TokenTracker` 记录每个 Agent 的 token 消耗并落盘 logs/usage.jsonl，
  供 monitor.py 可视化；超出 TOKEN_BUDGET 抛出 :class:`BudgetExceededError`，
  由编排层捕获后优雅终止，防止失控烧 token。
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("agent_team.llm")

__all__ = ["TokenTracker", "LLMClient", "BudgetExceededError"]


class BudgetExceededError(RuntimeError):
    """Token 总预算耗尽。"""


class TokenTracker:
    """按 Agent 统计 token 消耗，逐次调用追加到 logs/usage.jsonl。"""

    def __init__(self, path: os.PathLike = "logs/usage.jsonl", budget: int = 0) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._budget = int(budget)
        self._totals: Dict[str, Dict[str, int]] = {}

    def record(self, agent: str, model: str, input_tokens: int, output_tokens: int) -> None:
        """记录一次 LLM 调用的消耗；超预算时抛出 BudgetExceededError。"""
        entry = self._totals.setdefault(agent, {"input": 0, "output": 0, "calls": 0})
        entry["input"] += input_tokens
        entry["output"] += output_tokens
        entry["calls"] += 1
        try:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "agent": agent, "model": model,
                    "input_tokens": input_tokens, "output_tokens": output_tokens,
                }, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("usage 落盘失败: %s", exc)
        if self._budget and self.grand_total() > self._budget:
            raise BudgetExceededError(
                f"Token 预算耗尽：已用 {self.grand_total()} > 预算 {self._budget}"
            )

    def agent_totals(self) -> Dict[str, Dict[str, int]]:
        return {k: dict(v) for k, v in self._totals.items()}

    def grand_total(self) -> int:
        return sum(v["input"] + v["output"] for v in self._totals.values())

    @property
    def budget(self) -> int:
        return self._budget


class LLMClient:
    """单个 Agent 专属的 LLM 会话客户端。

    Args:
        agent_name: Agent 名称（用于 token 归账）。
        model: 模型名（任何 OpenAI 兼容模型）。
        temperature: 采样温度。
        tracker: Token 计量器。
        llm: 直接注入的聊天模型实例（测试用）；为 None 时按环境变量
            构建 ``ChatOpenAI``（OPENAI_API_KEY / OPENAI_BASE_URL）。
    """

    def __init__(
        self,
        agent_name: str,
        model: str,
        temperature: float = 0.3,
        tracker: Optional[TokenTracker] = None,
        llm: Optional[Any] = None,
    ) -> None:
        self.agent_name = agent_name
        self.model = model
        self.temperature = temperature
        self.tracker = tracker
        if llm is not None:
            self._llm = llm
        else:
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            if not api_key:
                raise RuntimeError(
                    "缺少 OPENAI_API_KEY：请 cp .env.example .env 并填写。"
                    "支持 OpenAI / DeepSeek / 通义千问 / 智谱GLM 等 OpenAI 兼容接口。"
                )
            from langchain_openai import ChatOpenAI  # 延迟导入，加快 CLI 启动

            self._llm = ChatOpenAI(
                model=model,
                temperature=temperature,
                api_key=api_key,
                base_url=(os.getenv("OPENAI_BASE_URL", "").strip() or None),
                # 推理模型（如 DeepSeek V4）单步可能思考 1-3 分钟，默认放宽到 5 分钟
                timeout=int(os.getenv("LLM_TIMEOUT", "300")),
                max_retries=3,
            )

    def invoke(self, system: str, user: str) -> str:
        """执行一次对话：system 提示词 + user 输入，返回文本并自动记账。"""
        from langchain_core.messages import HumanMessage, SystemMessage

        resp = self._llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        usage: Dict[str, Any] = getattr(resp, "usage_metadata", None) or {}
        if self.tracker is not None:
            self.tracker.record(
                self.agent_name, self.model,
                int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0)),
            )
        content = resp.content
        if isinstance(content, list):  # 多模态返回时提取纯文本部分
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return str(content).strip()
