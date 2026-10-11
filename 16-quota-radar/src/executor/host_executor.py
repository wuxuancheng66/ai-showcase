#!/usr/bin/env python3
"""QuotaRadar 宿主执行器：消费 data/deploy_queue/ 里的部署计划，调用 openclaw CLI 执行。

纯标准库实现（宿主机无需装任何依赖）。设计要点：
- 每次部署前强制备份 openclaw.json；失败自动回滚并重启网关；
- dry-run 校验通过才真写；allowlist 做「现有 ∪ 新模型」并集（patch 数组是整体替换语义）；
- 验证用 `openclaw infer model run` 发真实一条消息，跑通才算 verified；
- 结果回写计划文件（status/result），雷达轮询展示并入册。

用法：python3 host_executor.py --once   # 单轮（launchd StartInterval 调度）
      python3 host_executor.py --watch  # 常驻轮询
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = ROOT / "data" / "deploy_queue"
LOG_FILE = QUEUE_DIR / "executor.log"
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
ALLOWED_APPS = {"OpenClaw", "AutoClaw", "DSH Desktop", "WorkBuddy", "启动 Agent Team", "LM Studio"}


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def redact_secrets(text: str) -> str:
    """子进程输出进入计划/日志前统一脱敏，避免 .env 值被回显。"""
    redacted = str(text or "")
    env_file = ROOT / ".env"
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    except OSError:
        lines = []
    for line in lines:
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        value = line.split("=", 1)[1].strip().strip('"').strip("'")
        if len(value) >= 6:
            redacted = redacted.replace(value, "[redacted]")
    redacted = re.sub(
        r"(?i)(api[_-]?key|access[_-]?token|token|password|authorization)"
        r"(\s*[=:]\s*)[^\s,;]+",
        r"\1\2[redacted]",
        redacted,
    )
    return redacted


def run(cmd: list[str], timeout: int = 120, input_text: str | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, input=input_text, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, redact_secrets((proc.stdout or "") + (proc.stderr or ""))
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except FileNotFoundError:
        return 127, f"command not found: {cmd[0]}"


def _read_env_value(var_name: str) -> str:
    """从雷达项目 .env 读取指定变量值（只在宿主机内存中流转，不打印）。"""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(f"{var_name}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def save_plan(plan: dict) -> None:
    path = QUEUE_DIR / f"{plan['id']}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


@contextmanager
def executor_lock():
    """同一时间仅允许一个执行器消费队列；重叠的 launchd/watch 调用直接跳过。"""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = QUEUE_DIR / ".executor.lock"
    handle = open(lock_path, "a+", encoding="utf-8")
    acquired = False
    try:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        acquired = True
    except (ImportError, BlockingIOError, OSError):
        acquired = False
    try:
        yield acquired
    finally:
        if acquired:
            try:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except (ImportError, OSError):
                pass
        handle.close()


def claim_plan(path: Path) -> dict | None:
    """仅把 queued 计划原子转换为 running；已完成/失败计划永不重复执行。"""
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if plan.get("status") != "queued":
        return None
    plan["status"] = "running"
    plan["lease_owner"] = f"pid:{os.getpid()}"
    plan["lease_started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_plan(plan)
    return plan


def openclaw_cli(plan: dict) -> str:
    cli = shutil.which("openclaw")
    if cli:
        return cli
    if plan.get("allow_install"):
        log("openclaw 未安装，按计划允许自动安装…")
        code, _out = run(["npm", "install", "-g", "openclaw@latest"], timeout=600)
        if code != 0:
            raise RuntimeError("OpenClaw 自动安装失败，请查看宿主执行器日志")
        cli = shutil.which("openclaw")
        if cli:
            return cli
    raise RuntimeError("openclaw CLI 不可用；请勾选『允许自动安装』或手动安装")


def hermes_cli(plan: dict) -> str:
    candidates = [
        shutil.which("hermes"),
        str(Path.home() / ".local" / "bin" / "hermes"),
        "/opt/homebrew/bin/hermes",
    ]
    cli = next((path for path in candidates if path and Path(path).exists()), None)
    if cli:
        return cli
    if plan.get("allow_install"):
        python = shutil.which("python3.11") or shutil.which("python3")
        if not python:
            raise RuntimeError("找不到 Python 3.11，无法自动安装 Hermes")
        log("Hermes 未安装，按计划允许自动安装…")
        code, _out = run(
            [python, "-m", "pip", "install", "--user", "--upgrade", "hermes-agent"],
            timeout=900,
        )
        if code != 0:
            raise RuntimeError("Hermes 自动安装失败，请查看宿主执行器日志")
        candidates = [
            shutil.which("hermes"),
            str(Path.home() / ".local" / "bin" / "hermes"),
            "/opt/homebrew/bin/hermes",
        ]
        cli = next((path for path in candidates if path and Path(path).exists()), None)
        if cli:
            return cli
    raise RuntimeError("Hermes 不可用；请勾选『允许自动安装』或手动安装")


def run_agent_deploy_task(plan: dict) -> dict:
    agent_id = plan.get("agent")
    prompt = str(plan.get("prompt") or "").strip()
    if not prompt:
        raise RuntimeError("接管任务缺少提示词")
    if agent_id == "openclaw":
        cli = openclaw_cli(plan)
        cmd = [cli, "agent", "--local", "--message", prompt, "--timeout", "900", "--json"]
    elif agent_id == "hermes":
        cli = hermes_cli(plan)
        cmd = [cli, "--safe-mode", "-z", prompt]
    else:
        raise RuntimeError(f"Agent {agent_id} 不支持接管任务")
    code, _out = run(cmd, timeout=960)
    if code != 0:
        raise RuntimeError(f"Agent 接管任务未完成（exit={code}），请查看 {agent_id} 会话")
    return {"status": "done", "verified": False,
            "detail": f"已交给 {agent_id} 执行；请查看该 Agent 会话中的操作结果"}


def merge_patch_for(plan: dict, cli: str) -> dict:
    """构造补丁：allowlist 取现有 ∪ 新模型；可选新增 provider（含 key）；可选设默认。"""
    provider = plan["provider"]
    model_id = plan["model_id"]
    cfg = json.loads(OPENCLAW_CONFIG.read_text(encoding="utf-8"))
    patch: dict = {}

    if plan.get("base_url"):
        provider_def = {
            "baseUrl": plan["base_url"],
            "api": "openai-completions",
            "models": [{
                "id": model_id, "name": model_id, "reasoning": False, "input": ["text"],
                "cost": {"input": 0, "output": 0},
                "contextWindow": plan.get("context_window", 131072),
                "maxTokens": 8192,
            }],
        }
        # 新 provider 需要 key：从雷达 .env 按变量名取值（值不落日志/对话）
        if plan.get("api_key_env"):
            key = _read_env_value(plan["api_key_env"])
            if not key:
                raise RuntimeError(
                    f"雷达 .env 中没有 {plan['api_key_env']} 的有效值，无法为新 provider 配凭证")
            provider_def["apiKey"] = key
        patch["models"] = {"providers": {provider: provider_def}}

    if plan.get("requires_allowlist", True):
        existing = (((cfg.get("agents") or {}).get("defaults") or {})
                    .get("modelPolicy") or {}).get("allow") or []
        # 白名单引用必须是 provider/model 全限定名（schema 校验要求）
        merged = sorted(set(existing) | {f"{provider}/{model_id}"})
        patch.setdefault("agents", {}).setdefault("defaults", {}).setdefault(
            "modelPolicy", {})["allow"] = merged

    if plan.get("set_default"):
        patch.setdefault("agents", {}).setdefault("defaults", {}).setdefault("model", {})
        patch["agents"]["defaults"]["model"]["primary"] = f"{provider}/{model_id}"
    return patch


def deploy(plan: dict) -> dict:
    steps: list[str] = []
    cli = openclaw_cli(plan)
    steps.append(f"CLI: {cli}")

    if not OPENCLAW_CONFIG.exists():
        raise RuntimeError(f"配置不存在: {OPENCLAW_CONFIG}")

    # 1) 备份（沿用 openclaw 的 .bak 习惯）
    backup = OPENCLAW_CONFIG.with_name(f"openclaw.json.bak-quotaradar-{plan['id']}")
    shutil.copy2(OPENCLAW_CONFIG, backup)
    steps.append(f"备份: {backup.name}")

    patch = merge_patch_for(plan, cli)
    if not patch:
        raise RuntimeError("空补丁，未生成可部署配置")

    # 2) dry-run 校验。补丁通过 stdin 传递，含凭证时绝不落盘。
    payload = json.dumps(patch, ensure_ascii=False)
    code, out = run([cli, "config", "patch", "--stdin", "--dry-run"], input_text=payload)
    steps.append(f"dry-run: {'通过' if code == 0 else '失败'}")
    if code != 0:
        raise RuntimeError(f"dry-run 校验失败（未做任何修改）: {out[-400:]}")

    # 3) 真写
    code, out = run([cli, "config", "patch", "--stdin"], input_text=payload)
    steps.append(f"写入: {'成功' if code == 0 else '失败'}")
    if code != 0:
        raise RuntimeError(f"配置写入失败: {out[-400:]}")

    # 4) 不重启网关：本机常态存在服务+应用两个网关实例，强重启易冲突（M14 实测）。
    #    验证用 `infer model run --local`——全新进程直接读最新配置，等价于验证新配置可用；
    #    常驻网关由应用自身热加载/下次重启时自然生效。
    steps.append("跳过网关重启（避免多实例冲突；配置由应用热加载生效）")

    # 5) 真实验证：--local 全新进程读最新配置，发一条真实消息
    #    大尺寸推理模型（550B 级）可能超过 2 分钟，验证超时给足 300 秒
    qualified = f"{plan['provider']}/{plan['model_id']}"
    code, out = run([cli, "infer", "model", "run", "--local", "--model", qualified,
                     "--prompt", "只回复两个字母: OK"], timeout=300)
    ok = code == 0 and "OK" in out
    steps.append(f"推理验证: {'✅ 跑通' if ok else '❌ 未跑通'} (exit={code})")
    if not ok:
        detail = out[-300:] or f"exit={code}"
        raise RuntimeError(f"推理验证未通过: {detail}")
    return {"status": "done", "verified": True, "detail": "已通过真实消息验证", "steps": steps}


def rollback(plan_id: str, backup: Path) -> None:
    if backup.exists():
        shutil.copy2(backup, OPENCLAW_CONFIG)
        log(f"{plan_id}: 已回滚配置（未重启网关，避免冲突）")


def process(plan_path: Path, plan: dict | None = None) -> None:
    if plan is None:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if plan.get("status") != "queued":
            return
        plan["status"] = "running"
        save_plan(plan)
    log(f"开始部署 {plan['id']}: {plan['provider']}/{plan['model_id']} → {plan['agent']}")
    backup = OPENCLAW_CONFIG.with_name(f"openclaw.json.bak-quotaradar-{plan['id']}")
    try:
        result = deploy(plan)
    except Exception as exc:  # noqa: BLE001 — 执行器必须自吞一切异常并回滚
        log(f"部署失败 {plan['id']}: {exc}")
        try:
            if backup.exists() and OPENCLAW_CONFIG.exists():
                rollback(plan["id"], backup)
                plan["status"] = "failed"
                plan["result"] = {"status": "failed", "verified": False,
                                  "rolled_back": True, "error": str(exc)}
                save_plan(plan)
                return
        except Exception as rb_exc:  # noqa: BLE001
            plan["status"] = "failed"
            plan["result"] = {"status": "failed", "verified": False,
                              "rolled_back": False, "error": f"{exc}; 回滚也失败: {rb_exc}"}
            save_plan(plan)
            return
        plan["status"] = "failed"
        plan["result"] = {"status": "failed", "verified": False, "error": str(exc)}
        save_plan(plan)
        return
    plan["status"] = "done"
    plan["result"] = result
    save_plan(plan)
    log(f"部署完成 {plan['id']}: verified={result['verified']}")


def once() -> int:
    with executor_lock() as acquired:
        if not acquired:
            return 0
        return _once_locked()


def _once_locked() -> int:
    if not QUEUE_DIR.exists():
        return 0
    for p in sorted(QUEUE_DIR.glob("dep_*.json")):
        plan = claim_plan(p)
        if not plan:
            continue
        if plan.get("action") == "agent_deploy_task":
            try:
                result = run_agent_deploy_task(plan)
                plan["status"] = "done"
                plan["result"] = result
            except Exception as exc:  # noqa: BLE001
                plan["status"] = "failed"
                plan["result"] = {"status": "failed", "verified": False, "error": str(exc)}
            save_plan(plan)
            log(f"Agent 接管任务完成: {plan['id']} status={plan['status']}")
            continue
        if plan.get("action") == "open_app":
            app_name = plan.get("app_name")
            if app_name not in ALLOWED_APPS:
                plan["status"] = "failed"
                plan["result"] = {"status": "failed", "error": "应用不在安全白名单"}
                save_plan(plan)
                continue
            code, out = run(["open", "-a", app_name], timeout=30)
            plan["status"] = "done" if code == 0 else "failed"
            plan["result"] = {
                "status": plan["status"], "app": app_name,
                "detail": f"已打开 {app_name}" if code == 0 else out[-200:],
            }
            save_plan(plan)
            log(f"打开应用动作完成: {plan['id']} app={app_name} exit={code}")
            continue
        if plan.get("action") == "restart_gateway":
            # 运维动作：重启 OpenClaw 网关（非模型部署）
            code, out = run(["openclaw", "daemon", "restart"], timeout=180)
            plan["status"] = "done" if code == 0 else "failed"
            plan["result"] = {"status": "done" if code == 0 else "failed",
                              "detail": out[-200:]}
            save_plan(plan)
            log(f"网关重启动作完成: {plan['id']} exit={code}")
            continue
        process(p, plan)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="单轮处理（launchd 定时调度用）")
    ap.add_argument("--watch", action="store_true", help="常驻轮询（15 秒一轮）")
    args = ap.parse_args()
    if args.watch:
        while True:
            once()
            time.sleep(15)
    once()
    return 0


if __name__ == "__main__":
    sys.exit(main())
