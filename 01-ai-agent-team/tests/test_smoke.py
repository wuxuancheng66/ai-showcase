"""离线冒烟测试：不访问网络、不需要 API Key，用脚本化假模型跑通全流程。

覆盖：
1. 计划生成（LLM 输出不合法时回退默认流水线）；
2. Agent 节点执行 → 自动审校 → 通过推进；
3. 产物落盘（artifacts/*.md + summary.json）；
4. 三条预置工作流的步骤合法性。
运行：python -m pytest tests -q
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from agents import AGENT_REGISTRY
from core.orchestrator import Orchestrator
from workflows import WORKFLOWS


class ScriptedLLM(BaseChatModel):
    """按顺序返回预设回复的假模型；超出后重复最后一条。"""

    replies: List[str] = []
    counter: int = 0

    def _generate(self, messages: List[BaseMessage], stop: List[str] = None,  # type: ignore[override]
                  run_manager: Any = None, **kwargs: Any) -> ChatResult:
        index = min(self.counter, len(self.replies) - 1)
        self.counter += 1
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.replies[index]))])

    @property
    def _llm_type(self) -> str:
        return "scripted-fake"


REPLIES: Dict[str, str] = {
    # 规划器输出非法 JSON → 触发默认流水线回退
    "orchestrator": "好的，我建议分两步：先研究再写作。",
    "researcher": (
        "## 核心观点\n\nZCode 是一个编程智能体 [1]。\n\n## 来源\n[1] https://example.com/zcode"
    ),
    "writer": (
        "## 速览\n\nZCode 是编程智能体 [1]。\n\n"
        "### 卡片1\n问题：ZCode 是什么？\n答案：一个编程智能体 [1]。\n\n"
        "## 来源\n[1] https://example.com/zcode"
    ),
    "analyst": "- 主题\n  - 观点A\n  - 观点B\n\n洞察：结构清晰。",
    "reviewer": '{"verdict":"pass","score":9,"issues":[],"fact_check":[],"logic_flaws":[]}',
    "coder": "架构：单模块。\n\n```python\n# file: demo.py\nprint('hi')\n```",
}


@pytest.fixture()
def orchestrator(tmp_path, monkeypatch):
    """在临时目录构建注入假模型的编排器（产物/日志不污染项目目录）。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TOKEN_BUDGET", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)  # 确保不触发真实调用

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

    def factory(agent_name: str, settings: Dict[str, Any]):
        return ScriptedLLM(replies=[REPLIES.get(agent_name, "ok")])

    return Orchestrator(config_path=os.path.join(root, "agent_config.yaml"),
                        llm_factory=factory)


def test_end_to_end_custom_task(orchestrator: Orchestrator):
    result = orchestrator.run("用一段话介绍 ZCode 并给出引用")
    assert result["status"] == "completed", result
    # 默认回退流水线：researcher → writer
    assert "research_notes" in result["artifacts"]
    assert "deliverable" in result["artifacts"]
    # 产物与摘要已落盘
    run_dir = result["run_dir"]
    assert os.path.exists(os.path.join(run_dir, "artifacts", "research_notes.md"))
    assert os.path.exists(os.path.join(run_dir, "artifacts", "deliverable.md"))
    assert os.path.exists(os.path.join(run_dir, "summary.json"))


def test_workflow_a_runs(orchestrator: Orchestrator):
    result = orchestrator.run("https://example.com/article", workflow="A")
    assert result["status"] == "completed", result
    for key in ("research_notes", "mindmap", "anki_cards"):
        assert key in result["artifacts"]


def test_workflow_definitions_are_valid():
    """三条工作流的每个步骤必须指向已注册且非 reviewer 的角色。"""
    assert set(WORKFLOWS) == {"A", "B", "C"}
    for wf in WORKFLOWS.values():
        assert wf.steps, wf.key
        for step in wf.steps:
            assert step["agent"] in AGENT_REGISTRY, (wf.key, step["agent"])
            assert step["agent"] != "reviewer"
            assert step.get("output_key")


def test_plan_rejects_unknown_agent(orchestrator: Orchestrator, monkeypatch):
    """规划器给出未知角色时，plan() 必须抛 ValueError。"""
    monkeypatch.setattr(orchestrator, "_llm_plan", lambda task: [{"agent": "nope", "task": "t"}])
    with pytest.raises(ValueError):
        orchestrator.plan("任意任务")
