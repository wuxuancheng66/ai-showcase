"""数据分析师 Agent：CSV 统计摘要 + 素材结构化 + 思维导图/洞察产出。"""
from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from core.state import AgentState

__all__ = ["AnalystAgent", "summarize_csv"]


def summarize_csv(text: str, max_cols: int = 20) -> Optional[str]:
    """对 CSV 文本做零依赖统计摘要（数值列的计数/均值/最值/求和）。"""
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        return None
    header = rows[0]
    data = [r for r in rows[1:] if any(cell.strip() for cell in r)]
    if not header or not data:
        return None
    numeric: Dict[int, List[float]] = {}
    for row in data:
        for idx, cell in enumerate(row[:max_cols]):
            try:
                numeric.setdefault(idx, []).append(float(cell))
            except ValueError:
                continue
    lines = [f"- 数据行数: {len(data)}；列数: {len(header)}"]
    for idx, values in sorted(numeric.items()):
        if len(values) < len(data) * 0.6:  # 数值占比过低的列不算数值列
            continue
        name = header[idx] if idx < len(header) else f"col{idx}"
        lines.append(
            f"- 列『{name}』: 均值={sum(values) / len(values):.4f}, "
            f"最小={min(values):.4g}, 最大={max(values):.4g}, 合计={sum(values):.4g}"
        )
    return "\n".join(lines) if len(lines) > 1 else None


class AnalystAgent(BaseAgent):
    """解读数据与素材，产出关键发现、明细表与结构化整理（如思维导图）。"""

    name = "analyst"
    description = "数据分析与结构化整理，产出洞察与思维导图"

    def run(self, state: AgentState, step: Dict[str, Any]) -> Dict[str, Any]:
        data_ctx = ""
        data_file = step.get("data_file")
        if data_file:
            res = self.call_tool("file_read", path=data_file)
            if res.ok:
                stats = summarize_csv(res.text)
                data_ctx = f"## 数据统计摘要（{data_file}）\n{stats or res.text[:6000]}"
            else:
                data_ctx = f"## 数据读取失败（{data_file}）\n{res.text}"

        artifacts = state.get("artifacts", {})
        context = self.build_context(artifacts, step.get("input_from"))
        data_section = data_ctx + "\n\n" if data_ctx else ""
        user = (
            f"## 任务\n{step.get('task', '分析并整理材料')}\n\n"
            f"{data_section}"
            f"## 上游材料\n{context}\n\n"
            "## 输出要求\n"
            "数字结论必须与输入数据一致；输出含关键发现、明细（Markdown 表格）"
            "与建议；思维导图用 Markdown 嵌套列表表达。"
        )
        text = self.client.invoke(self.system_prompt, user)
        self.memory.write(self.name, step.get("output_key", "analysis"), text)
        return {"artifact": text, "files": []}
