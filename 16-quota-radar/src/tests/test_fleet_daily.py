"""舰队清单 + AI 日报生成测试。"""

import json

import pytest

from radar.core import fleet
from radar.core.fleet import fleet_inventory
from radar.core.seeder import run_seeders
from radar.db import connect, init_db


class NoKeySettings:
    notify_mode = "log"

    def api_key(self, name: str) -> str:
        return ""


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "f.db"
    init_db(p)
    conn = connect(p)
    run_seeders(conn)
    yield conn
    conn.close()


def test_fleet_inventory_structure(db, monkeypatch):
    monkeypatch.setattr("radar.deploy.detect.detect_agents",
                        lambda: [{"id": "openclaw", "name": "OpenClaw（NVIDIA）", "detected": True,
                                  "gateway_url": "http://localhost:18790", "providers": ["nvidia"],
                                  "configured_channel_ids": ["nvidia-nim"], "capabilities": []}])
    inv = fleet_inventory(db, NoKeySettings())
    assert set(inv) == {"paid", "free", "updated_at"}
    all_entries = inv["paid"] + inv["free"]
    # 充值/免费互斥且全覆盖渠道种子
    assert any(e["id"] == "deepseek" for e in inv["paid"])       # cheap → 充值类
    assert any(e["id"] == "nvidia-nim" for e in inv["free"])     # free tier
    # OpenClaw agent 条目
    oc = next(e for e in inv["free"] if e["id"] == "openclaw")
    assert oc["kind"] == "agent" and oc["status"] == "ok"
    # 每个条目都有诊断与修复字段
    for e in all_entries:
        assert "diagnosis" in e and "repairs" in e
    # 未配 key 的需 key 渠道 → 有领取指引类诊断
    groq = next(e for e in inv["free"] if e["id"] == "groq")
    assert groq["diagnosis"] and "未配置 key" in groq["diagnosis"]
    # kv 已缓存
    assert db.execute("SELECT 1 FROM kv WHERE key='fleet'").fetchone()


def test_fleet_diagnosis_rules(db, monkeypatch):
    monkeypatch.setattr("radar.deploy.detect.detect_agents", lambda: [])
    inv = fleet_inventory(db, NoKeySettings())
    by_id = {e["id"]: e for e in inv["paid"] + inv["free"]}
    # deepseek（充值类、unknown 状态、无 key）→ 未配置 key 诊断
    assert "未配置 key" in (by_id["deepseek"]["diagnosis"] or "")


def test_daily_report_generation(tmp_path, db, monkeypatch):
    monkeypatch.setenv("QR_REPORT_DIR", str(tmp_path))
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    monkeypatch.setattr("radar.daily.report.OUTPUTS_DIR", outputs)
    fake_news = {
        "items": [
            {"title": "OpenAI 发布新模型", "url": "https://example.com/1",
             "grade": "🔵", "source": "TechCrunch", "summary": "摘要A",
             "date": None},
            {"title": "DeepSeek 降价", "url": "https://example.com/2",
             "grade": "🟡", "source": "量子位", "summary": "摘要B", "date": None},
        ],
        "sources": [{"name": "TechCrunch", "grade": "🔵", "ok": True, "count": 1},
                    {"name": "量子位", "grade": "🟡", "ok": True, "count": 1}],
    }
    monkeypatch.setattr("radar.daily.news.fetch_news", lambda **k: fake_news)
    from radar.daily.report import generate_daily
    result = generate_daily(db)
    assert result["items"] == 2
    out = tmp_path / f"AI日报_{__import__('time').strftime('%Y-%m-%d')}.html"
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    for section in ("今日头条", "行业动态", "数据与观点", "信源质量评估"):
        assert section in html
    assert "OpenAI 发布新模型" in html
    assert 'href="https://example.com/1"' in html   # 来源链接保留
    assert "charset" in html
    # 雷达数据板块有变更统计
    assert "本机雷达捕获模型、价格与渠道变化" in html


def test_daily_page_renders_without_any_report(tmp_path, monkeypatch):
    monkeypatch.setenv("QR_REPORT_DIR", str(tmp_path / "empty-reports"))
    from fastapi.testclient import TestClient
    from radar.web.app import app
    from radar.web.deps import get_db
    from radar.db import connect, init_db

    db_path = tmp_path / "daily-empty.db"
    init_db(db_path)

    def override_db():
        conn = connect(db_path)
        try:
            yield conn
        finally:
            conn.close()

    monkeypatch.setenv("QR_DISABLE_SCHEDULER", "1")
    monkeypatch.setattr("radar.web.app.connect", lambda: connect(db_path))
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.get("/daily")
        assert response.status_code == 200
        assert "暂无最新一期" in response.text
    finally:
        app.dependency_overrides.clear()
