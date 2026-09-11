"""总控调度器（Orchestrator）：任务分解、分发、审校回流与结果落盘。

执行图（LangGraph 状态机）::

    START → init → dispatcher ⇄ researcher/writer/coder/analyst
                       ↑              ↓ (每步产物)
                       └── review ←───┘   审校不通过→重做当前步(有上限)
                       (通过→推进下一步) → ... → finalize → END

职责边界：
* 预置工作流：直接执行确定性步骤模板，LLM 只做执行者（稳定可复现）；
* 自定义任务：LLM 动态分解为步骤，解析失败时回退默认流水线
  （researcher → writer），保证任何情况下都有可用计划；
* 每个步骤的产物自动送 reviewer 审校，fail 且未超重试上限时回到
  同一步骤重做；所有产物与 summary.json 落盘到 outputs/<时间戳>_<工作流>/。
"""
from __future__ import annotations

import copy
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml
from langgraph.graph import END, START, StateGraph

from agents import AGENT_REGISTRY
from core.base import ToolRegistry
from core.llm import BudgetExceededError, LLMClient, TokenTracker
from core.memory import SharedMemory, create_memory
from core.state import AgentState
from tools import build_default_tools
from workflows import WORKFLOWS

logger = logging.getLogger("agent_team.orchestrator")

__all__ = ["Orchestrator", "log_task"]

PLAN_SYSTEM = (
    "你是严谨的任务规划器。把用户任务分解为 2-6 个顺序步骤，"
    "每步交给一个最合适的 Agent 执行。只输出 JSON 数组，"
    '元素形如 {"agent": "角色名", "task": "该步骤要做什么的清晰指令", '
    '"output_key": "产物英文标识"}，不要输出任何其他文字。'
)

TASKS_LOG = Path("logs/tasks.jsonl")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _evt(event: str, **fields: Any) -> Dict[str, Any]:
    return {"ts": _now(), "event": event, **fields}


def log_task(event: str, **fields: Any) -> None:
    """追加一条任务事件到 logs/tasks.jsonl（monitor.py 的数据源）。"""
    try:
        TASKS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with TASKS_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": _now(), "event": event, **fields},
                                ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning("tasks 事件落盘失败: %s", exc)


