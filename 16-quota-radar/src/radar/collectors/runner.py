"""采集编排：跑全部数据源 → 评分 → 变更检测 → 落库。

单个数据源失败不影响其余源；状态翻转时记一条 source_status 变更事件。
"""

import json
import logging
import threading

from radar.collectors import litellm, openrouter
from radar.collectors.http import CollectorError
from radar.core import scoring
from radar.core.detector import detect_and_upsert
from radar.db import connect, init_db, kv_get, kv_set, now_iso

log = logging.getLogger("radar.runner")

SOURCES: list[tuple[str, callable]] = [
    ("litellm", litellm.collect),
    ("openrouter", openrouter.collect),
]

_collection_lock = threading.Lock()


def run_collection(conn=None) -> dict:
    if not _collection_lock.acquire(blocking=False):
        log.warning("已有采集任务运行，跳过重复调用")
        return {
            "skipped": True,
            "reason": "已有采集任务运行中",
            "changes": [],
            "results": {},
        }
    own = conn is None
    try:
        if own:
            init_db()
            conn = connect()
        now = now_iso()
        all_changes: list[dict] = []
        results: dict = {}

        for name, fetch in SOURCES:
            try:
                models = fetch()
            except CollectorError as exc:
                log.error("数据源 %s 失败: %s", name, exc)
                results[name] = {"status": "error", "detail": str(exc)}
                if kv_get(conn, f"source_status_{name}") != "error":
                    conn.execute(
                        "INSERT INTO changes(kind,target,summary,created_at) VALUES(?,?,?,?)",
                        ("source_error", name, f"数据源 {name} 暂时不可达，将在下轮重试", now),
                    )
                    conn.commit()
                kv_set(conn, f"source_status_{name}", "error")
                continue

            scoring.enrich(models)
            changes = detect_and_upsert(conn, models, now)
            results[name] = {"status": "ok", "models": len(models), "changes": len(changes)}
            all_changes.extend(changes)
            if kv_get(conn, f"source_status_{name}") == "error":
                conn.execute(
                    "INSERT INTO changes(kind,target,summary,created_at) VALUES(?,?,?,?)",
                    ("source_recovered", name, f"数据源 {name} 已恢复", now),
                )
                conn.commit()
            kv_set(conn, f"source_status_{name}", "ok")

        kv_set(conn, "last_collect_at", now)
        kv_set(conn, "last_collect_summary", json.dumps(results, ensure_ascii=False))
        log.info("采集完成: %s", results)
        return {"changes": all_changes, "results": results}
    finally:
        if own:
            if conn is not None:
                conn.close()
        _collection_lock.release()
