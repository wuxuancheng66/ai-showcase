"""领取框架测试：加密库、演示适配器、验证码转人工、活动监控。"""

import respx
from httpx import Response

from radar.claimer.base import BaseClaimer, CaptchaRequired, ClaimCheck, ClaimResult, DemoClaimer
from radar.claimer.monitor import check_activities, mark_done
from radar.claimer.runner import run_claims
from radar.claimer.vault import Vault
from radar.core.seeder import run_seeders
from radar.db import connect, init_db


class NoopSettings:
    notify_mode = "log"

    def api_key(self, name: str) -> str:
        return ""


def test_vault_roundtrip(tmp_path):
    v = Vault(tmp_path / "k", tmp_path / "d.enc")
    assert v.get("zhipu") is None
    v.set("zhipu", {"user": "abc", "pass": "***"})
    assert v.get("zhipu") == {"user": "abc", "pass": "***"}
    assert v.platforms() == ["zhipu"]
    # 落盘的是密文
    assert b"abc" not in (tmp_path / "d.enc").read_bytes()
    # 删除
    assert v.delete("zhipu") is True
    assert v.get("zhipu") is None


def test_vault_wrong_key_raises(tmp_path):
    v1 = Vault(tmp_path / "k1", tmp_path / "d1.enc")
    v1.set("x", {"a": 1})
    v2 = Vault(tmp_path / "k2", tmp_path / "d1.enc")  # 换密钥读同一密文
    try:
        v2.get("x")
        raised = False
    except Exception:
        raised = True
    assert raised


def test_demo_claimer_and_registry(tmp_path):
    p = tmp_path / "c.db"
    init_db(p)
    conn = connect(p)
    try:
        # 默认全部禁用 → 无结果、无事件
        results = run_claims(conn, NoopSettings())
        assert results == []
        assert conn.execute("SELECT COUNT(*) c FROM changes").fetchone()["c"] == 0

        # 启用 demo → 正常领取并记事件
        demo = DemoClaimer()
        demo.enabled = True
        results = run_claims(conn, NoopSettings(), registry=[demo])
        assert results[0]["status"] == "claimed"
        kinds = [r["kind"] for r in conn.execute("SELECT kind FROM changes").fetchall()]
        assert "activity" in kinds
    finally:
        conn.close()


def test_captcha_goes_to_human(tmp_path):
    p = tmp_path / "c.db"
    init_db(p)
    conn = connect(p)
    try:
        class EvilPlatform(BaseClaimer):
            platform = "evil"
            enabled = True
            requires_credentials = False

            def check(self):
                return ClaimCheck(claimable=True)

            def claim(self):
                raise CaptchaRequired("evil", "滑块验证码")

        results = run_claims(conn, NoopSettings(), registry=[EvilPlatform()])
        assert results[0]["status"] == "human_required"
        rows = conn.execute(
            "SELECT summary FROM changes WHERE kind='claim_blocked'").fetchall()
        assert any("绝不绕过" in r["summary"] for r in rows)
    finally:
        conn.close()


def test_activity_monitor_hash_change(tmp_path, monkeypatch):
    monkeypatch.setattr("radar.claimer.monitor.httpx.get",
                        lambda *a, **k: Response(200, text="页面内容V1"))
    p = tmp_path / "a.db"
    init_db(p)
    conn = connect(p)
    try:
        run_seeders(conn)
        # 首轮：只登记基线，不报警
        assert check_activities(conn) == []
        # 内容不变：无事件
        assert check_activities(conn) == []
        # 内容变化：报警（条数 = 有 URL 的待办活动数）
        monkeypatch.setattr("radar.claimer.monitor.httpx.get",
                            lambda *a, **k: Response(200, text="页面内容V2 新活动!"))
        changes = check_activities(conn)
        n_pending = conn.execute(
            "SELECT COUNT(*) c FROM activities WHERE status='pending' AND url IS NOT NULL"
        ).fetchone()["c"]
        assert len(changes) == n_pending >= 4
        assert all(c["kind"] == "activity" for c in changes)
        assert "可能有新活动可领" in changes[0]["summary"]
    finally:
        conn.close()


def test_mark_done(tmp_path):
    p = tmp_path / "a.db"
    init_db(p)
    conn = connect(p)
    try:
        run_seeders(conn)
        assert mark_done(conn, "zhipu-bigmodel") is True
        row = conn.execute("SELECT status FROM activities WHERE id='zhipu-bigmodel'").fetchone()
        assert row["status"] == "done"
        assert mark_done(conn, "not-exist") is False
    finally:
        conn.close()


def test_ledger_forecast(tmp_path):
    from radar.core.ledger import balance, forecast, record

    p = tmp_path / "l.db"
    init_db(p)
    conn = connect(p)
    try:
        record(conn, 1_000_000, channel_id="zhipu-flash", note="签到赠送")
        record(conn, -100_000, channel_id="zhipu-flash", model_key="glm-4.5-flash")
        record(conn, -100_000, channel_id="zhipu-flash", model_key="glm-4.5-flash")
        assert balance(conn, "zhipu-flash") == 800_000
        f = forecast(conn, "zhipu-flash", days=7)
        assert f["balance"] == 800_000
        assert f["daily_burn"] > 0
        assert f["days_left"] > 3  # 80万 / (20万/7天) = 28 天
        # 无消耗记录 → days_left=None
        assert forecast(conn, "other")["days_left"] is None
        import pytest
        with pytest.raises(ValueError):
            record(conn, 0)
    finally:
        conn.close()
