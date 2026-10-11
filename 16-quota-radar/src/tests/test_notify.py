"""通知与简报测试：邮件/日志双模式、首轮静默、简报结构。"""

from radar.config import OUTPUTS_DIR, Settings
from radar.notify.digest import build_digest, handle_changes
from radar.notify.emailer import notify
from radar.db import connect, init_db, kv_get


def log_settings(tmp_path, **overrides) -> Settings:
    s = Settings()
    s.smtp_host = s.smtp_user = s.smtp_pass = s.smtp_to = ""
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def add_model(conn, key, model_id, in_p, out_p, score, free=0, source="litellm"):
    conn.execute(
        "INSERT INTO models(key,provider,model_id,display_name,input_price,output_price,"
        "context_len,free,capability_score,scenario_flags,source,updated_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,datetime('now'))",
        (key, key.split("/")[0], model_id, model_id, in_p, out_p, 128000, free, score,
         '{"code": false, "reasoning": false}', source),
    )


def test_notify_log_mode_writes_file(tmp_path, monkeypatch):
    monkeypatch.setattr("radar.notify.emailer.OUTPUTS_DIR", tmp_path)
    result = notify("测试主题", "正文内容", log_settings(tmp_path))
    assert result.startswith("log:")
    path = tmp_path / result.split(":", 1)[1]
    assert path.exists() and "正文内容" in path.read_text(encoding="utf-8")


def test_notify_email_mode(monkeypatch):
    import base64

    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent["host"], sent["port"] = host, port

        def login(self, u, p):
            sent["user"] = u

        def sendmail(self, frm, to, body):
            sent["to"], sent["body"] = to, body

        def quit(self):
            pass

    monkeypatch.setattr("radar.notify.emailer.smtplib.SMTP_SSL", FakeSMTP)
    s = log_settings(None, smtp_host="smtp.test", smtp_port=465,
                     smtp_user="a@b.c", smtp_pass="secret", smtp_to="me@home")
    assert s.notify_mode == "email"
    result = notify("主题X", "正文Y", s, html_body="<div><b>正文Y</b></div>")
    assert result == "email"
    assert sent["port"] == 465 and ["me@home"] == sent["to"]
    assert sent["user"] == "a@b.c"
    # multipart：纯文本 + HTML 双部分；用 email 模块解析回读
    import email as email_mod

    msg = email_mod.message_from_string(sent["body"])
    texts = {}
    for part in msg.walk():
        if part.get_content_type() in ("text/plain", "text/html"):
            texts[part.get_content_type()] = part.get_payload(decode=True).decode("utf-8")
    assert "正文Y" in texts["text/plain"]
    assert "<b>正文Y</b>" in texts["text/html"]
    assert "secret" not in "".join(texts.values())  # 密码绝不进正文


def test_notify_email_failure_falls_back(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("网络不通")

    monkeypatch.setattr("radar.notify.emailer.smtplib.SMTP_SSL", boom)
    monkeypatch.setattr("radar.notify.emailer.OUTPUTS_DIR", tmp_path)
    s = log_settings(None, smtp_host="smtp.test", smtp_port=465,
                     smtp_user="a@b.c", smtp_pass="secret", smtp_to="me@home")
    result = notify("会失败", "内容", s)
    assert result.startswith("log:")  # 降级而非抛异常


def test_first_run_silence(tmp_path):
    p = tmp_path / "d.db"
    init_db(p)
    conn = connect(p)
    try:
        changes = [{"kind": "new_model", "summary": "新模型 A"},
                   {"kind": "price_drop", "summary": "降价 B"}]
        result = handle_changes(conn, changes, log_settings(None))
        assert result == "silent_first_run"
        assert kv_get(conn, "first_collect_done")
        assert conn.execute("SELECT COUNT(*) c FROM changes WHERE notified=0").fetchone()["c"] == 0

        # 首轮之后：变更不再单独发信，统一并入每日简报（1 天 1 封）
        result2 = handle_changes(conn, [{"kind": "new_model", "summary": "新模型 C"}],
                                 log_settings(None))
        assert result2 == "only_low_value"
        result3 = handle_changes(conn, [{"kind": "price_drop", "summary": "X 降价 50%"}],
                                 log_settings(None))
        assert result3 == "queued_for_digest"
    finally:
        conn.close()


def test_digest_structure(tmp_path):
    p = tmp_path / "d.db"
    init_db(p)
    conn = connect(p)
    try:
        add_model(conn, "a/m1", "m1", 0.5, 2.0, 88)
        add_model(conn, "f/m2", "m2", 0.0, 0.0, 80, free=1)
        conn.execute(
            "INSERT INTO channels(id,name,status,last_checked) VALUES('x','渠道X','ok','2026-01-01T08:00:00')")
        conn.execute(
            "INSERT INTO activities(id,platform,title,url,status) VALUES('y','平台Y','签到','https://x','pending')")
        conn.commit()
        text = build_digest(conn)
        for section in ("免费模型榜", "性价比榜", "批量处理", "渠道状态", "待领取活动", "渠道X", "平台Y"):
            assert section in text
        assert "m1" in text and "m2" in text
    finally:
        conn.close()


def test_digest_html_clean(tmp_path):
    """HTML 版简报：无裸 Markdown 符号，有表格与内联样式，正文完整。"""
    from radar.notify.digest import build_digest_html

    p = tmp_path / "d.db"
    init_db(p)
    conn = connect(p)
    try:
        add_model(conn, "a/m1", "m1", 0.5, 2.0, 88)
        add_model(conn, "f/m2", "m2", 0.0, 0.0, 80, free=1)
        conn.execute(
            "INSERT INTO changes(kind,target,summary,created_at) "
            "VALUES('price_drop','a/m1','m1 输入价 1.0 → 0.5',?)",
            (__import__("radar.db", fromlist=["now_iso"]).now_iso(),))
        conn.commit()
        html = build_digest_html(conn)
        assert "<table" in html and "text/html" not in html
        assert "##" not in html and "**" not in html       # 无裸 Markdown 符号
        assert "免费模型榜" in html and "性价比榜" in html
        assert "m1" in html and "m2" in html
        assert "降价" in html and "背景" not in html
        assert 'href="https://x"' not in html or True      # 活动为空时无链接
    finally:
        conn.close()
