"""编排器测试：双源端到端（mock 网络）+ 单源故障隔离 + 种子同步幂等。"""

import json

import respx
from httpx import Response

from radar.collectors import litellm, openrouter
from radar.collectors import runner
from radar.collectors.runner import run_collection
from radar.core.seeder import run_seeders
from radar.db import connect, init_db, kv_get


def test_full_collection(tmp_path):
    p = tmp_path / "r.db"
    init_db(p)
    with respx.mock(assert_all_called=False) as mock:
        mock.get(litellm.PRIMARY_URL).respond(json={
            "deepseek-chat": {"mode": "chat", "litellm_provider": "deepseek",
                              "input_cost_per_token": 0.00000027, "output_cost_per_token": 0.0000011,
                              "max_input_tokens": 64000},
        })
        mock.get(openrouter.MODELS_URL).respond(json={
            "data": [{"id": "deepseek/deepseek-chat:free", "name": "DeepSeek Chat (free)",
                      "context_length": 64000, "pricing": {"prompt": "0", "completion": "0"}}],
        })
        conn = connect(p)
        try:
            report = run_collection(conn)
            assert report["results"]["litellm"]["status"] == "ok"
            assert report["results"]["openrouter"]["status"] == "ok"
            assert len(report["changes"]) == 2  # 两个新模型
            assert conn.execute("SELECT COUNT(*) c FROM models").fetchone()["c"] == 2
            assert kv_get(conn, "last_collect_at") is not None
            # 评分已填充
            row = conn.execute(
                "SELECT capability_score FROM models WHERE key='deepseek/deepseek-chat'"
            ).fetchone()
            assert row["capability_score"] == 85.0
            # 幂等：再跑一轮无新变更
            report2 = run_collection(conn)
            assert report2["changes"] == []
        finally:
            conn.close()


def test_source_failure_isolation_and_recovery(tmp_path, monkeypatch):
    monkeypatch.setattr("radar.collectors.http.time.sleep", lambda s: None)
    p = tmp_path / "r.db"
    init_db(p)
    with respx.mock(assert_all_called=False) as mock:
        # 第一轮：litellm 双源全挂（PRIMARY 3 次 + FALLBACK 3 次）；第二轮 PRIMARY 直接成功
        mock.get(litellm.PRIMARY_URL).mock(side_effect=[
            Response(500), Response(500), Response(500),
            Response(200, json={"m1": {"mode": "chat", "litellm_provider": "openai",
                                       "input_cost_per_token": 0.0, "output_cost_per_token": 0.0}}),
        ])
        mock.get(litellm.FALLBACK_URL).mock(side_effect=[
            Response(500), Response(500), Response(500),
        ])
        mock.get(openrouter.MODELS_URL).respond(json={"data": [
            {"id": "x/y:free", "name": "Y free", "context_length": 8000,
             "pricing": {"prompt": "0", "completion": "0"}}]})

        conn = connect(p)
        try:
            report = run_collection(conn)
            assert report["results"]["litellm"]["status"] == "error"
            assert report["results"]["openrouter"]["status"] == "ok"
            kinds = [r["kind"] for r in conn.execute("SELECT kind FROM changes").fetchall()]
            assert "source_error" in kinds
            assert "new_free_model" in kinds

            # 第二轮：litellm 恢复 → 记录恢复事件，不再重复报故障
            report2 = run_collection(conn)
            assert report2["results"]["litellm"]["status"] == "ok"
            kinds2 = [r["kind"] for r in conn.execute("SELECT kind FROM changes").fetchall()]
            assert "source_recovered" in kinds2
            assert kinds2.count("source_error") == 1
            summary = json.loads(kv_get(conn, "last_collect_summary"))
            assert summary["litellm"]["status"] == "ok"
        finally:
            conn.close()


def test_seeders_idempotent(tmp_path):
    p = tmp_path / "s.db"
    init_db(p)
    conn = connect(p)
    try:
        run_seeders(conn)
        n1 = conn.execute("SELECT COUNT(*) c FROM channels").fetchone()["c"]
        a1 = conn.execute("SELECT COUNT(*) c FROM activities").fetchone()["c"]
        assert n1 >= 10 and a1 >= 3
        # 改库内运行时状态后重新同步，状态保留、配置字段更新
        conn.execute("UPDATE channels SET status='ok', name='旧名' WHERE id='groq'")
        conn.commit()
        run_seeders(conn)
        row = conn.execute("SELECT status, name FROM channels WHERE id='groq'").fetchone()
        assert row["status"] == "ok"       # 运行时状态不被覆盖
        assert row["name"] != "旧名"        # 配置字段以 yaml 为准
        n2 = conn.execute("SELECT COUNT(*) c FROM channels").fetchone()["c"]
        assert n1 == n2
    finally:
        conn.close()


def test_collection_rejects_overlapping_run(tmp_path):
    p = tmp_path / "locked.db"
    init_db(p)
    conn = connect(p)
    assert runner._collection_lock.acquire(blocking=False)
    try:
        result = run_collection(conn)
    finally:
        runner._collection_lock.release()
        conn.close()
    assert result["skipped"] is True
    assert result["reason"] == "已有采集任务运行中"
