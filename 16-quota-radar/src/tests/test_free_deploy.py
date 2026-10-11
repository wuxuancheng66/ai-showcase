"""M11-M13 测试：免费渠道排行 + 部署规划器 + 部署 API。"""

import json

import pytest
from fastapi.testclient import TestClient

from radar.core.free_rank import WEIGHTS, compute_free_rank, detect_agent_channels
from radar.core.seeder import run_seeders
from radar.db import connect, init_db
from radar.deploy import planner
from radar.web.app import app
from radar.web.deps import get_db


class NoKeySettings:
    notify_mode = "log"

    def api_key(self, name: str) -> str:
        return ""


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_free_rank_orders_and_breakdown(tmp_path):
    p = tmp_path / "f.db"
    init_db(p)
    conn = connect(p)
    try:
        run_seeders(conn)
        ranked = compute_free_rank(conn, NoKeySettings())
        assert len(ranked) >= 10  # 免费渠道都在
        scores = [r["score"] for r in ranked]
        assert scores == sorted(scores, reverse=True)
        for r in ranked:
            assert 1 <= r["score"] <= 100
            assert set(r["breakdown"]) == {"capability", "access", "limits", "stability", "onboarding"}
            assert isinstance(r["reasons"], list)
        # nvidia 有 configured_in_agent 种子 → 上手分应高于未配置渠道
        nvidia = next(r for r in ranked if r["id"] == "nvidia-nim")
        assert nvidia["configured_in_agent"] is True
        assert nvidia["breakdown"]["onboarding"] >= 75
        assert "已部署进本机 agent" in "；".join(nvidia["reasons"])
        # 非免费渠道不进榜（deepseek tier=cheap）
        assert all(r["id"] != "deepseek" for r in ranked)
        # 结果写 kv 供仪表盘
        assert conn.execute("SELECT 1 FROM kv WHERE key='free_rank'").fetchone()
    finally:
        conn.close()


def test_detect_agent_channels_with_fake_config(tmp_path, monkeypatch):
    fake = tmp_path / "openclaw.json"
    fake.write_text(json.dumps({"models": {"providers": {"nvidia": {"baseUrl": "https://x/v1"},
                                                          "other": {}}}}), encoding="utf-8")
    monkeypatch.setattr("radar.core.free_rank._OPENCLAW_CONFIGS", [str(fake)])
    found = detect_agent_channels()
    assert found == {"nvidia-nim": ["nvidia"]}


def test_detect_agent_channels_missing_config():
    monkey_tmp = "/nonexistent/openclaw.json"
    import radar.core.free_rank as fr
    saved = fr._OPENCLAW_CONFIGS
    fr._OPENCLAW_CONFIGS = [monkey_tmp]
    try:
        assert detect_agent_channels() == {}
    finally:
        fr._OPENCLAW_CONFIGS = saved


def test_planner_build_patch_reuse_provider():
    patch = planner.build_patch("nvidia", "z-ai/glm-5.1", set_default=True,
                                requires_allowlist=True)
    # 复用已有 provider：不含 models 段（不改 provider 本体）
    assert "models" not in patch
    assert patch["agents"]["defaults"]["modelPolicy"]["allow"] == ["z-ai/glm-5.1"]
    assert patch["agents"]["defaults"]["model"]["primary"] == "nvidia/z-ai/glm-5.1"


def test_deployment_target_requires_compatible_provider_and_key():
    from radar.deploy.planner import deployment_target
    google = {"id": "google-ai-studio", "provider": "google", "probe": {"type": "google_list"}}
    assert deployment_target(google, {"providers": []}, True)["ready"] is False

    groq = {"id": "groq", "provider": "groq", "env_key": "GROQ_API_KEY",
            "probe": {"type": "openai_compatible", "base_url": "https://api.groq.com/openai/v1"}}
    assert deployment_target(groq, {"providers": []}, False)["ready"] is False
    assert deployment_target(groq, {"providers": []}, True)["ready"] is True
    assert deployment_target(groq, {"providers": ["groq"]}, False)["base_url"] is None


def test_planner_build_patch_new_provider():
    patch = planner.build_patch("siliconflow", "Qwen/Qwen2.5-7B-Instruct", set_default=False,
                                base_url="https://api.siliconflow.cn/v1")
    prov = patch["models"]["providers"]["siliconflow"]
    assert prov["baseUrl"] == "https://api.siliconflow.cn/v1"
    assert prov["models"][0]["cost"] == {"input": 0, "output": 0}
    assert "model" not in patch.get("agents", {}).get("defaults", {})