class Orchestrator:
    """多智能体流水线总控。

    Args:
        config_path: agent_config.yaml 路径。
        llm_factory: ``(agent_name, settings) -> chat_model | None``，
            返回 None 时由 LLMClient 按环境变量构建真实模型（测试可注入假模型）。
        tools/memory/tracker: 可选注入，默认按配置自动构建。
    """

    def __init__(
        self,
        config_path: os.PathLike = "agent_config.yaml",
        llm_factory: Optional[Callable[[str, Dict[str, Any]], Optional[Any]]] = None,
        tools: Optional[ToolRegistry] = None,
        memory: Optional[SharedMemory] = None,
        tracker: Optional[TokenTracker] = None,
    ) -> None:
        with open(config_path, "r", encoding="utf-8") as fh:
            self.config: Dict[str, Any] = yaml.safe_load(fh) or {}

        budget = int(os.getenv("TOKEN_BUDGET", "0") or 0)
        self.tracker = tracker or TokenTracker(path="logs/usage.jsonl", budget=budget)
        self.tools = tools or build_default_tools()
        self.memory = memory or create_memory()
        self._llm_factory = llm_factory or (lambda name, settings: None)

        agent_cfg = self.config.get("agents") or {}
        self.agents = {
            name: cls(self._make_client(name), self.tools, self.memory, agent_cfg.get(name))
            for name, cls in AGENT_REGISTRY.items()
        }
        orch = self.config.get("orchestrator") or {}
        self.max_steps = int(orch.get("max_steps", 12))
        self.max_retries = int((self.config.get("defaults") or {}).get("max_retries", 2))
        self._planner = self._make_client("orchestrator")
        self._graph = self._build_graph()

    # ------------------------------------------------------------------ 配置
    def _make_client(self, name: str) -> LLMClient:
        if name == "orchestrator":
            section = dict(self.config.get("orchestrator") or {})
        else:
            section = dict((self.config.get("agents") or {}).get(name) or {})
        defaults = self.config.get("defaults") or {}
        model = (section.get("model") or defaults.get("model")
                 or os.getenv("DEFAULT_MODEL") or "gpt-4o-mini")
        temperature = float(section.get("temperature", defaults.get("temperature", 0.3)))
        return LLMClient(agent_name=name, model=model, temperature=temperature,
                         tracker=self.tracker, llm=self._llm_factory(name, section))

    # ------------------------------------------------------------------ 计划
    def plan(self, task: str, workflow: Optional[str] = None) -> List[Dict[str, Any]]:
        """生成执行计划：预置工作流模板或 LLM 动态分解，并做规范化校验。"""
        if workflow:
            wf = WORKFLOWS.get(workflow.upper())
            if wf is None:
                raise KeyError(f"未知工作流 {workflow!r}，可选: {sorted(WORKFLOWS)}")
            steps = copy.deepcopy(wf.steps)
            for s in steps:
                s["task"] = s["task"].replace("{input}", task[:2000])
        else:
            steps = self._llm_plan(task)

        steps = steps[: self.max_steps]
        normalized: List[Dict[str, Any]] = []
        for idx, step in enumerate(steps):
            agent = str(step.get("agent", "")).strip()
            if agent not in AGENT_REGISTRY:
                raise ValueError(f"计划包含未知 Agent: {agent!r}")
            if agent == "reviewer":
                raise ValueError("reviewer 是自动审校角色，不能出现在计划步骤中")
            out_key = str(step.get("output_key") or f"{agent}_{idx}").strip()
            if any(out_key == n["output_key"] for n in normalized):
                out_key = f"{out_key}_{idx}"
            normalized.append({**step, "agent": agent, "task": str(step.get("task", "")),
                               "output_key": out_key})
        return normalized

    def _llm_plan(self, task: str) -> List[Dict[str, Any]]:
        """LLM 动态规划；解析失败时回退默认流水线，绝不空转。"""
        available = ", ".join(k for k in AGENT_REGISTRY if k != "reviewer")
        user = (
            "可用 Agent: " + available + "\n"
            "用户任务: " + task[:2000] + "\n"
            '请输出 JSON 数组，元素形如 {"agent":"researcher","task":"...","output_key":"..."}'
        )
        try:
            raw = self._planner.invoke(PLAN_SYSTEM, user)
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            data = json.loads(match.group(0)) if match else None
            if isinstance(data, list) and data and all(
                isinstance(x, dict) and x.get("agent") for x in data
            ):
                return data
            logger.warning("规划输出不合法，回退默认流水线")
        except BudgetExceededError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM 规划失败，回退默认流水线: %s", exc)
        return [
            {"agent": "researcher",
             "task": "收集并核实与任务相关的事实信息，标注来源。原始任务：" + task[:300],
             "output_key": "research_notes", "require_citations": True},
            {"agent": "writer",
             "task": "基于研究笔记完成任务并输出 Markdown 成品。原始任务：" + task[:1000],
             "output_key": "deliverable", "input_from": ["research_notes"]},
        ]

    # ------------------------------------------------------------------ 执行图
    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("init", self._node_init)
        graph.add_node("dispatcher", self._node_dispatcher)
        for name in self.agents:
            if name != "reviewer":  # reviewer 仅作为自动审校节点，不进调度路由
                graph.add_node(name, self._make_agent_node(name))
        graph.add_node("review", self._node_review)
        graph.add_node("finalize", self._node_finalize)

        graph.add_edge(START, "init")
        graph.add_edge("init", "dispatcher")
        graph.add_conditional_edges("dispatcher", self._route_dispatch)
        for name in self.agents:
            if name != "reviewer":
                graph.add_edge(name, "review")
        graph.add_edge("review", "dispatcher")
        graph.add_edge("finalize", END)
        return graph.compile()

    def _route_dispatch(self, state: AgentState) -> str:
        plan = state.get("plan") or []
        index = state.get("step_index", 0)
        if index >= len(plan):
            return "finalize"
        return plan[index]["agent"]

    def _node_init(self, state: AgentState) -> Dict[str, Any]:
        return {"step_index": 0, "retries": 0, "status": "running",
                "history": [_evt("init", task=str(state.get("task", ""))[:120])]}

    def _node_dispatcher(self, state: AgentState) -> Dict[str, Any]:
        plan = state.get("plan") or []
        index = state.get("step_index", 0)
        if index >= len(plan):
            return {}
        step = dict(plan[index])
        step["index"] = index
        role_cn = {"researcher": "研究员", "writer": "写手", "coder": "代码助手",
                   "analyst": "数据分析师"}.get(step["agent"], step["agent"])
        # 推理模型单步可能耗时 1-3 分钟，打印进度行让用户知道流水线活着
        logger.info("▶ 步骤 %d/%d · %s 正在执行：%s",
                    index + 1, len(plan), role_cn, (step.get("task") or "")[:60])
        log_task("stage", task_id=Path(str(state.get("run_dir", ""))).name,
                 index=index, total=len(plan), agent=step["agent"])
        return {"current_step": step,
                "history": [_evt("stage", index=index, agent=step["agent"])]}

    def _make_agent_node(self, name: str):
        def _node(state: AgentState) -> Dict[str, Any]:
            step = state.get("current_step") or {}
            error: Optional[str] = None
            try:
                result = self.agents[name].run(state, step)
            except BudgetExceededError:
                raise
            except Exception as exc:  # noqa: BLE001 单步失败不拖垮整条流水线
                logger.exception("Agent %s 执行失败", name)
                error = str(exc)
                result = {"artifact": f"> ⚠️ 本步骤执行出错：{exc}", "files": []}
            key = step.get("output_key") or f"{name}_{state.get('step_index', 0)}"
            meta = {"agent": name, "task": step.get("task", ""),
                    "files": result.get("files", []),
                    "tools_used": result.get("tools_used", []),
                    "citation_issues": result.get("citation_issues", []),
                    "ts": _now()}
            updates: Dict[str, Any] = {
                "artifacts": {key: str(result.get("artifact", ""))},
                "artifact_meta": {key: meta},
                "history": [_evt("artifact", key=key, agent=name)],
            }
            if error:
                updates["errors"] = [{"step": key, "agent": name, "error": error}]
            return updates
        return _node

    def _node_review(self, state: AgentState) -> Dict[str, Any]:
        step = state.get("current_step") or {}
        key = step.get("output_key", "")
        try:
            review = self.agents["reviewer"].run(state, step)
        except BudgetExceededError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("审校节点异常，默认放行: %s", exc)
            review = {"verdict": "pass", "score": 5,
                      "issues": [f"审校异常，默认放行: {exc}"],
                      "fact_check": [], "logic_flaws": []}

        index = state.get("step_index", 0)
        retries = state.get("retries", 0)
        run_id = Path(str(state.get("run_dir", ""))).name
        verdict_cn = "✅ 通过" if review["verdict"] == "pass" else "❌ 打回重做"
        logger.info("%s 审校完成：%s（%d/10 分）%s",
                    "🔍" if review["verdict"] == "pass" else "🔁",
                    verdict_cn, review.get("score", 5),
                    f"问题: {review['issues'][0][:50]}" if review.get("issues") else "")
        log_task("review", task_id=run_id, key=key, verdict=review["verdict"],
                 score=review.get("score"))
        if review["verdict"] == "fail" and retries < self.max_retries:
            log_task("retry", task_id=run_id, key=key, attempt=retries + 1)
            return {"review": review, "retries": retries + 1,
                    "history": [_evt("review", key=key, verdict="fail",
                                     retry=retries + 1,
                                     issues=review.get("issues", [])[:3])]}
        return {"review": review, "step_index": index + 1, "retries": 0,
                "history": [_evt("review", key=key, verdict=review["verdict"],
                                 score=review.get("score"),
                                 issues=review.get("issues", [])[:3])]}

    def _node_finalize(self, state: AgentState) -> Dict[str, Any]:
        run_dir = Path(state.get("run_dir") or "outputs/run")
        saved: Dict[str, str] = {}
        for key, content in (state.get("artifacts") or {}).items():
            path = run_dir / "artifacts" / f"{key}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            saved[key] = str(path)
        summary = {
            "task": state.get("task"),
            "workflow": state.get("workflow"),
            "status": "completed",
            "plan": [{"agent": s.get("agent"), "task": s.get("task"),
                      "output_key": s.get("output_key")} for s in state.get("plan", [])],
            "final_review": state.get("review"),
            "errors": state.get("errors", []),
            "saved_files": saved,
            "token_usage": self.tracker.agent_totals(),
            "token_total": self.tracker.grand_total(),
        }
        (run_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        log_task("task_done", task_id=run_dir.name, status="completed",
                 tokens=self.tracker.grand_total())
        return {"status": "completed", "saved_files": saved,
                "history": [_evt("done", artifacts=len(saved))]}

    # ------------------------------------------------------------------ 对外入口
    def run(self, task: str, workflow: Optional[str] = None) -> Dict[str, Any]:
        """执行一次完整流水线，返回任务摘要（产物路径、token 消耗等）。"""
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = Path("outputs") / f"{stamp}_{workflow or 'custom'}"
        run_dir.mkdir(parents=True, exist_ok=True)
        log_task("task_start", task_id=run_dir.name, task=task[:200],
                 workflow=workflow or "custom")

        plan = self.plan(task, workflow)
        initial: Dict[str, Any] = {
            "task": task, "workflow": workflow or "", "plan": plan,
            "step_index": 0, "retries": 0, "current_step": {},
            "artifacts": {}, "artifact_meta": {}, "review": {},
            "history": [], "errors": [], "run_dir": str(run_dir),
            "status": "running", "saved_files": {},
        }
        try:
            final: Dict[str, Any] = self._graph.invoke(
                initial, config={"recursion_limit": 100})
        except BudgetExceededError as exc:
            log_task("task_done", task_id=run_dir.name, status="budget_exceeded",
                     error=str(exc), tokens=self.tracker.grand_total())
            return {"task_id": run_dir.name, "status": "budget_exceeded",
                    "run_dir": str(run_dir), "error": str(exc),
                    "token_total": self.tracker.grand_total()}

        return {
            "task_id": run_dir.name,
            "status": final.get("status", "completed"),
            "run_dir": str(run_dir),
            "artifacts": sorted((final.get("artifacts") or {})),
            "saved_files": final.get("saved_files", {}),
            "errors": final.get("errors", []),
            "token_usage": self.tracker.agent_totals(),
            "token_total": self.tracker.grand_total(),
        }
