import math

from app.providers.base import EmbeddingProvider, LLMProvider, OCRProvider, RerankerProvider
from app.providers.fake import FakeEmbeddingProvider, FakeLLMProvider, FakeOCRProvider, FakeRerankerProvider
from app.providers.openai_compatible import OpenAICompatibleEmbeddingProvider, OpenAICompatibleLLMProvider


def test_fake_embedding_provider_returns_structured_normalized_result():
    provider: EmbeddingProvider = FakeEmbeddingProvider()

    result = provider.embed("FlyingRC F4 USB power USB")

    assert result.provider_name == "fake"
    assert result.model_name == "fake-hash-embedding"
    assert result.latency_ms >= 0
    assert result.error_message == ""
    assert len(result.vector) == 16
    assert math.isclose(math.sqrt(sum(value * value for value in result.vector)), 1.0)


def test_fake_reranker_provider_returns_one_score_per_document():
    provider: RerankerProvider = FakeRerankerProvider()

    result = provider.rerank("USB power connector", ["USB connector setup", "CAN bus telemetry"])

    assert result.provider_name == "fake"
    assert result.model_name == "fake-overlap-reranker"
    assert result.latency_ms >= 0
    assert result.error_message == ""
    assert len(result.scores) == 2
    assert result.scores[0] > result.scores[1]


def test_fake_llm_provider_returns_citation_backed_answer_shape():
    provider: LLMProvider = FakeLLMProvider()

    result = provider.answer("Can I power servos from USB?", ["USB is for configuration only.", "Do not power servos from USB."])

    assert result.provider_name == "fake"
    assert result.model_name == "fake-citation-llm"
    assert result.latency_ms >= 0
    assert result.error_message == ""
    assert "[E1]" in result.answer_text
    assert "[E2]" in result.answer_text


def test_fake_llm_provider_handles_empty_evidence_without_citations():
    provider: LLMProvider = FakeLLMProvider()

    result = provider.answer("Can I power servos from USB?", [])

    assert result.provider_name == "fake"
    assert result.model_name == "fake-citation-llm"
    assert "not have enough saved evidence" in result.answer_text


def test_openai_compatible_llm_provider_requires_credentials(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAICompatibleLLMProvider("openai", "gpt-test", {})

    result = provider.answer("Can I power servos from USB?", ["USB is for configuration only."])

    assert result.provider_name == "openai"
    assert result.model_name == "gpt-test"
    assert result.error_message == "OpenAI-compatible LLM provider is configured but no API key is available."
    assert "missing credentials" in result.answer_text


def test_openai_compatible_llm_provider_parses_chat_completion(monkeypatch):
    captured = {}

    def fake_post_json(url, headers, payload, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        captured["timeout"] = timeout
        return {"choices": [{"message": {"content": "USB is for configuration only. [E1]"}}]}

    monkeypatch.setattr("app.providers.openai_compatible._post_json", fake_post_json)
    provider = OpenAICompatibleLLMProvider(
        "openai_compatible",
        "hardware-chat",
        {"api_key": "test-key", "base_url": "https://llm.internal/v1", "timeout_seconds": 7},
    )

    result = provider.answer("Can I power servos from USB?", ["USB is for configuration only."])

    assert result.error_message == ""
    assert result.answer_text == "USB is for configuration only. [E1]"
    assert captured["url"] == "https://llm.internal/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["payload"]["model"] == "hardware-chat"
    assert "[E1] USB is for configuration only." in captured["payload"]["messages"][1]["content"]
    assert captured["timeout"] == 7


def test_openai_compatible_embedding_provider_requires_credentials(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAICompatibleEmbeddingProvider("openai", "embed-test", {})

    result = provider.embed("USB power")

    assert result.provider_name == "openai"
    assert result.model_name == "embed-test"
    assert result.vector == []
    assert result.error_message == "OpenAI-compatible embedding provider is configured but no API key is available."


def test_openai_compatible_embedding_provider_parses_embedding_response(monkeypatch):
    captured = {}

    def fake_post_json(url, headers, payload, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        captured["timeout"] = timeout
        return {"data": [{"embedding": [0.25, 0.5, 0.75]}]}

    monkeypatch.setattr("app.providers.openai_compatible._post_json", fake_post_json)
    provider = OpenAICompatibleEmbeddingProvider(
        "openai_compatible",
        "hardware-embed",
        {"api_key": "test-key", "base_url": "https://llm.internal/v1", "timeout_seconds": 9},
    )

    result = provider.embed("USB power")

    assert result.error_message == ""
    assert result.vector == [0.25, 0.5, 0.75]
    assert captured["url"] == "https://llm.internal/v1/embeddings"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["payload"] == {"model": "hardware-embed", "input": "USB power"}
    assert captured["timeout"] == 9


def test_fake_ocr_provider_returns_structured_placeholder_result():
    provider: OCRProvider = FakeOCRProvider()

    result = provider.ocr("local://image.png")

    assert result.provider_name == "fake"
    assert result.model_name == "fake-ocr-placeholder"
    assert result.latency_ms >= 0
    assert result.error_message == ""
    assert result.text == ""
    assert result.confidence == 0.0
