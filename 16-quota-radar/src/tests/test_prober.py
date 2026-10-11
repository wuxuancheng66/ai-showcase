"""渠道探活测试：状态分类、凭证缺失跳过、状态变化事件。全部 mock 网络。"""

import httpx
import respx

from radar.channels.prober import probe_all, probe_channel
from radar.core.seeder import run_seeders
from radar.db import connect, init_db


class FakeSettings:
    def __init__(self, keys: dict | None = None):
        self._keys = keys or {}

    def api_key(self, name: str) -> str:
        return self._keys.get(name, "")


def get_channel(conn, cid):
    return conn.execute("SELECT * FROM channels WHERE id=?", (cid,)).fetchone()


def test_probe_openai_ok_and_events(tmp_path):
    p = tmp_path / "p.db"
    init_db(p)
    conn = connect(p)
    run_seeders(conn)
    ch = get_channel(conn, "groq")
    assert ch["status"] == "unknown"

    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://api.groq.com/openai/v1/chat/completions").respond(
            json={"choices": []})
        status = probe_channel(conn, ch, api_key="test-key")
    assert status == "ok"
    row = get_channel(conn, "groq")
    assert row["status"] == "ok" and row["last_ok"]

    # 重复同状态不重复记事件
    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://api.groq.com/openai/v1/chat/completions").respond(json={})
        probe_channel(conn, row, api_key="test-key")
    events = conn.execute(
        "SELECT * FROM changes WHERE kind='channel_status' AND target='groq'").fetchall()
    assert len(events) == 1
    assert "unknown → ok" in events[0]["summary"]
    conn.close()


def test_probe_limited_and_error(tmp_path):
    p = tmp_path / "p.db"
    init_db(p)
    conn = connect(p)
    run_seeders(conn)

    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://api.groq.com/openai/v1/chat/completions").respond(status_code=429)
        assert probe_channel(conn, get_channel(conn, "groq"), "k") == "limited"

    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://api.groq.com/openai/v1/chat/completions").respond(status_code=401)
        assert probe_channel(conn, get_channel(conn, "groq"), "k") == "error"

    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://api.groq.com/openai/v1/chat/completions").mock(
            side_effect=httpx.ConnectError("boom"))
        assert probe_channel(conn, get_channel(conn, "groq"), "k") == "error"
    conn.close()


def test_probe_google_via_header(tmp_path):
    """Google 探活走 x-goog-api-key 头，key 不进 URL。"""
    p = tmp_path / "p.db"
    init_db(p)
    conn = connect(p)
    run_seeders(conn)
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get("https://generativelanguage.googleapis.com/v1beta/models").respond(
            json={"models": []})
        assert probe_channel(conn, get_channel(conn, "google-ai-studio"), "gk") == "ok"
    sent = route.calls.last.request
    assert sent.headers.get("x-goog-api-key") == "gk"
    assert b"key=gk" not in sent.url.query  # key 绝不出现在 URL
    conn.close()


def test_no_key_stays_unknown(tmp_path):
    p = tmp_path / "p.db"
    init_db(p)
    conn = connect(p)
    run_seeders(conn)
    assert probe_channel(conn, get_channel(conn, "groq"), "") is None
    assert get_channel(conn, "groq")["status"] == "unknown"
    # probe_type=none 的渠道也不探测
    assert probe_channel(conn, get_channel(conn, "ernie-speed"), "whatever") is None
    conn.close()


def test_probe_all_polite_and_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr("radar.channels.prober.time.sleep", lambda s: None)
    p = tmp_path / "p.db"
    init_db(p)
    conn = connect(p)
    run_seeders(conn)
    settings = FakeSettings({"GROQ_API_KEY": "k1", "OPENROUTER_API_KEY": "k2"})
    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://api.groq.com/openai/v1/chat/completions").respond(json={})
        route = mock.get("https://openrouter.ai/api/v1/models").respond(status_code=429)
        results = probe_all(conn, settings)
    assert results["groq"] == "ok"
    assert results["openrouter-free"] == "limited"
    assert route.calls.last.request.headers.get("Authorization") == "Bearer k2"
    assert "google-ai-studio" not in results          # 未配 key → 跳过
    assert "ernie-speed" not in results               # probe_type=none → 跳过
    conn.close()