def test_planner_enqueue_and_read(tmp_path, monkeypatch):
    monkeypatch.setattr("radar.deploy.planner.QUEUE_DIR", tmp_path)
    plan = planner.enqueue("openclaw", "nvidia-nim", "nvidia", "z-ai/glm-5.1",
                           set_default=True, requires_allowlist=True)
    assert plan["status"] == "queued"
    read = planner.read_plan(plan["id"])
    assert read["model_id"] == "z-ai/glm-5.1"
    assert planner.read_result(plan["id"]) is None


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("QR_DISABLE_SCHEDULER", "1")
    p = tmp_path / "dep.db"
    init_db(p)
    conn = connect(p)
    run_seeders(conn)
    conn.close()

    def override():
        c = connect(p)
        try:
            yield c
        finally:
            c.close()

    app.dependency_overrides[get_db] = override
    queue_dir = tmp_path / "queue"
    monkeypatch.setattr("radar.deploy.planner.QUEUE_DIR", queue_dir)
    monkeypatch.setattr("radar.deploy.detect.detect_agents", lambda: [{
        "id": "openclaw", "name": "OpenClaw", "detected": True,
        "gateway_url": "http://localhost:18790", "providers": ["nvidia"],
        "configured_channel_ids": ["nvidia-nim"], "capabilities": [],
    }])
    with TestClient(app):
        yield p
    app.dependency_overrides.clear()


def test_deploy_enqueue_and_status_flow(client):
    c = TestClient(app)
    r = c.post("/api/v1/deploy", json={"channel_id": "nvidia-nim",
                                       "model_id": "z-ai/glm-5.1", "set_default": True})
    assert r.status_code == 200
    plan_id = r.json()["plan_id"]
    plan_file = client  # 队列目录被 monkeypatch 到 tmp；直接读文件验证
    import radar.deploy.planner as pl
    plan = pl.read_plan(plan_id)
    assert plan["status"] == "queued"
    assert plan["provider"] == "nvidia" and plan["base_url"] is None  # 已配置 provider 复用

    # 模拟执行器完成并验证通过 → 状态接口应入册
    plan["status"] = "done"
    plan["result"] = {"status": "done", "verified": True, "detail": "已通过真实消息验证"}
    (pl.QUEUE_DIR / f"{plan_id}.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    r2 = c.get(f"/api/v1/deploy/status/{plan_id}")
    assert r2.json()["status"] == "done"
    rows = c.get("/api/v1/deploy/configured").json()["configured"]
    assert rows and rows[0]["model_id"] == "z-ai/glm-5.1" and rows[0]["verified"] == 1
    # 幂等：不重复入册
    c.get(f"/api/v1/deploy/status/{plan_id}")
    rows2 = c.get("/api/v1/deploy/configured").json()["configured"]
    assert len(rows2) == 1


def test_deploy_enqueue_validation(client):
    c = TestClient(app)
    assert c.post("/api/v1/deploy", json={"channel_id": ""}).status_code == 422
    assert c.post("/api/v1/deploy", json={"channel_id": "nope", "model_id": "x"}).status_code == 404
    assert c.post("/api/v1/deploy", json={"channel_id": "google-ai-studio",
                                          "model_id": "gemini-2.5-pro"}).status_code == 422
    assert c.get("/api/v1/deploy/status/nope").status_code == 404


def test_agent_catalog_api_and_open_command(client, monkeypatch):
    monkeypatch.setattr(
        "radar.agent_catalog._local_scan",
        lambda conn=None: {"OpenClaw": {}, "Codex CLI": {}},
    )
    c = TestClient(app)
    catalog = c.get("/api/v1/deploy/agents")
    assert catalog.status_code == 200
    assert len(catalog.json()["agents"]) >= 10
    opened = c.post("/api/v1/agents/codex/open")
    assert opened.status_code == 200
    assert opened.json()["mode"] == "command"
    assert opened.json()["command"] == "codex"
    gateway = c.post("/api/v1/agents/openclaw/open")
    assert gateway.status_code == 200
    assert gateway.json()["mode"] == "url"


def test_agent_task_route_creates_safe_plan(client, monkeypatch):
    monkeypatch.setattr(
        "radar.agent_catalog._local_scan",
        lambda conn=None: {"OpenClaw": {}, "Hermes Agent（终端版）": {}},
    )
    c = TestClient(app)
    response = c.post("/api/v1/deploy/agent-task", json={
        "agent_id": "hermes",
        "channel_id": "nvidia-nim",
        "model_id": "z-ai/glm-5.1",
        "allow_install": False,
    })
    assert response.status_code == 200
    plan = planner.read_plan(response.json()["plan_id"])
    assert plan["action"] == "agent_deploy_task"
    assert plan["agent"] == "hermes"
    assert "验证码" in plan["prompt"]
    assert "不要索取" in plan["prompt"]
