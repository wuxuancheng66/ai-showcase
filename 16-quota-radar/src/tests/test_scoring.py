"""能力评分测试。"""

from radar.core.scoring import scenario_flags, score_model


def test_exact_seed_match():
    assert score_model("gpt-4o") == 88.0
    assert score_model("claude-opus-4") == 95.0


def test_substring_longest_wins():
    # "openai/gpt-4o-2024-08-06" 含 "gpt-4o" → 88
    assert score_model("openai/gpt-4o-2024-08-06") == 88.0
    # 同时含 "gpt-4o" 和 "gpt-4o-mini"，最长关键词优先 → 78
    assert score_model("gpt-4o-mini-2024") == 78.0


def test_family_fallback_and_bounds():
    base = score_model("totally-unknown-model")
    with_modifier = score_model("totally-unknown-model-mini")
    assert base == 60.0
    assert with_modifier < base
    assert 1.0 <= with_modifier <= 99.0
    # 极端叠加不越界
    assert 1.0 <= score_model("x-max-opus-pro-large-thinking-r1") <= 99.0


def test_scenario_flags():
    assert scenario_flags("deepseek-r1")["reasoning"] is True
    assert scenario_flags("codestral")["code"] is True
    assert scenario_flags("gpt-4o")["reasoning"] is False
