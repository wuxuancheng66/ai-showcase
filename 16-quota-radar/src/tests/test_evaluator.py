"""评估引擎测试：混合价、价值指数、五场景排序、跨源去重。"""

import pytest

from radar.core.evaluator import blended_price, canonical_name, recommend
from radar.db import connect, init_db


def add_model(conn, key, model_id, in_p, out_p, score, free=0, ctx=128000,
              flags='{"code": false, "reasoning": false}', source="litellm"):
    conn.execute(
        "INSERT INTO models(key,provider,model_id,display_name,input_price,output_price,"
        "context_len,free,capability_score,scenario_flags,source,updated_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,datetime('now'))",
        (key, key.split("/")[0], model_id, model_id, in_p, out_p, ctx, free, score, flags, source),
    )
    conn.commit()


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "e.db"
    init_db(p)
    conn = connect(p)
    yield conn
    conn.close()


def test_canonical_name():
    assert canonical_name("deepseek/deepseek-chat") == "deepseek-chat"
    assert canonical_name("meta-llama/llama-3.3-70b:free") == "llama-3.3-70b"
    assert canonical_name("gpt-4o") == "gpt-4o"


def test_blended_price(db):
    m = {"input_price": 3.0, "output_price": 10.0}
    assert abs(blended_price(m) - (0.75 * 3.0 + 0.25 * 10.0)) < 1e-9


def test_recommend_chat_by_value_index(db):
    add_model(db, "a/m1", "m1", 3.0, 10.0, 80)    # value ≈ 16.8
    add_model(db, "b/m2", "m2", 5.0, 15.0, 90)    # value = 12
    add_model(db, "c/m3", "m3", 0.5, 2.0, 70)     # value = 80 → 第一
    top = recommend(db, "chat", top_n=3)
    assert [t["model_id"] for t in top] == ["m3", "m1", "m2"]
    assert top[0]["value_index"] == 80.0


def test_recommend_low_score_excluded(db):
    add_model(db, "a/cheap", "cheap", 0.1, 0.3, 55)  # 低于 chat 门槛 70
    assert recommend(db, "chat") == []


def test_recommend_code_scenario(db):
    add_model(db, "a/coder", "coder", 1.0, 3.0, 76, flags='{"code": true, "reasoning": false}')
    add_model(db, "b/almost", "almost", 0.1, 0.2, 84)  # 无 code 标记且 <85 → 排除
    add_model(db, "c/strong", "strong", 2.0, 8.0, 90)  # 高分即入围
    ids = [t["model_id"] for t in recommend(db, "code", top_n=5)]
    assert set(ids) == {"coder", "strong"}
    assert "almost" not in ids


def test_recommend_longctx_scenario(db):
    add_model(db, "a/big", "big", 1.0, 4.0, 80, ctx=200000)
    add_model(db, "b/small", "small", 0.1, 0.2, 95, ctx=64000)  # 上下文不足 → 排除
    ids = [t["model_id"] for t in recommend(db, "longctx")]
    assert ids == ["big"]


def test_recommend_bulk_by_price(db):
    add_model(db, "a/expensive", "expensive", 10.0, 30.0, 95)
    add_model(db, "b/cheap", "cheap", 0.1, 0.5, 65)
    top = recommend(db, "bulk", top_n=2)
    assert top[0]["model_id"] == "cheap"  # 批量场景最便宜优先


def test_recommend_free_scenario(db):
    add_model(db, "a/paid", "paid", 1.0, 2.0, 95)
    add_model(db, "f/mid", "mid", 0.0, 0.0, 78, free=1)
    add_model(db, "f/low", "low", 0.0, 0.0, 60, free=1)
    top = recommend(db, "free", top_n=5)
    ids = [t["model_id"] for t in top]
    assert ids == ["mid", "low"]  # 免费榜按能力分，付费的不掺和


def test_dedupe_across_sources(db):
    add_model(db, "deepseek/deepseek-chat", "deepseek-chat", 1.0, 2.0, 85)
    add_model(db, "openrouter/deepseek/deepseek-chat", "deepseek/deepseek-chat", 0.5, 1.0, 85,
              source="openrouter")
    top = recommend(db, "chat", top_n=5)
    assert len(top) == 1
    assert top[0]["source"] == "openrouter"  # 保留价值指数更高的那条


def test_unknown_scenario_raises(db):
    with pytest.raises(ValueError):
        recommend(db, "nope")
