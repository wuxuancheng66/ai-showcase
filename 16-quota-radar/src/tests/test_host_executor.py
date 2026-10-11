"""宿主执行器队列状态机回归：已完成计划绝不重复执行。"""

import json

from executor import host_executor


def _write_plan(queue_dir, **overrides):
    plan = {
        "id": "dep_test",
        "action": "open_app",
        "app_name": "OpenClaw",
        "status": "queued",
    }
    plan.update(overrides)
    path = queue_dir / f"{plan['id']}.json"
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return path, plan


def test_claim_plan_only_moves_queued_to_running(tmp_path, monkeypatch):
    monkeypatch.setattr(host_executor, "QUEUE_DIR", tmp_path)
    path, _ = _write_plan(tmp_path)
    claimed = host_executor.claim_plan(path)
    assert claimed["status"] == "running"
    assert claimed["lease_owner"].startswith("pid:")
    assert host_executor.claim_plan(path) is None


def test_completed_action_is_not_replayed(tmp_path, monkeypatch):
    monkeypatch.setattr(host_executor, "QUEUE_DIR", tmp_path)
    _write_plan(tmp_path, status="done", result={"status": "done"})

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("completed action must not run")

    monkeypatch.setattr(host_executor, "run", fail_if_called)
    assert host_executor.once() == 0


def test_queued_action_runs_exactly_once(tmp_path, monkeypatch):
    monkeypatch.setattr(host_executor, "QUEUE_DIR", tmp_path)
    _write_plan(tmp_path)
    calls = []
    monkeypatch.setattr(host_executor, "run", lambda *args, **kwargs: (calls.append(args), (0, "ok"))[1])

    host_executor.once()
    host_executor.once()
    assert len(calls) == 1
    saved = json.loads((tmp_path / "dep_test.json").read_text(encoding="utf-8"))
    assert saved["status"] == "done"


def test_executor_redacts_env_values(tmp_path, monkeypatch):
    monkeypatch.setattr(host_executor, "ROOT", tmp_path)
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=secret-value-123\n", encoding="utf-8")
    redacted = host_executor.redact_secrets("failed secret-value-123 api_key=another-value")
    assert "secret-value-123" not in redacted
    assert "another-value" not in redacted
