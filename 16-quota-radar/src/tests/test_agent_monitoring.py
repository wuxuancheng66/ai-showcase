"""Agent 目录与自动监测回归测试。"""

import sqlite3

from radar.agent_catalog import list_agents, match_channel
from radar.db import connect, init_db
from radar.monitoring import latest_metrics, refresh_local, summary


def test_agent_catalog_covers_local_agent_entries(monkeypatch):
    monkeypatch.setattr(
        "radar.agent_catalog._local_scan",
        lambda conn=None: {
            "OpenClaw（NVIDIA agent）": {},
            "Codex CLI": {},
            "Claude Code": {},
            "Hermes Agent（终端版）": {},
            "AutoClaw（GLM 生态 agent）": {},
        },
    )
    agents = list_agents()
    by_id = {a["id"]: a for a in agents}
    assert len(agents) >= 10
    assert by_id["openclaw"]["detected"] is True
    assert by_id["codex"]["detected"] is True
    assert by_id["openclaw"]["computer_control"] is True
    assert by_id["openclaw"]["plugin_capable"] is True


def test_channel_match_prefers_detected_openclaw(monkeypatch):
    monkeypatch.setattr(
        "radar.agent_catalog._local_scan",
        lambda conn=None: {"OpenClaw": {}, "Hermes Agent（终端版）": {}},
    )
    agents = list_agents()
    match = match_channel({"deploy_ready": True, "deploy_reason": ""}, agents)
    assert match["automatic"] is True
    assert match["agent"]["id"] == "openclaw"


def test_codex_monitor_reads_token_usage(tmp_path, monkeypatch):
    logs = tmp_path / "logs_2.sqlite"
    conn = sqlite3.connect(logs)
    conn.execute(
        "CREATE TABLE logs (id INTEGER PRIMARY KEY, ts INTEGER, feedback_log_body TEXT)"
    )
    body = (
        "post sampling token usage turn_id=turn-1 total_usage_tokens=12345 "
        "auto_compact_scope_limit=Some(50000)"
    )
    conn.execute("INSERT INTO logs(ts,feedback_log_body) VALUES(?,?)", (9999999999999, body))
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        "radar.monitoring._first_existing",
        lambda *parts: logs if "logs_2.sqlite" in parts else None,
    )
    monkeypatch.setattr("radar.agent_catalog._local_scan", lambda conn=None: {"OpenClaw": {}})

    db = connect(tmp_path / "monitor.db")
    init_db(tmp_path / "monitor.db")
    try:
        assert refresh_local(db, force=True) is True
        metric = latest_metrics(db)["codex"]
        assert metric["used_tokens"] == 12345
        assert metric["limit_tokens"] == 50000
        report = summary(db)
        assert report["token_used_7d"] >= 12345
        assert report["monitored"] >= 1
    finally:
        db.close()
