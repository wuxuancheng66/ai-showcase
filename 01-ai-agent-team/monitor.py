"""简易监控台：Token 消耗与任务进度可视化。

数据源（均由系统自动落盘）:
* logs/usage.jsonl  —— 每次 LLM 调用的 token 记账
* logs/tasks.jsonl  —— 任务/阶段/审校/重试事件

用法::

    python monitor.py             # 输出一次当前状态
    python monitor.py --watch     # 每 5 秒刷新（Ctrl+C 退出）
    python monitor.py --interval 2 --last-tasks 10
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

USAGE_LOG = Path("logs/usage.jsonl")
TASKS_LOG = Path("logs/tasks.jsonl")

# 任务事件在状态列里的展示优先级
_STATUS_OF_EVENT = {"task_start": "运行中", "stage": "运行中", "task_done": "已结束"}


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """宽容读取 jsonl：文件不存在或个别行损坏都跳过。"""
    if not path.exists():
        return []
    items: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


def render(last_tasks: int) -> None:
    usage_rows = read_jsonl(USAGE_LOG)
    task_rows = read_jsonl(TASKS_LOG)

    console.clear()
    console.print(Panel("[bold cyan]AI Agent Team 监控台[/]", border_style="cyan"))

    # ---- Token 消耗 ----
    totals: Dict[str, Dict[str, int]] = defaultdict(lambda: {"calls": 0, "input": 0, "output": 0})
    for row in usage_rows:
        entry = totals[row.get("agent", "unknown")]
        entry["calls"] += 1
        entry["input"] += int(row.get("input_tokens", 0) or 0)
        entry["output"] += int(row.get("output_tokens", 0) or 0)

    table = Table(title="Token 消耗（按 Agent）", show_header=True, header_style="bold")
    for col in ("Agent", "调用次数", "输入 tokens", "输出 tokens", "合计"):
        table.add_column(col)
    grand = 0
    for agent, u in sorted(totals.items()):
        subtotal = u["input"] + u["output"]
        grand += subtotal
        table.add_row(agent, str(u["calls"]), str(u["input"]), str(u["output"]), str(subtotal))
    table.add_section()
    table.add_row("[bold]总计[/]", "", "", "", f"[bold]{grand}[/]")
    console.print(table)

    budget = int(os.getenv("TOKEN_BUDGET", "0") or 0)
    if budget:
        used_pct = min(100.0, grand * 100.0 / budget)
        bar = "█" * int(used_pct // 5) + "·" * (20 - int(used_pct // 5))
        console.print(f"预算 {budget}: [{bar}] {grand}/{budget} ({used_pct:.1f}%)")

    # ---- 任务进度 ----
    tasks_table = Table(title=f"最近 {last_tasks} 条任务事件", show_header=True,
                        header_style="bold")
    for col in ("时间", "任务", "事件", "详情"):
        tasks_table.add_column(col, overflow="fold")
    for row in task_rows[-last_tasks:]:
        detail_parts = []
        for key in ("agent", "index", "key", "verdict", "attempt", "status", "tokens"):
            if row.get(key) not in (None, ""):
                detail_parts.append(f"{key}={row[key]}")
        tasks_table.add_row(str(row.get("ts", "")), str(row.get("task_id", "")),
                            str(row.get("event", "")), " ".join(detail_parts))
    console.print(tasks_table)

    if not usage_rows and not task_rows:
        console.print("[dim]暂无数据：先运行 python main.py 跑一次任务。[/]")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Token 消耗与任务进度监控")
    parser.add_argument("--watch", action="store_true", help="持续刷新模式")
    parser.add_argument("--interval", type=int, default=5, help="刷新间隔秒数（默认5）")
    parser.add_argument("--last-tasks", type=int, default=15, help="展示最近 N 条事件")
    args = parser.parse_args()

    if not args.watch:
        render(args.last_tasks)
        return
    try:
        while True:
            render(args.last_tasks)
            time.sleep(max(1, args.interval))
    except KeyboardInterrupt:
        console.print("\n[dim]监控已退出。[/]")


if __name__ == "__main__":
    main()
