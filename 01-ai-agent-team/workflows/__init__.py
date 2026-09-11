"""三条预置高质量工作流定义。

工作流 = 确定性的步骤模板（LLM 只负责执行步骤，不负责规划），
比动态规划更稳定、可复现；步骤中的 ``{input}`` 占位符会在运行时
被用户输入替换。reviewer 审校不在步骤中显式出现——每个步骤完成后
由编排器自动送审，不通过自动重做。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

__all__ = ["WorkflowDef", "WORKFLOWS"]


@dataclass
class WorkflowDef:
    """一条工作流的定义。"""

    key: str
    name: str
    description: str
    steps: List[Dict] = field(default_factory=list)


WORKFLOW_A = WorkflowDef(
    key="A",
    name="知识萃取",
    description="输入 URL/PDF/主题 → 提炼核心观点 → 思维导图 → Anki 记忆卡片",
    steps=[
        {
            "agent": "researcher",
            "task": "针对输入材料「{input}」完成知识萃取的第一步：先获取内容"
                    "（URL 用 url_fetch、PDF 用 pdf_read、主题用 web_search），"
                    "再提炼核心观点、关键数据与结论，标注来源编号并附来源清单。",
            "output_key": "research_notes",
            "require_citations": True,
        },
        {
            "agent": "analyst",
            "task": "基于研究笔记整理：1) 层级思维导图（Markdown 嵌套列表）；"
                    "2) 3-5 条关键洞察；3) 需进一步核实的存疑点清单。",
            "output_key": "mindmap",
            "input_from": ["research_notes"],
        },
        {
            "agent": "writer",
            "task": "基于研究笔记与思维导图产出学习包：1) 一页速览（TL;DR）；"
                    "2) 10-20 张 Anki 卡片，每张格式为『### 卡片N』下接"
                    "『问题：』与『答案：』两行；3) 卡片将自动导出为 CSV。",
            "output_key": "anki_cards",
            "input_from": ["research_notes", "mindmap"],
            "deliver": "anki",
        },
    ],
)

WORKFLOW_B = WorkflowDef(
    key="B",
    name="代码开发",
    description="需求描述 → 架构设计 → 分模块实现+单元测试 → README",
    steps=[
        {
            "agent": "coder",
            "task": "根据需求「{input}」完成架构设计：模块划分、数据流、"
                    "技术选型理由、目录结构（逐文件说明职责）与非功能考虑"
                    "（错误处理、安全、性能）。",
            "output_key": "architecture",
        },
        {
            "agent": "coder",
            "task": "严格按照架构文档分模块实现完整代码，并编写 pytest 单元测试；"
                    "每个文件一个代码块，块首行标注『# file: 相对路径』。",
            "output_key": "implementation",
            "input_from": ["architecture"],
        },
        {
            "agent": "writer",
            "task": "基于架构与实现产出 README.md：项目简介、功能列表、安装步骤、"
                    "快速上手示例、API/配置说明、FAQ。",
            "output_key": "readme",
            "input_from": ["architecture", "implementation"],
        },
    ],
)

WORKFLOW_C = WorkflowDef(
    key="C",
    name="内容创作",
    description="选题方向 → 收集素材 → 初稿 → 润色终稿+配图建议+发布文案",
    steps=[
        {
            "agent": "researcher",
            "task": "围绕选题「{input}」收集创作素材：用 web_search 检索最新资料、"
                    "数据与案例，整理为带来源编号的素材清单（观点/数据/金句分组）。",
            "output_key": "material",
            "require_citations": True,
        },
        {
            "agent": "writer",
            "task": "基于素材撰写初稿：拟定标题与小节结构，观点有数据支撑，"
                    "语言有感染力，保留来源标注。",
            "output_key": "draft",
            "input_from": ["material"],
        },
        {
            "agent": "writer",
            "task": "在初稿基础上完成终稿发布包：1) 润色后的终稿；"
                    "2) 配图建议（每节 1 张：主题+构图+风格）；"
                    "3) 微信公众号版与小红书版发布文案各一版。",
            "output_key": "publish_pack",
            "input_from": ["draft", "material"],
        },
    ],
)

WORKFLOWS: Dict[str, WorkflowDef] = {
    WORKFLOW_A.key: WORKFLOW_A,
    WORKFLOW_B.key: WORKFLOW_B,
    WORKFLOW_C.key: WORKFLOW_C,
}
