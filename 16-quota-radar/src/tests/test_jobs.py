"""调度任务测试：端到端采集任务、异常兜底、调度器测试开关。"""

import respx

from radar.collectors import litellm, openrouter
from radar.db import connect, init_db, kv_get
from radar.scheduler.jobs import _guarded, job_collect, start_scheduler


def test_scheduler_disable_switch(monkeypatch):
    monkeypatch.setenv("QR_DISABLE_SCHEDULER", "1")
    s = start_scheduler()
    assert s.running is False  # noop 替身


def test_job_collect_end_to_end(tmp_path, monkeypatch):
    p = tmp_path / "j.db"
    init_db(p)
    monkeypatch.setattr("radar.scheduler.jobs._job_conn", lambda: connect(p))  # 每次新建，job 内部会 close
    with respx.mock(assert_all_called=False) as mock:
        mock.get(litellm.PRIMARY_URL).respond(json={
            "gpt-4o": {"mode": "chat", "litellm_provider": "openai",
                       "input_cost_per_token": 0.0000025, "output_cost_per_token": 0.00001,
                       "max_input_tokens": 128000}})
        mock.get(openrouter.MODELS_URL).respond(json={"data": []})
        _guarded("collect", job_collect)  # 走真实调度包装路径

    conn = connect(p)
    try:
        assert conn.execute("SELECT COUNT(*) c FROM models").fetchone()["c"] == 1
        assert kv_get(conn, "first_collect_done")          # 首轮静默已登记
        assert kv_get(conn, "last_job_collect").endswith("ok")
        assert kv_get(conn, "last_collect_at")
    finally:
        conn.close()


def test_guarded_swallows_exceptions(tmp_path, monkeypatch):
    p = tmp_path / "g.db"
    init_db(p)
    monkeypatch.setattr("radar.scheduler.jobs._job_conn", lambda: connect(p))

    def boom():
        raise RuntimeError("任务炸了")

    _guarded("testjob", boom)  # 不应向外抛
    conn = connect(p)
    try:
        assert "ERROR" in kv_get(conn, "last_job_testjob")
        assert "RuntimeError" in kv_get(conn, "last_job_testjob")
        state = conn.execute("SELECT status, consecutive_failures FROM job_state WHERE job_name='testjob'").fetchone()
        assert state["status"] == "error"
        assert state["consecutive_failures"] == 1
    finally:
        conn.close()
