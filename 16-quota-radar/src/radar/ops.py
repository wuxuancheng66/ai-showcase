"""运行状态、任务遥测与健康检查。"""

import json
import sqlite3
from datetime import datetime

from radar import __version__
from radar.backup import list_backups
from radar.config import DATA_DIR, get_settings
from radar.db import SCHEMA_VERSION, db_path, kv_get, now_iso


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def age_seconds(value: str | None) -> int | None:
    parsed = parse_iso(value)
    if not parsed:
        return None
    now = datetime.now(parsed.tzinfo) if parsed.tzinfo else datetime.now()
    return max(0, int((now - parsed).total_seconds()))


def record_job_started(conn: sqlite3.Connection, job_name: str) -> None:
    stamp = now_iso()
    conn.execute(
        "INSERT INTO job_state(job_name,status,last_started_at,run_count,updated_at) "
        "VALUES(?, 'running', ?, 1, ?) "
        "ON CONFLICT(job_name) DO UPDATE SET "
        "status='running', last_started_at=excluded.last_started_at, "
        "run_count=job_state.run_count+1, last_error=NULL, updated_at=excluded.updated_at",
        (job_name, stamp, stamp),
    )
    conn.commit()


def record_job_finished(conn: sqlite3.Connection, job_name: str, *,
                        duration_ms: int, error: str | None = None) -> None:
    stamp = now_iso()
    status = "error" if error else "ok"
    conn.execute(
        "INSERT INTO job_state(job_name,status,last_finished_at,duration_ms,last_error,"
        "consecutive_failures,updated_at) VALUES(?,?,?,?,?,?,?) "
        "ON CONFLICT(job_name) DO UPDATE SET status=excluded.status, "
        "last_finished_at=excluded.last_finished_at, duration_ms=excluded.duration_ms, "
        "last_error=excluded.last_error, "
        "consecutive_failures=CASE WHEN excluded.last_error IS NULL THEN 0 "
        "ELSE job_state.consecutive_failures+1 END, updated_at=excluded.updated_at",
        (job_name, status, stamp, duration_ms, error, 1 if error else 0, stamp),
    )
    conn.commit()


def record_job_skipped(conn: sqlite3.Connection, job_name: str, reason: str) -> None:
    stamp = now_iso()
    conn.execute(
        "INSERT INTO job_state(job_name,status,last_finished_at,last_error,updated_at) "
        "VALUES(?, 'skipped', ?, ?, ?) "
        "ON CONFLICT(job_name) DO UPDATE SET status='skipped', "
        "last_finished_at=excluded.last_finished_at, last_error=excluded.last_error, "
        "updated_at=excluded.updated_at",
        (job_name, stamp, reason, stamp),
    )
    conn.commit()


def _jobs(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT job_name,status,last_started_at,last_finished_at,duration_ms,last_error,"
        "run_count,consecutive_failures,updated_at FROM job_state ORDER BY job_name"
    ).fetchall()
    jobs = [dict(row) for row in rows]
    if jobs:
        return jobs

    # 兼容旧库/旧版本：没有 job_state 时保留 kv 的最后状态展示。
    return [
        {
            "job_name": row["key"].removeprefix("last_job_"),
            "status": "ok" if str(row["value"]).endswith(" ok") else "error",
            "last_finished_at": str(row["value"]).removesuffix(" ok").removesuffix(" ERROR"),
            "last_error": None,
        }
        for row in conn.execute(
            "SELECT key,value FROM kv WHERE key LIKE 'last_job_%' ORDER BY key"
        ).fetchall()
    ]


def _scheduler_snapshot(scheduler) -> dict:
    if scheduler is None:
        return {"running": False, "jobs": []}
    jobs = []
    try:
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "next_run_at": job.next_run_time.isoformat(timespec="seconds") if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
    except (AttributeError, RuntimeError):
        pass
    return {"running": bool(getattr(scheduler, "running", False)), "jobs": jobs}


def _db_size() -> int:
    try:
        return db_path().stat().st_size
    except OSError:
        return 0


def build_status(conn: sqlite3.Connection, scheduler=None) -> dict:
    """构造无敏感信息的运行状态，供健康检查和系统页共用。"""
    quick = conn.execute("PRAGMA quick_check(1)").fetchone()
    integrity = quick[0] if quick else "empty result"
    models = conn.execute("SELECT COUNT(*) c FROM models").fetchone()["c"]
    channels = conn.execute("SELECT COUNT(*) c FROM channels").fetchone()["c"]
    last_collect = kv_get(conn, "last_collect_at")
    collect_age = age_seconds(last_collect)
    settings = get_settings()
    max_age = max(settings.collect_interval_min * 2, 60) * 60
    collect_fresh = collect_age is not None and collect_age <= max_age

    source_rows = conn.execute(
        "SELECT key,value FROM kv WHERE key LIKE 'source_status_%' ORDER BY key"
    ).fetchall()
    sources = {
        row["key"].removeprefix("source_status_"): row["value"]
        for row in source_rows
    }
    try:
        last_summary = json.loads(kv_get(conn, "last_collect_summary") or "{}")
    except (TypeError, ValueError):
        last_summary = {}

    checks = {
        "database": {"status": "ok" if integrity == "ok" else "error", "detail": integrity},
        "models": {"status": "ok" if models else "empty", "count": models},
        "channels": {"status": "ok" if channels else "empty", "count": channels},
        "collection": {
            "status": "ok" if collect_fresh else ("pending" if collect_age is None else "stale"),
            "last_at": last_collect,
            "age_seconds": collect_age,
            "max_age_seconds": max_age,
        },
    }
    if integrity != "ok":
        overall = "error"
    elif any(item["status"] in {"empty", "stale", "pending"} for item in checks.values()):
        overall = "degraded"
    else:
        overall = "ok"

    started_at = kv_get(conn, "startup_at")
    return {
        "status": overall,
        "ready": integrity == "ok",
        "version": __version__,
        "schema_version": SCHEMA_VERSION,
        "started_at": started_at,
        "uptime_seconds": age_seconds(started_at),
        "database": {
            "integrity": integrity,
            "size_bytes": _db_size(),
            "filename": db_path().name,
        },
        "checks": checks,
        "sources": sources,
        "last_collect_summary": last_summary,
        "jobs": _jobs(conn),
        "scheduler": _scheduler_snapshot(scheduler),
        "backups": list_backups(limit=5),
    }
