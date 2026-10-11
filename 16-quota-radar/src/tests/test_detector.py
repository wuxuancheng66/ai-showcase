"""变更检测测试：新模型 / 降价 / 免费状态翻转 / 幂等。"""

from radar.core.detector import detect_and_upsert
from radar.db import connect, init_db


def make(key, model_id, in_p, out_p, free=0, ctx=128000, source="litellm"):
    return {
        "key": key, "provider": key.split("/")[0], "model_id": model_id,
        "display_name": model_id, "input_price": in_p, "output_price": out_p,
        "context_len": ctx, "free": free, "capability_score": 80.0,
        "scenario_flags": '{"reasoning": false, "code": false}', "source": source,
    }


def test_new_and_price_drop(tmp_path):
    p = tmp_path / "d.db"
    init_db(p)
    conn = connect(p)
    try:
        changes1 = detect_and_upsert(conn, [make("openai/gpt-4o", "gpt-4o", 2.5, 10.0)])
        assert [c["kind"] for c in changes1] == ["new_model"]

        changes2 = detect_and_upsert(conn, [make("openai/gpt-4o", "gpt-4o", 1.5, 10.0)])
        kinds = [c["kind"] for c in changes2]
        assert kinds == ["price_drop"]
        assert "2.5 → 1.5" in changes2[0]["summary"]

        row = conn.execute("SELECT input_price FROM models WHERE key='openai/gpt-4o'").fetchone()
        assert row["input_price"] == 1.5
        assert conn.execute("SELECT COUNT(*) c FROM price_history").fetchone()["c"] == 2
    finally:
        conn.close()


def test_no_change_is_silent(tmp_path):
    p = tmp_path / "d.db"
    init_db(p)
    conn = connect(p)
    try:
        detect_and_upsert(conn, [make("a/m", "m", 2.0, 6.0)])
        changes = detect_and_upsert(conn, [make("a/m", "m", 2.0, 6.0)])
        assert changes == []
        assert conn.execute("SELECT COUNT(*) c FROM price_history").fetchone()["c"] == 1
    finally:
        conn.close()


def test_free_flag_transitions(tmp_path):
    p = tmp_path / "d.db"
    init_db(p)
    conn = connect(p)
    try:
        detect_and_upsert(conn, [make("p/m", "m", 0.0, 0.0, free=1)])
        changes = detect_and_upsert(conn, [make("p/m", "m", 3.0, 9.0, free=0)])
        # 输入价、输出价各产生一条 price_rise（0→3.0 与 0→9.0），随后免费状态事件
        kinds = [c["kind"] for c in changes]
        assert kinds.count("price_rise") == 2
        assert kinds[-1] == "free_removed"

        detect_and_upsert(conn, [make("p/m2", "m2", 0.0, 0.0, free=1)])
        changes = detect_and_upsert(conn, [make("p/m2", "m2", 0.0, 0.0, free=0)])
        assert "free_removed" in [c["kind"] for c in changes]
    finally:
        conn.close()


def test_context_change(tmp_path):
    p = tmp_path / "d.db"
    init_db(p)
    conn = connect(p)
    try:
        detect_and_upsert(conn, [make("a/m", "m", 1.0, 2.0, ctx=128000)])
        changes = detect_and_upsert(conn, [make("a/m", "m", 1.0, 2.0, ctx=200000)])
        assert [c["kind"] for c in changes] == ["context_change"]
    finally:
        conn.close()


def test_capability_and_flags_update_without_price_change(tmp_path):
    p = tmp_path / "d.db"
    init_db(p)
    conn = connect(p)
    try:
        first = make("a/m", "m", 1.0, 2.0)
        detect_and_upsert(conn, [first])
        second = dict(first)
        second["capability_score"] = 91.0
        second["scenario_flags"] = '{"reasoning": true, "code": true}'
        changes = detect_and_upsert(conn, [second])
        assert changes == []
        row = conn.execute(
            "SELECT capability_score, scenario_flags FROM models WHERE key='a/m'"
        ).fetchone()
        assert row["capability_score"] == 91.0
        assert row["scenario_flags"] == second["scenario_flags"]
    finally:
        conn.close()


def test_price_unknown_and_recovery_are_tracked(tmp_path):
    p = tmp_path / "unknown.db"
    init_db(p)
    conn = connect(p)
    try:
        detect_and_upsert(conn, [make("a/m", "m", 1.0, 2.0)])
        unknown = make("a/m", "m", None, None)
        changes = detect_and_upsert(conn, [unknown])
        assert [c["kind"] for c in changes] == ["price_unknown", "price_unknown"]
        row = conn.execute("SELECT input_price, output_price FROM models WHERE key='a/m'").fetchone()
        assert row["input_price"] is None and row["output_price"] is None

        recovered = make("a/m", "m", 1.25, 2.5)
        changes = detect_and_upsert(conn, [recovered])
        assert [c["kind"] for c in changes] == ["price_available", "price_available"]
        assert conn.execute("SELECT COUNT(*) c FROM price_history").fetchone()["c"] == 3
    finally:
        conn.close()


def test_source_change_is_persisted(tmp_path):
    p = tmp_path / "source.db"
    init_db(p)
    conn = connect(p)
    try:
        detect_and_upsert(conn, [make("a/m", "m", 1.0, 2.0, source="litellm")])
        detect_and_upsert(conn, [make("a/m", "m", 1.0, 2.0, source="openrouter")])
        row = conn.execute("SELECT source FROM models WHERE key='a/m'").fetchone()
        assert row["source"] == "openrouter"
    finally:
        conn.close()
