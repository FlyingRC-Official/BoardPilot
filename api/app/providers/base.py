from dataclasses import dataclass
from typing import List, Protocol


@dataclass
class ProviderResult:
    provider_name: str
    model_name: str
    latency_ms: int
    error_message: str = ""


@dataclass
class EmbeddingResult(ProviderResult):
    vector: List[float] = None


@dataclass
class RerankResult(ProviderResult):
    scores: List[float] = None


@dataclass
class LLMResult(ProviderResult):
    answer_text: str = ""


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> EmbeddingResult:
        ...


class RerankerProvider(Protocol):
    def rerank(self, query: str, documents: List[str]) -> RerankResult:
        ...


class LLMProvider(Protocol):
    def answer(self, question: str, evidence_quotes: List[str]) -> LLMResult:
        ...


class OCRProvider(Protocol):
    def ocr(self, image_uri: str) -> ProviderResult:
        ...

