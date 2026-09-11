"""命令行交互入口。

用法示例::

    python main.py                                  # 交互式菜单
    python main.py --workflow A --input "https://..."
    python main.py --workflow B --input "做一个TODO命令行应用"
    python main.py --task "帮我调研 LangGraph 的最新特性并写成报告"
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional, Tuple

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

console = Console()

BANNER = "[bold cyan]AI Agent Team[/] · 多智能体协作流水线\n研究员 · 写手 · 审校员 · 代码助手 · 数据分析师"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Agent Team 多智能体协作系统")
    parser.add_argument("--workflow", choices=["A", "B", "C"],
                        help="预置工作流：A=知识萃取 B=代码开发 C=内容创作")
    parser.add_argument("--input", dest="user_input",
                        help="工作流输入（URL / PDF 路径 / 主题 / 需求描述）")
    parser.add_argument("--task", help="自定义任务描述（动态分解为流水线）")
    parser.add_argument("--config", default="agent_config.yaml", help="配置文件路径")
    parser.add_argument("--verbose", action="store_true", help="输出 DEBUG 日志")
    return parser.parse_args()


def resolve_job(args: argparse.Namespace) -> Tuple[Optional[str], str]:
    """从命令行参数或交互式菜单得出 (workflow, task)。"""
    if args.workflow:
        if not args.user_input:
            console.print("[red]使用 --workflow 时必须提供 --input[/]")
            sys.exit(2)
        return args.workflow, args.user_input
    if args.task:
        return None, args.task

    console.print(Panel(BANNER, border_style="cyan"))
    console.print("[bold]请选择运行模式[/]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("选项", width=6)
    table.add_column("说明")
    table.add_row("A", "知识萃取：URL/PDF/主题 → 核心观点 → 思维导图 → Anki 卡片")
    table.add_row("B", "代码开发：需求 → 架构 → 分模块实现+测试 → README")
    table.add_row("C", "内容创作：选题 → 素材 → 初稿 → 终稿+配图建议+发布文案")
    table.add_row("T", "自定义任务：描述目标，规划器自动分解流水线")
    console.print(table)
    choice = Prompt.ask("选择", choices=["A", "B", "C", "T"], default="T").upper()
    if choice == "T":
        task = Prompt.ask("请描述你的任务")
        return None, task
    user_input = Prompt.ask("请输入 " + {"A": "URL / PDF 路径 / 主题",
                                         "B": "需求描述",
                                         "C": "选题方向"}[choice])
    return choice, user_input


def print_summary(result: dict) -> None:
    """渲染任务结果摘要。"""
    status = result.get("status")
    style = "green" if status == "completed" else "red"
    console.print(Panel(f"[{style}]任务状态: {status}[/]\n"
                        f"产物目录: {result.get('run_dir')}", border_style=style))
    for key in result.get("artifacts", []):
        console.print(f"  • 产物 [cyan]{key}[/]")
    for path in (result.get("saved_files") or {}).values():
        console.print(f"  📄 {path}")
    usage = result.get("token_usage") or {}
    if usage:
        table = Table(title="Token 消耗", show_header=True, header_style="bold")
        for col in ("Agent", "调用", "输入", "输出"):
            table.add_column(col)
        for agent, u in usage.items():
            table.add_row(agent, str(u["calls"]), str(u["input"]), str(u["output"]))
        console.print(table)
        console.print(f"  合计: [bold]{result.get('token_total', 0)}[/] tokens")
    if result.get("errors"):
        console.print("[yellow]部分步骤出现错误（已记录，未中断流水线）:[/]")
        for err in result["errors"]:
            console.print(f"  ⚠ {err.get('step')} ({err.get('agent')}): {err.get('error')}")


def main() -> int:
    load_dotenv()
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        workflow, task = resolve_job(args)

        # 延迟导入：保证 .env 已加载后再构建编排器
        from core.orchestrator import Orchestrator

        orchestrator = Orchestrator(config_path=args.config)
        result = orchestrator.run(task, workflow)
        print_summary(result)
        return 0 if result.get("status") == "completed" else 1
    except KeyboardInterrupt:
        console.print("\n[yellow]已取消。[/]")
        return 130
    except RuntimeError as exc:  # 配置类错误（如缺 API Key）
        console.print(Panel(f"[red]{exc}[/]", title="配置错误", border_style="red"))
        return 1


if __name__ == "__main__":
    sys.exit(main())
