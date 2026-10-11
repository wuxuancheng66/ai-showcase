"""运行状态、迁移、备份、系统页与安全管理测试。"""

import base64
import sqlite3

import pytest
from fastapi.testclient import TestClient

from radar.backup import create_backup
from radar.config import Settings, reset_settings
from radar.db import SCHEMA_VERSION, connect, init_db
from radar.web.app import app
from radar.web.deps import get_db


def test_schema_migration_is_versioned_and_idempotent(tmp_path):
    path = tmp_path / "schema.db"
    init_db(path)
    init_db(path)
    conn = connect(path)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert conn.execute("SELECT COUNT(*) c FROM schema_migrations").fetchone()["c"] == SCHEMA_VERSION
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 15000
    finally:
        conn.close()


def test_future_schema_version_is_rejected(tmp_path):
    path = tmp_path / "future.db"
    init_db(path)
    conn = connect(path)
    try:
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION + 1}")
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(RuntimeError, match="高于程序支持"):
        init_db(path)


def test_online_backup_is_consistent_and_restorable(tmp_path):
    source_path = tmp_path / "source.db"
    init_db(source_path)
    conn = connect(source_path)
    try:
        conn.execute(
            "INSERT INTO models(key,provider,model_id,input_price,output_price,free) "
            "VALUES('p/m','p','m',1,2,0)"
        )
        conn.commit()
        backup = create_backup(conn, destination_dir=tmp_path / "backups", note="test")
    finally:
        conn.close()

    assert backup["integrity"] == "ok"
    assert len(backup["sha256"]) == 64
    restored = sqlite3.connect(backup["path"])
    try:
        assert restored.execute("SELECT COUNT(*) FROM models").fetchone()[0] == 1
        assert restored.execute("PRAGMA quick_check(1)").fetchone()[0] == "ok"
    finally:
        restored.close()


def test_invalid_time_falls_back_safely(monkeypatch):
    monkeypatch.setenv("QR_DIGEST_TIME", "25:99")
    monkeypatch.setenv("QR_DAILY_TIME", "not-a-time")
    monkeypatch.setenv("QR_PORT", "70000")
    settings = Settings()
    assert settings.digest_time == "09:00"
    assert settings.daily_time == "07:30"
    assert settings.port == 65535


@pytest.fixture
def system_client(tmp_path, monkeypatch):
    path = tmp_path / "system.db"
    init_db(path)

    def override_db():
        conn = connect(path)
        try:
            yield conn
        finally:
            conn.close()

    monkeypatch.setenv("QR_DISABLE_SCHEDULER", "1")
    monkeypatch.setattr("radar.web.app.connect", lambda: connect(path))
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        reset_settings()


def test_system_page_and_api(system_client):
    page = system_client.get("/system")
    assert page.status_code == 200
    assert "系统状态" in page.text
    status = system_client.get("/api/v1/system/status")
    assert status.status_code == 200
    body = status.json()
    assert body["ready"] is True
    assert body["schema_version"] == SCHEMA_VERSION
    assert system_client.get("/health/live").status_code == 200
    assert system_client.get("/health/ready").status_code == 200


def test_optional_basic_auth_protects_management_but_not_health(system_client, monkeypatch):
    monkeypatch.setenv("QR_ADMIN_USER", "admin")
    monkeypatch.setenv("QR_ADMIN_PASSWORD", "test-password")
    reset_settings()
    try:
        assert system_client.get("/api/v1/meta").status_code == 401
        assert system_client.get("/system").status_code == 401
        assert system_client.get("/health/live").status_code == 200
        token = base64.b64encode(b"admin:test-password").decode()
        response = system_client.get("/api/v1/meta", headers={"Authorization": f"Basic {token}"})
        assert response.status_code == 200
    finally:
        reset_settings()


def test_cross_site_write_is_rejected(system_client):
    response = system_client.post(
        "/api/v1/daily/generate",
        headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "拒绝跨站状态变更请求"


def test_web_install_requires_explicit_server_opt_in(system_client):
    response = system_client.post("/api/v1/deploy/agent-task", json={
        "agent_id": "hermes",
        "channel_id": "nvidia-nim",
        "model_id": "z-ai/glm-5.1",
        "allow_install": True,
    })
    assert response.status_code == 403
    assert "QR_ALLOW_WEB_INSTALL" in response.json()["detail"]


def test_direct_deploy_rejects_non_openclaw_agent(system_client):
    response = system_client.post("/api/v1/deploy", json={
        "channel_id": "nvidia-nim",
        "model_id": "z-ai/glm-5.1",
        "agent": "hermes",
    })
    assert response.status_code == 422
    assert "仅支持 OpenClaw" in response.json()["detail"]


def test_api_rejects_control_characters_and_oversized_payload(system_client):
    invalid = system_client.post("/api/v1/usage", json={"tokens": 1, "note": "x" * 501})
    assert invalid.status_code == 422
    too_large = system_client.post(
        "/api/v1/usage",
        content=b"{}",
        headers={"Content-Type": "application/json", "Content-Length": "1048577"},
    )
    assert too_large.status_code == 413
