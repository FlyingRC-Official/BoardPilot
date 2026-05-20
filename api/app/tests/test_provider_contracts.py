import math

from app.providers.base import EmbeddingProvider, LLMProvider, OCRProvider, RerankerProvider
from app.providers.fake import FakeEmbeddingProvider, FakeLLMProvider, FakeOCRProvider, FakeRerankerProvider


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


def test_fake_ocr_provider_returns_structured_placeholder_result():
    provider: OCRProvider = FakeOCRProvider()

    result = provider.ocr("local://image.png")

    assert result.provider_name == "fake"
    assert result.model_name == "fake-ocr-placeholder"
    assert result.latency_ms >= 0
    assert result.error_message == ""
    assert result.text == ""
    assert result.confidence == 0.0
