"""API 与页面集成测试。"""

import pytest
from fastapi.testclient import TestClient

from radar.core.seeder import run_seeders
from radar.db import connect, init_db
from radar.web.app import app
from radar.web.deps import get_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("QR_DISABLE_SCHEDULER", "1")
    p = tmp_path / "api.db"
    init_db(p)

    def override():
        conn = connect(p)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override
    with TestClient(app):
        yield p
    app.dependency_overrides.clear()


def add_model(db_path, key, model_id, in_p, out_p, score, free=0, ctx=128000, source="litellm"):
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO models(key,provider,model_id,display_name,input_price,output_price,"
            "context_len,free,capability_score,scenario_flags,source,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,datetime('now'))",
            (key, key.split("/")[0], model_id, model_id, in_p, out_p, ctx, free, score,
             '{"code": false, "reasoning": false}', source))
        conn.commit()
    finally:
        conn.close()


def test_models_filters(client):
    p = client
    add_model(p, "a/paid", "paid", 1.0, 2.0, 90)
    add_model(p, "b/free", "freebie", 0.0, 0.0, 80, free=1)
    c = TestClient(app)  # fixture 已开过 context；直接新建走 overrides
    r = c.get("/api/v1/models?free=true")
    assert r.status_code == 200
    assert [m["model_id"] for m in r.json()["models"]] == ["freebie"]
    r = c.get("/api/v1/models?q=paid")
    assert r.json()["models"][0]["model_id"] == "paid"
    r = c.get("/api/v1/models?limit=1")
    assert len(r.json()["models"]) == 1


def test_recommend_endpoint(client):
    p = client
    add_model(p, "a/m1", "m1", 0.5, 2.0, 88)
    c = TestClient(app)
    r = c.get("/api/v1/recommend?scenario=chat&top=3")
    assert r.status_code == 200
    body = r.json()
    assert body["scenario"] == "chat"
    assert len(body["top"]) == 1
    assert body["top"][0]["value_index"] > 0      # A7：含性价比依据
    assert c.get("/api/v1/recommend?scenario=nope").status_code == 400


def test_usage_flow(client):
    c = TestClient(app)
    r = c.post("/api/v1/usage", json={"tokens": 1_000_000, "channel_id": "x", "note": "签到"})
    assert r.json()["balance"] == 1_000_000
    r = c.post("/api/v1/usage", json={"tokens": -400_000, "channel_id": "x"})
    assert r.json()["balance"] == 600_000
    r = c.post("/api/v1/usage", json={"tokens": 0})
    assert r.status_code == 422
    r = c.get("/api/v1/usage")
    body = r.json()
    assert body["overall"]["balance"] == 600_000
    assert body["overall"]["days_left"] is not None


def test_activities_mark_done(client):
    conn = connect(client)
    try:
        run_seeders(conn)
    finally:
        conn.close()
    c = TestClient(app)
    assert c.post("/api/v1/activities/zhipu-bigmodel/done").status_code == 200
    assert c.post("/api/v1/activities/nope/done").status_code == 404
    body = c.get("/api/v1/activities").json()
    done_ids = [a["id"] for a in body["activities"] if a["status"] == "done"]
    assert done_ids == ["zhipu-bigmodel"]


def test_pages_render(client):
    conn = connect(client)
    try:
        run_seeders(conn)
        add_model(client, "a/m1", "m1", 0.5, 2.0, 88)
    finally:
        conn.close()
    c = TestClient(app)
    for path, needle in [
        ("/", "看板"), ("/recommend", "场景化推荐"), ("/channels", "免费额度渠道"),
        ("/activities", "活动中心"), ("/changes", "变更日志"),
    ]:
        r = c.get(path)
        assert r.status_code == 200 and needle in r.text, path


def test_manual_collect_button(client, monkeypatch):
    called = []

    def fake_run(conn):
        called.append(1)

    monkeypatch.setattr("radar.collectors.runner.run_collection", fake_run)
    c = TestClient(app)
    r = c.post("/run/collect", follow_redirects=False)
    assert r.status_code == 303
    assert called  # 后台任务已执行（TestClient 同步执行 BackgroundTasks）


def test_activity_done_form_page_endpoint(client):
    """回归：页面表单标记完成曾因漏导入 mark_done 而 500。"""
    from radar.core.seeder import run_seeders
    from radar.db import connect
    conn = connect(client)
    try:
        run_seeders(conn)
    finally:
        conn.close()
    c = TestClient(app)
    r = c.post("/activities/zhipu-bigmodel/done", follow_redirects=False)
    assert r.status_code == 303
    body = c.get("/api/v1/activities").json()
    done = [a for a in body["activities"] if a["status"] == "done"]
    assert done and done[0]["id"] == "zhipu-bigmodel"


def test_deploy_page_agents_detected(client):
    """回归：部署中心 agent 检测栏目曾因读未写入的 kv 而空白。"""
    c = TestClient(app)
    r = c.get("/deploy")
    assert r.status_code == 200
    assert "OpenClaw" in r.text or "未检测到" in r.text


def test_manage_probe_rejects_bad_payload(client):
    c = TestClient(app)
    r = c.post("/api/v1/manage/probe", json={"channel_id": []})
    assert r.status_code == 422
