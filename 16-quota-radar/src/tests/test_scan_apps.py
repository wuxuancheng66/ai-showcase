"""桌面应用识别测试。"""

from radar.local_scan import scan_apps, _load_platform_index


def test_scan_apps_detects_and_matches(tmp_path, monkeypatch):
    # 伪造两个应用包
    (tmp_path / "AutoClaw.app").mkdir()
    (tmp_path / "ChatGPT.app").mkdir()
    (tmp_path / "随机应用.app").mkdir()
    monkeypatch.setattr("radar.local_scan.APP_DIRS", [str(tmp_path)])

    index = [p for p in _load_platform_index() if p.get("apps")]
    result = scan_apps(index)
    names = set(result.keys())
    assert "AutoClaw（GLM 生态 agent）" in names
    assert "OpenAI（ChatGPT）" in names
    # 隐私/安全：位置记录的是 .app 路径
    assert any("AutoClaw.app" in loc for loc in result["AutoClaw（GLM 生态 agent）"]["locations"])
    # 未匹配平台的应用不出现
    assert all("随机应用" not in n for n in names)


def test_scan_apps_no_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr("radar.local_scan.APP_DIRS", [str(tmp_path / "nothing")])
    assert scan_apps(_load_platform_index()) == {}
