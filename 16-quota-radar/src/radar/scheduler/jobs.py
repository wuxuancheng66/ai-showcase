"""常驻任务调度。每个 job 独立容错：失败记日志与 kv，绝不拖垮整个进程。

环境变量 QR_DISABLE_SCHEDULER=1 时不启动真实调度（测试/CI 用）。
"""

import logging
import os
import re
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import BaseScheduler

from radar.config import DATA_DIR, get_settings
from radar.db import connect, init_db, kv_set, now_iso
from radar.ops import record_job_finished, record_job_skipped, record_job_started

log = logging.getLogger("radar.jobs")

_scheduler: BackgroundScheduler | None = None
_scheduler_lock_file = None


def _safe_error(exc: Exception) -> str:
    """记录足够定位的异常摘要，同时屏蔽常见凭据字段。"""
    message = str(exc).replace("\n", " ")[:500]
    message = re.sub(
        r"(?i)(api[_-]?key|access[_-]?token|token|password|authorization)\s*[=:]\s*\S+",
        r"\1=[redacted]",
        message,
    )
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__


def _guarded(name: str, fn, *args):
    """job 包装：异常只记日志，不让 APScheduler 线程死掉。"""
    started = time.monotonic()
    state_conn = None
    try:
        state_conn = _job_conn()
        record_job_started(state_conn, name)
        result = fn(*args)
        status = "skipped" if isinstance(result, dict) and result.get("skipped") else "ok"
        if status == "skipped":
            record_job_skipped(state_conn, name, str(result.get("reason") or "已有同类任务运行中"))
            kv_set(state_conn, f"last_job_{name}", now_iso() + " skipped")
        else:
            duration = int((time.monotonic() - started) * 1000)
            record_job_finished(state_conn, name, duration_ms=duration)
            kv_set(state_conn, f"last_job_{name}", now_iso() + " ok")
        return result
    except Exception as exc:  # noqa: BLE001 — 调度容错边界
        log.exception("任务 %s 失败: %s", name, exc)
        duration = int((time.monotonic() - started) * 1000)
        try:
            if state_conn is None:
                state_conn = _job_conn()
            detail = _safe_error(exc)
            record_job_finished(state_conn, name, duration_ms=duration, error=detail)
            kv_set(state_conn, f"last_job_{name}", now_iso() + f" ERROR {type(exc).__name__}")
        except Exception:
            log.exception("任务 %s 的失败状态未能写入", name)
            pass
        return None
    finally:
        if state_conn is not None:
            state_conn.close()


def _job_conn():
    from radar.db import connect as _c
    return _c()


def job_collect() -> dict:
    from radar.collectors.runner import run_collection
    from radar.notify.digest import handle_changes
    from radar.config import get_settings as gs

    conn = _job_conn()
    try:
        report = run_collection(conn)
        handle_changes(conn, report["changes"], gs())
        return report
    finally:
        conn.close()


def job_probe() -> None:
    from radar.channels.prober import probe_all
    conn = _job_conn()
    try:
        probe_all(conn, get_settings())
    finally:
        conn.close()


def job_digest() -> None:
    from radar.notify.digest import job_digest as _digest
    _digest()


def job_activities() -> None:
    from radar.claimer.monitor import check_activities
    conn = _job_conn()
    try:
        check_activities(conn)
    finally:
        conn.close()


def job_claims() -> None:
    from radar.claimer.runner import run_claims
    conn = _job_conn()
    try:
        run_claims(conn, get_settings())
    finally:
        conn.close()


def job_local_scan() -> None:
    from radar.local_scan import sync_local
    conn = _job_conn()
    try:
        sync_local(conn)
    finally:
        conn.close()


def job_daily_report() -> None:
    from radar.daily.report import generate_daily
    conn = _job_conn()
    try:
        generate_daily(conn)
    finally:
        conn.close()


def job_monitor_local() -> None:
    from radar.monitoring import refresh_local
    conn = _job_conn()
    try:
        refresh_local(conn, force=True)
    finally:
        conn.close()


def job_monitor_providers() -> None:
    from radar.monitoring import refresh_providers
    conn = _job_conn()
    try:
        refresh_providers(conn, force=True)
    finally:
        conn.close()


def job_backup() -> dict:
    """创建一致性 SQLite 备份。"""
    from radar.backup import create_backup
    return create_backup(note="scheduled")


