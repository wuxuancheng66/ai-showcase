"""写手 Agent：Markdown 成稿 + 引用格式校验 + Anki 卡片 CSV 导出。"""
from __future__ import annotations

import csv
import io
import re
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from core.state import AgentState

__all__ = ["WriterAgent", "check_citations", "extract_anki_cards"]

_CARD_RE = re.compile(r"###\s*卡片\s*\d+.*?(?=\n###\s*卡片\s*\d+|\Z)", re.DOTALL)
_Q_RE = re.compile(r"问题\s*[:：]\s*(.+)")
_A_RE = re.compile(r"答案\s*[:：]\s*(.+)")


def check_citations(text: str, min_length: int = 200) -> List[str]:
    """引用格式校验：正文达到一定长度却没有任何 [n]/URL 引用时返回问题列表。"""
    if len(text) < min_length:
        return []
    if re.search(r"\[\d+\]", text) or re.search(r"https?://", text):
        return []
    return ["正文未包含任何来源引用（缺少 [编号] 或 URL），请补充来源标注。"]


def extract_anki_cards(text: str) -> List[Dict[str, str]]:
    """从 Markdown 中解析『### 卡片N / 问题：/ 答案：』格式的 Anki 卡片。"""
    cards: List[Dict[str, str]] = []
    for block in _CARD_RE.findall(text):
        q = _Q_RE.search(block)
        a = _A_RE.search(block)
        if q and a:
            cards.append({"front": q.group(1).strip(), "back": a.group(1).strip()})
    return cards


class WriterAgent(BaseAgent):
    """基于上游素材撰写 Markdown 成品，自动校验引用并按需导出 CSV。"""

    name = "writer"
    description = "撰写结构清晰的 Markdown 成品，保留引用并校验格式"

    def run(self, state: AgentState, step: Dict[str, Any]) -> Dict[str, Any]:
        artifacts = state.get("artifacts", {})
        context = self.build_context(artifacts, step.get("input_from"))
        user = (
            f"## 任务\n{step.get('task', '撰写文档')}\n\n"
            f"## 参考资料\n{context}\n\n"
            "## 输出要求\n"
            "输出 Markdown 成品：忠于素材事实、不引入无来源的新论断；"
            "沿用素材中的来源编号或 URL；标题层级清晰、善用列表与表格。"
        )
        text = self.client.invoke(self.system_prompt, user)
        issues = check_citations(text)
        files: List[str] = []

        if step.get("deliver") == "anki":
            csv_path = self._export_anki_csv(text, str(state.get("run_dir", "outputs")))
            if csv_path:
                files.append(csv_path)

        self.memory.write(self.name, step.get("output_key", "article"), text)
        return {"artifact": text, "citation_issues": issues, "files": files}

    def _export_anki_csv(self, text: str, run_dir: str) -> Optional[str]:
        """把解析出的卡片写入 anki_cards.csv（front,back），失败不阻塞。"""
        cards = extract_anki_cards(text)
        if not cards:
            return None
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["front", "back"])
        for card in cards:
            writer.writerow([card["front"], card["back"]])
        path = f"{run_dir}/anki_cards.csv"
        res = self.call_tool("file_write", path=path, content=buffer.getvalue())
        return path if res.ok else None
