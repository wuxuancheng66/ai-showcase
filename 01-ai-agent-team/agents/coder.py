"""代码助手 Agent：架构设计 / 分模块实现 / 单元测试，代码块自动落盘。"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from agents.base_agent import BaseAgent
from core.state import AgentState

logger = logging.getLogger("agent_team.agents.coder")

__all__ = ["CoderAgent", "extract_code_blocks"]

# 匹配 ```python 且首行带 "# file: 相对路径" 的代码块
CODE_BLOCK_RE = re.compile(
    r"```[a-zA-Z0-9_+-]*\s*\n#\s*file:\s*(?P<path>\S+)[^\n]*\n(?P<code>.*?)```",
    re.DOTALL,
)


def extract_code_blocks(text: str) -> List[Dict[str, str]]:
    """从产物中提取带 ``# file:`` 标注的代码块列表。"""
    return [{"path": m.group("path"), "code": m.group("code")}
            for m in CODE_BLOCK_RE.finditer(text)]


class CoderAgent(BaseAgent):
    """编写生产级代码；带文件标注的代码块自动写入 run_dir/code/。"""

    name = "coder"
    description = "架构设计、分模块编码与单元测试"

    def run(self, state: AgentState, step: Dict[str, Any]) -> Dict[str, Any]:
        artifacts = state.get("artifacts", {})
        context = self.build_context(artifacts, step.get("input_from"))
        user = (
            f"## 任务\n{step.get('task', '完成编码任务')}\n\n"
            f"## 参考资料\n{context}\n\n"
            "## 输出要求\n"
            "代码必须完整可运行（Python 3.10+，含 Type Hints 与 docstring）；"
            "每个文件放在独立 fenced code block 中，且块内第一行写"
            "『# file: 相对路径』；测试使用 pytest。"
        )
        text = self.client.invoke(self.system_prompt, user)
        files = self._persist_code(text, str(state.get("run_dir", "outputs")))
        self.memory.write(self.name, step.get("output_key", "code"), text)
        return {"artifact": text, "files": files}

    def _persist_code(self, text: str, run_dir: str) -> List[str]:
        """把标注的代码块写入沙箱内文件；路径不安全时跳过并告警。"""
        saved: List[str] = []
        for block in extract_code_blocks(text):
            rel = block["path"].lstrip("/")
            if ".." in Path(rel).parts:
                logger.warning("跳过不安全路径的代码块: %s", rel)
                continue
            path = f"{run_dir}/code/{rel}"
            res = self.call_tool("file_write", path=path, content=block["code"])
            if res.ok:
                saved.append(path)
        return saved
