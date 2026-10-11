"""本机扫描器测试：用临时 HOME 模拟配置文件，验证发现能力与隐私红线。"""

import json

from radar.local_scan import import_keys, scan, sync_local
from radar.db import connect, init_db


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_scan_detects_platforms(tmp_path, monkeypatch):
    write(tmp_path / "proj" / ".env",
          "ZHIPU_API_KEY=fake-value-1\nDEEPSEEK_API_KEY=fake-value-2\nUNRELATED=x\n")
    write(tmp_path / "cli" / ".codex" / "auth.env",
          "export GROQ_API_KEY=fake-value-3\n")
    monkeypatch.setattr("radar.local_scan.SCAN_DIRS", [str(tmp_path)])
    monkeypatch.setattr("radar.local_scan.SCAN_FILES", [])
    monkeypatch.setattr("radar.local_scan.CLI_TOOLS", [])  # 隔离真实家目录
    monkeypatch.setattr("radar.local_scan.APP_DIRS", [str(tmp_path / "noapps")])

    result = scan()
    names = set(result.keys())
    assert "智谱 BigModel" in names
    assert "DeepSeek" in names
    assert "Groq" in names
    # 位置与变量名被记录
    assert str(tmp_path / "proj" / ".env") in result["智谱 BigModel"]["locations"]
    assert "ZHIPU_API_KEY" in result["智谱 BigModel"]["vars"]
    # 隐私红线：任何假密钥值都不出现在整个返回结构里
    assert "fake-value" not in json.dumps(result, ensure_ascii=False)


def test_scan_empty_when_nothing_configured(tmp_path, monkeypatch):
    monkeypatch.setattr("radar.local_scan.SCAN_DIRS", [str(tmp_path / "nothing")])
    monkeypatch.setattr("radar.local_scan.SCAN_FILES", [])
    monkeypatch.setattr("radar.local_scan.CLI_TOOLS", [])  # 隔离真实家目录
    monkeypatch.setattr("radar.local_scan.APP_DIRS", [str(tmp_path / "noapps")])
    assert scan() == {}


def test_sync_local_registers_activities(tmp_path, monkeypatch):
    write(tmp_path / "p" / ".env", "ZHIPU_API_KEY=fake-v\nDEEPSEEK_API_KEY=fake-v\n")
    monkeypatch.setattr("radar.local_scan.SCAN_DIRS", [str(tmp_path)])
    monkeypatch.setattr("radar.local_scan.SCAN_FILES", [])
    monkeypatch.setattr("radar.local_scan.CLI_TOOLS", [])  # 隔离真实家目录
    monkeypatch.setattr("radar.local_scan.APP_DIRS", [str(tmp_path / "noapps")])
    monkeypatch.setattr("radar.local_scan.CLI_TOOLS", [])  # 隔离真实家目录

    p = tmp_path / "s.db"
    init_db(p)
    conn = connect(p)
    try:
        result = sync_local(conn)
        # 智谱有可领活动 → 自动登记；DeepSeek 无 → 不登记
        rows = conn.execute("SELECT id FROM activities WHERE id LIKE 'local-%'").fetchall()
        ids = [r["id"] for r in rows]
        assert "local-智谱 BigModel" in ids
        assert "local-DeepSeek" not in ids
        assert "added_activities" in result
        assert "fake-v" not in conn.execute(
            "SELECT note FROM activities WHERE id='local-智谱 BigModel'").fetchone()["note"]
    finally:
        conn.close()


def test_import_keys_appends_without_duplicates(tmp_path, monkeypatch):
    source = write(tmp_path / "src" / ".env", "GROQ_API_KEY=gsk_fake123\n")
    product_dir = tmp_path / "product"
    product_dir.mkdir()
    product_env = product_dir / ".env"
    product_env.write_text("SMTP_HOST=smtp.qq.com\nGROQ_API_KEY=already-here\n", encoding="utf-8")

    monkeypatch.setattr("radar.local_scan.SCAN_DIRS", [str(tmp_path / "src")])
    monkeypatch.setattr("radar.local_scan.SCAN_FILES", [])

    # 已有同名变量 → 不重复导入
    assert import_keys(product_env) == 0

    # 换一个未配置的平台 key → 追加
    write(source, "CEREBRAS_API_KEY=csk_fake456\n")
    n = import_keys(product_env)
    assert n == 1
    content = product_env.read_text(encoding="utf-8")
    assert "CEREBRAS_API_KEY=csk_fake456" in content
    # 再次运行 → 已存在，不再追加
    assert import_keys(product_env) == 0
