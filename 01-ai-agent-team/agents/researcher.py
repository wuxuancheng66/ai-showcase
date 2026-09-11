"""研究员 Agent：联网搜索 + 网页抓取 + PDF/本地文件解析，产出带引用的研究笔记。"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from agents.base_agent import BaseAgent
from core.state import AgentState

__all__ = ["ResearcherAgent"]

# 任务文本中出现的本地文件路径（相对沙箱根目录）
_FILE_TOKEN_RE = re.compile(
    r"[\w.\-/\u4e00-\u9fff]+?\.(html?|md|py|css|js|json|csv|txt|pdf|xlsx?)\b", re.IGNORECASE
)


class ResearcherAgent(BaseAgent):
    """根据输入类型自动选择工具：URL→抓取、本地文件→读取、主题→联网搜索。"""

    name = "researcher"
    description = "信息收集与交叉验证，产出带来源编号的研究笔记"

    def run(self, state: AgentState, step: Dict[str, Any]) -> Dict[str, Any]:
        source = str(state.get("task", "")).strip()
        step_text = f"{source} {step.get('task', '')}"
        tool_logs: List[str] = []
        collected: List[str] = []

        # 1) 任务中提到的本地文件 → file_read（按存在性判定，支持任意扩展名）
        seen: set = set()
        for token in _FILE_TOKEN_RE.finditer(step_text):
            path = token.group(0).strip("。，,；;：:）(）\"'`")
            if path in seen:
                continue
            seen.add(path)
            if re.match(r"^https?://", path):
                continue
            res = self.call_tool("file_read", path=path)
            tool_logs.append(f"file_read({path}) ok={res.ok}")
            if res.ok:
                collected.append(f"## 本地文件内容（{path}）\n{res.text}")

        # 2) URL → 抓取
        for url in re.findall(r"https?://[^\s，,；;）)\"']+", step_text):
            res = self.call_tool("url_fetch", url=url)
            tool_logs.append(f"url_fetch({url[:60]}) ok={res.ok}")
            collected.append(f"## 网页内容（{url}）\n{res.text}")

        # 3) PDF（显式 .pdf 路径已在步骤 1 处理；此处兜底单文件任务）
        if not collected and source.lower().endswith(".pdf"):
            res = self.call_tool("pdf_read", path=source)
            tool_logs.append(f"pdf_read ok={res.ok}")
            collected.append(f"## PDF 内容（{source}）\n{res.text}")

        # 4) 都没有 → 联网搜索
        if not collected:
            query = (step.get("query") or source or step.get("task", ""))[:200]
            res = self.call_tool("web_search", query=query,
                                 max_results=int(step.get("max_results", 5)))
            tool_logs.append(f"web_search ok={res.ok}")
            collected.append(f"## 搜索结果（query={query}）\n{res.text}")

        user = (
            f"## 任务\n{step.get('task', '收集并整理相关资料')}\n\n"
            f"## 工具收集到的原始材料\n" + "\n\n".join(collected) + "\n\n"
            "## 输出要求\n"
            "基于以上材料完成任务要求的信息提炼；引用具体文件时给出准确的文件内位置"
            "（章节/行/代码片段），关键事实后标注来源编号 [n]，文末列『## 来源』清单"
            "（本地文件注明路径）；材料不足时如实说明，禁止编造。"
        )
        text = self.client.invoke(self.system_prompt, user)
        self.memory.write(self.name, step.get("output_key", "research_notes"), text)
        return {"artifact": text, "tools_used": tool_logs}
