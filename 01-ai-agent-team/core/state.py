"""全局共享状态（AgentState）定义。

LangGraph 中所有节点共享同一份状态；字典/列表字段通过 reducer 合并，
保证并行或回溯执行时不会互相覆盖。
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, TypedDict

__all__ = ["AgentState", "merge_dict", "merge_list"]


def merge_dict(left: Dict[Any, Any], right: Dict[Any, Any]) -> Dict[Any, Any]:
    """字典合并 reducer：右侧覆盖同名键。"""
    return {**(left or {}), **(right or {})}


def merge_list(left: List[Any], right: List[Any]) -> List[Any]:
    """列表追加 reducer。"""
    return (left or []) + (right or [])


class AgentState(TypedDict, total=False):
    """流水线全局状态。

    字段说明：
    * ``task``            用户原始任务描述；
    * ``workflow``        预置工作流标识（A/B/C），自定义任务为空串；
    * ``plan``            任务计划：[{"agent","task","output_key","input_from",...}]；
    * ``step_index``      当前执行到的步骤下标；
    * ``retries``         当前步骤的审校重试次数；
    * ``current_step``    正在执行的步骤（dispatcher 节点写入）；
    * ``artifacts``       各步骤产物：output_key -> Markdown 文本；
    * ``artifact_meta``   产物元信息：agent、引用校验、生成的文件清单等；
    * ``review``          最近一次审校结论 {"verdict","score","issues",...}；
    * ``history``         事件流水（init/stage/review/done），用于监控与回放；
    * ``errors``          节点级错误收集（不中断流水线）；
    * ``run_dir``         本次运行的输出目录 outputs/<时间戳>_<工作流>；
    * ``status``          running / completed。
    """

    task: str
    workflow: str
    plan: List[Dict[str, Any]]
    step_index: int
    retries: int
    current_step: Dict[str, Any]
    artifacts: Annotated[Dict[str, str], merge_dict]
    artifact_meta: Annotated[Dict[str, Dict[str, Any]], merge_dict]
    review: Dict[str, Any]
    history: Annotated[List[Dict[str, Any]], merge_list]
    errors: Annotated[List[Dict[str, Any]], merge_list]
    run_dir: str
    status: str
    saved_files: Dict[str, str]
