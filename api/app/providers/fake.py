import math
from collections import Counter
from typing import List

from .base import EmbeddingResult, LLMResult, ProviderResult, RerankResult


def tokenize(text: str) -> List[str]:
    return [t.lower() for t in text.replace("/", " ").replace("-", " ").split() if t.strip()]


class FakeEmbeddingProvider:
    provider_name = "fake"
    model_name = "fake-hash-embedding"

    def embed(self, text: str) -> EmbeddingResult:
        buckets = [0.0] * 16
        for token in tokenize(text):
            buckets[hash(token) % len(buckets)] += 1.0
        norm = math.sqrt(sum(v * v for v in buckets)) or 1.0
        return EmbeddingResult(self.provider_name, self.model_name, 0, vector=[v / norm for v in buckets])


class FakeRerankerProvider:
    provider_name = "fake"
    model_name = "fake-overlap-reranker"

    def rerank(self, query: str, documents: List[str]) -> RerankResult:
        q = Counter(tokenize(query))
        scores = []
        for document in documents:
            d = Counter(tokenize(document))
            overlap = sum(min(q[t], d[t]) for t in q)
            scores.append(overlap / max(len(q), 1))
        return RerankResult(self.provider_name, self.model_name, 0, scores=scores)


class FakeLLMProvider:
    provider_name = "fake"
    model_name = "fake-citation-llm"

    def answer(self, question: str, evidence_quotes: List[str]) -> LLMResult:
        if not evidence_quotes:
            return LLMResult(self.provider_name, self.model_name, 0, answer_text="I do not have enough saved evidence to answer this.")
        answer = "Based on the saved evidence, " + " ".join(
            f"{quote.strip()[:180]} [E{i + 1}]" for i, quote in enumerate(evidence_quotes[:3])
        )
        return LLMResult(self.provider_name, self.model_name, 0, answer_text=answer)


class FakeOCRProvider:
    provider_name = "fake"
    model_name = "fake-ocr-placeholder"

    def ocr(self, image_uri: str) -> ProviderResult:
        return ProviderResult(self.provider_name, self.model_name, 0)

