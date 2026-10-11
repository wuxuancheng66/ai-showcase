"""采集器测试：重试退避、双源解析、免费判定。全部 mock 网络。

注意：路由必须通过 respx.mock(...) 返回的 mock 对象注册（mock.get），
模块级 respx.get 指向默认路由器，与带 kwargs 的新路由器不一致。
"""

import respx
from httpx import Response

from radar.collectors import litellm, openrouter
from radar.collectors.http import CollectorError, fetch_json

LITELLM_SAMPLE = {
    "gpt-4o": {
        "mode": "chat", "litellm_provider": "openai",
        "input_cost_per_token": 0.0000025, "output_cost_per_token": 0.00001,
        "max_input_tokens": 128000, "max_tokens": 4096,
    },
    "glm-4.5-flash": {
        "mode": "chat", "litellm_provider": "zhipu",
        "input_cost_per_token": 0.0, "output_cost_per_token": 0.0,
        "max_input_tokens": 128000,
    },
    "text-embedding-3-small": {
        "mode": "embedding", "litellm_provider": "openai",
        "input_cost_per_token": 2e-8, "output_cost_per_token": 0.0,
    },
    "broken-entry": {"mode": "chat", "litellm_provider": "openai"},
    "$sample_spec": "not-a-model",
}

OPENROUTER_SAMPLE = {
    "data": [
        {"id": "openai/gpt-4o", "name": "OpenAI: GPT-4o", "context_length": 128000,
         "pricing": {"prompt": "0.0000025", "completion": "0.00001"}},
        {"id": "meta-llama/llama-3.3-70b-instruct:free", "name": "Meta: Llama 3.3 70B (free)",
         "context_length": 131072, "pricing": {"prompt": "0", "completion": "0"}},
        {"id": "weird/model", "name": "Weird", "context_length": 8000,
         "pricing": {"prompt": "-1", "completion": "0"}},
    ]
}


def test_fetch_json_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("radar.collectors.http.time.sleep", lambda s: None)
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get("https://example.com/data.json").mock(
            side_effect=[Response(500), Response(500), Response(200, json={"ok": True})]
        )
        assert fetch_json("https://example.com/data.json") == {"ok": True}
        assert route.call_count == 3


def test_fetch_json_exhausts_retries(monkeypatch):
    monkeypatch.setattr("radar.collectors.http.time.sleep", lambda s: None)
    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://example.com/bad.json").respond(status_code=503)
        try:
            fetch_json("https://example.com/bad.json", retries=2)
            raised = False
        except CollectorError:
            raised = True
        assert raised


def test_litellm_collect_parse():
    with respx.mock(assert_all_called=False) as mock:
        mock.get(litellm.PRIMARY_URL).respond(json=LITELLM_SAMPLE)
        models = litellm.collect()
    assert len(models) == 2  # embedding/broken/$sample 被过滤
    gpt4o = next(m for m in models if m["model_id"] == "gpt-4o")
    assert gpt4o["input_price"] == 2.5   # 0.0000025 * 1e6
    assert gpt4o["output_price"] == 10.0
    assert gpt4o["context_len"] == 128000
    assert gpt4o["free"] == 0
    flash = next(m for m in models if m["model_id"] == "glm-4.5-flash")
    assert flash["free"] == 1


def test_litellm_fallback_source(monkeypatch):
    monkeypatch.setattr("radar.collectors.http.time.sleep", lambda s: None)
    with respx.mock(assert_all_called=False) as mock:
        mock.get(litellm.PRIMARY_URL).respond(status_code=404)
        mock.get(litellm.FALLBACK_URL).respond(json=LITELLM_SAMPLE)
        models = litellm.collect()
    assert len(models) == 2


def test_litellm_all_sources_down(monkeypatch):
    monkeypatch.setattr("radar.collectors.http.time.sleep", lambda s: None)
    with respx.mock(assert_all_called=False) as mock:
        mock.get(litellm.PRIMARY_URL).respond(status_code=500)
        mock.get(litellm.FALLBACK_URL).respond(status_code=500)
        try:
            litellm.collect()
            raised = False
        except CollectorError:
            raised = True
        assert raised


def test_openrouter_collect_parse():
    with respx.mock(assert_all_called=False) as mock:
        mock.get(openrouter.MODELS_URL).respond(json=OPENROUTER_SAMPLE)
        models = openrouter.collect()
    assert len(models) == 2  # 负价格被跳过
    free_model = next(m for m in models if m["free"] == 1)
    assert free_model["model_id"].endswith(":free")
    assert free_model["provider"] == "meta-llama"
    gpt4o = next(m for m in models if m["model_id"] == "openai/gpt-4o")
    assert gpt4o["input_price"] == 2.5
