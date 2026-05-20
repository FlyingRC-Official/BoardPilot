import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import RerankResult


DEFAULT_BASE_URL = "https://api.cohere.com/v2"
DEFAULT_TIMEOUT_SECONDS = 30


def _api_key(config_json: dict[str, Any]) -> str:
    explicit = str(config_json.get("api_key", "") or "").strip()
    if explicit:
        return explicit
    env_name = str(config_json.get("api_key_env", "COHERE_API_KEY") or "COHERE_API_KEY")
    return os.environ.get(env_name, "").strip()


def _rerank_url(config_json: dict[str, Any]) -> str:
    base_url = str(config_json.get("base_url", DEFAULT_BASE_URL) or DEFAULT_BASE_URL).rstrip("/")
    return f"{base_url}/rerank"


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class CohereRerankerProvider:
    provider_name = "cohere"

    def __init__(self, model_name: str, config_json: dict[str, Any]) -> None:
        self.model_name = model_name
        self.config_json = config_json

    def rerank(self, query: str, documents: list[str]) -> RerankResult:
        started = time.monotonic()
        api_key = _api_key(self.config_json)
        if not api_key:
            return RerankResult(
                self.provider_name,
                self.model_name,
                0,
                error_message="Cohere reranker provider is configured but no API key is available.",
                scores=[],
            )

        payload = {
            "model": self.model_name,
            "query": query,
            "documents": documents,
            "top_n": int(self.config_json.get("top_n", len(documents)) or len(documents)),
        }
        try:
            response = _post_json(
                _rerank_url(self.config_json),
                {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                payload,
                float(self.config_json.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS) or DEFAULT_TIMEOUT_SECONDS),
            )
        except HTTPError as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            error_detail = exc.read().decode("utf-8", errors="replace").strip()
            return RerankResult(
                self.provider_name,
                self.model_name,
                latency_ms,
                error_message=error_detail or f"Cohere reranker request failed with HTTP {exc.code}.",
                scores=[],
            )
        except (TimeoutError, URLError, OSError) as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            return RerankResult(
                self.provider_name,
                self.model_name,
                latency_ms,
                error_message=str(exc) or exc.__class__.__name__,
                scores=[],
            )

        scores = [0.0] * len(documents)
        for result in response.get("results", []):
            index = int(result.get("index", -1))
            if 0 <= index < len(scores):
                scores[index] = float(result.get("relevance_score", 0.0) or 0.0)
        latency_ms = int((time.monotonic() - started) * 1000)
        if not response.get("results") and documents:
            return RerankResult(
                self.provider_name,
                self.model_name,
                latency_ms,
                error_message="Cohere reranker response did not include results.",
                scores=[],
            )
        return RerankResult(self.provider_name, self.model_name, latency_ms, scores=scores)
