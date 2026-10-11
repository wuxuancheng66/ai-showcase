"""M0/M3 冒烟测试：应用生命周期、健康检查、数据库初始化、调度器。"""

import pytest
from fastapi.testclient import TestClient

from radar.db import connect, init_db, kv_get, kv_set


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("QR_DISABLE_SCHEDULER", "1")
    init_db(tmp_path / "t.db")
    monkeypatch.setattr("radar.web.app.connect", lambda: connect(tmp_path / "t.db"))
    from radar.web.app import app

    with TestClient(app) as c:  # with 语句触发 lifespan（种子同步+调度器开关）
        yield c


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body and "last_jobs" in body


def test_db_schema_and_kv(tmp_path):
    p = tmp_path / "k.db"
    init_db(p)
    conn = connect(p)
    try:
        # 表都存在且为空
        for table in ("models", "price_history", "changes", "channels", "activities", "usage_log", "kv"):
            assert conn.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"] == 0
        kv_set(conn, "foo", "bar")
        assert kv_get(conn, "foo") == "bar"
    finally:
        conn.close()


def test_wal_mode(tmp_path):
    p = tmp_path / "w.db"
    init_db(p)
    conn = connect(p)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_connection_can_close_from_worker_thread(tmp_path):
    """回归：FastAPI 依赖清理线程可能与创建连接线程不同。"""
    from concurrent.futures import ThreadPoolExecutor

    p = tmp_path / "thread.db"
    conn = connect(p)
    conn.execute("SELECT 1").fetchone()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(conn.close).result()