def build_scheduler() -> BaseScheduler:
    settings = get_settings()
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        lambda: _guarded("collect", job_collect),
        "interval", minutes=max(settings.collect_interval_min, 15),
        id="collect", next_run_time=datetime.now(),  # 启动即首采
        misfire_grace_time=600, coalesce=True, max_instances=1,
    )
    scheduler.add_job(
        lambda: _guarded("probe", job_probe),
        "interval", minutes=max(settings.probe_interval_min, 30),
        id="probe", next_run_time=datetime.now(),
        misfire_grace_time=600, coalesce=True, max_instances=1,
    )
    hour, minute = settings.digest_parts
    scheduler.add_job(
        lambda: _guarded("digest", job_digest),
        "cron", hour=int(hour), minute=int(minute),
        id="digest", misfire_grace_time=3600, coalesce=True, max_instances=1,
    )
    scheduler.add_job(
        lambda: _guarded("activities", job_activities),
        "interval", minutes=max(settings.activity_interval_min, 30),
        id="activities", misfire_grace_time=600, coalesce=True, max_instances=1,
    )
    scheduler.add_job(
        lambda: _guarded("claims", job_claims),
        "interval", minutes=240,  # 领取类操作保守频率
        id="claims", misfire_grace_time=600, coalesce=True, max_instances=1,
    )
    scheduler.add_job(
        lambda: _guarded("local_scan", job_local_scan),
        "interval", minutes=360,  # 本机平台发现：6 小时一轮
        id="local_scan", next_run_time=datetime.now(),
        misfire_grace_time=600, coalesce=True, max_instances=1,
    )
    scheduler.add_job(
        lambda: _guarded("monitor_local", job_monitor_local),
        "interval", minutes=3,
        id="monitor_local", next_run_time=datetime.now(),
        misfire_grace_time=600, coalesce=True, max_instances=1,
    )
    scheduler.add_job(
        lambda: _guarded("monitor_providers", job_monitor_providers),
        "interval", minutes=30,
        id="monitor_providers", next_run_time=datetime.now(),
        misfire_grace_time=900, coalesce=True, max_instances=1,
    )
    d_hour, d_minute = settings.daily_parts
    scheduler.add_job(
        lambda: _guarded("daily_report", job_daily_report),
        "cron", hour=int(d_hour), minute=int(d_minute),
        id="daily_report", misfire_grace_time=3600, coalesce=True, max_instances=1,
    )
    backup_hour, backup_minute = settings.backup_parts
    scheduler.add_job(
        lambda: _guarded("backup", job_backup),
        "cron", hour=backup_hour, minute=backup_minute,
        id="backup", misfire_grace_time=3600, coalesce=True, max_instances=1,
    )
    return scheduler


def _acquire_scheduler_lock() -> bool:
    """只允许一个进程启动调度器，避免多 worker 重复采集和重复通知。"""
    global _scheduler_lock_file
    try:
        import fcntl
    except ImportError:  # pragma: no cover - Windows fallback
        return True
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    handle = open(DATA_DIR / "scheduler.lock", "a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return False
    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    _scheduler_lock_file = handle
    return True


def _release_scheduler_lock() -> None:
    global _scheduler_lock_file
    if _scheduler_lock_file is None:
        return
    try:
        import fcntl
        fcntl.flock(_scheduler_lock_file.fileno(), fcntl.LOCK_UN)
    except (ImportError, OSError):
        pass
    _scheduler_lock_file.close()
    _scheduler_lock_file = None


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if os.environ.get("QR_DISABLE_SCHEDULER") == "1":
        log.info("调度器被 QR_DISABLE_SCHEDULER 禁用（测试模式）")
        return _noop_scheduler
    if _scheduler is None or not _scheduler.running:
        if not _acquire_scheduler_lock():
            log.info("另一个进程已持有调度器锁，本进程不启动重复调度")
            return _noop_scheduler
        _scheduler = build_scheduler()
        try:
            _scheduler.start()
        except Exception:
            _release_scheduler_lock()
            _scheduler = None
            raise
        log.info("调度器已启动: collect/%dmin probe/%dmin digest@%s",
                 get_settings().collect_interval_min,
                 get_settings().probe_interval_min, get_settings().digest_time)
    return _scheduler


def stop_scheduler(wait: bool = True) -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=wait)
        log.info("调度器已停止")
    _scheduler = None
    _release_scheduler_lock()


class _NoopScheduler:
    """测试替身：保持 app.state.scheduler 接口可用。"""

    running = False

    def shutdown(self, wait: bool = True) -> None:
        pass

    def get_jobs(self) -> list:
        return []


_noop_scheduler = _NoopScheduler()
