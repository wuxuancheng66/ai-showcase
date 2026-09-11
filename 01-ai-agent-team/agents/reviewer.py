"""审校员 Agent：事实核查 + 逻辑漏洞检测，输出结构化 JSON 裁决。

裁决协议（稳定运行的关键）：
* LLM 必须输出 {"verdict":"pass|fail","score":0-10,"issues":[],...}；
* 输出无法解析时**默认放行**并记录告警——宁可有瑕疵通过，也不让流水线
  因解析失败而卡死循环；
* 写手标记的 citation_issues 会并入审校意见；require_citations 步骤
  存在引用缺失时强制 fail，触发重写。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from core.state import AgentState

logger = logging.getLogger("agent_team.agents.reviewer")

__all__ = ["ReviewerAgent", "extract_verdict"]


def extract_verdict(raw: str) -> Optional[Dict[str, Any]]:
    """从 LLM 输出中提取 JSON 裁决；失败返回 None。"""
    raw = raw.strip()
    candidates = [raw]
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        candidates.insert(0, match.group(0))
    for cand in candidates:
        try:
            data = json.loads(cand)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            continue
    return None


class ReviewerAgent(BaseAgent):
    """质量把关：每个执行步骤完成后自动审校，不通过则触发重做。"""

    name = "reviewer"
    description = "事实核查与逻辑漏洞检测，输出 pass/fail 裁决"

    def run(self, state: AgentState, step: Dict[str, Any]) -> Dict[str, Any]:
        key = step.get("output_key", "")
        artifacts = state.get("artifacts", {})
        content = artifacts.get(key) or (list(artifacts.values())[-1] if artifacts else "")
        meta = (state.get("artifact_meta") or {}).get(key, {})
        pre_issues: List[str] = list(meta.get("citation_issues") or [])

        user = (
            f"## 产出要求\n{step.get('task', '')}\n\n"
            f"## 待审内容\n{content[:12000]}\n\n"
            "请按要求只输出一个 JSON 对象。"
        )
        try:
            raw = self.client.invoke(self.system_prompt, user)
        except Exception as exc:  # noqa: BLE001 审校器故障不阻塞流水线
            logger.warning("审校 LLM 调用失败，默认放行: %s", exc)
            return {"verdict": "pass", "score": 5,
                    "issues": pre_issues + [f"审校器异常，默认放行: {exc}"],
                    "fact_check": [], "logic_flaws": []}

        data = extract_verdict(raw)
        if data is None:
            return {"verdict": "pass", "score": 5,
                    "issues": pre_issues + ["审校输出无法解析为 JSON，默认放行"],
                    "fact_check": [], "logic_flaws": []}

        verdict = str(data.get("verdict", "pass")).lower()
        issues = pre_issues + [str(x) for x in (data.get("issues") or [])]
        if step.get("require_citations") and pre_issues:
            verdict = "fail"  # 声明要求引用的步骤缺引用 → 强制重写
        return {
            "verdict": "fail" if verdict == "fail" else "pass",
            "score": int(data.get("score", 5) or 5),
            "issues": issues,
            "fact_check": [str(x) for x in (data.get("fact_check") or [])],
            "logic_flaws": [str(x) for x in (data.get("logic_flaws") or [])],
        }
