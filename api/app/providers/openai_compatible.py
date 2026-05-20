import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import EmbeddingResult, LLMResult


DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_TIMEOUT_SECONDS = 30


def _api_key(config_json: dict[str, Any]) -> str:
    explicit = str(config_json.get("api_key", "") or "").strip()
    if explicit:
        return explicit
    env_name = str(config_json.get("api_key_env", "OPENAI_API_KEY") or "OPENAI_API_KEY")
    return os.environ.get(env_name, "").strip()


def _chat_url(config_json: dict[str, Any]) -> str:
    base_url = str(config_json.get("base_url", DEFAULT_BASE_URL) or DEFAULT_BASE_URL).rstrip("/")
    return f"{base_url}/chat/completions"


def _embeddings_url(config_json: dict[str, Any]) -> str:
    base_url = str(config_json.get("base_url", DEFAULT_BASE_URL) or DEFAULT_BASE_URL).rstrip("/")
    return f"{base_url}/embeddings"


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class OpenAICompatibleLLMProvider:
    def __init__(self, provider_name: str, model_name: str, config_json: dict[str, Any]) -> None:
        self.provider_name = provider_name
        self.model_name = model_name
        self.config_json = config_json

    def answer(self, question: str, evidence_quotes: list[str]) -> LLMResult:
        started = time.monotonic()
        api_key = _api_key(self.config_json)
        if not api_key:
            return LLMResult(
                self.provider_name,
                self.model_name,
                0,
                error_message="OpenAI-compatible LLM provider is configured but no API key is available.",
                answer_text="Answer generation failed because the configured LLM provider is missing credentials.",
            )

        evidence_text = "\n".join(f"[E{index}] {quote}" for index, quote in enumerate(evidence_quotes, start=1))
        system_prompt = str(
            self.config_json.get(
                "system_prompt",
                "Answer only from the supplied evidence. Cite every factual claim with visible [E#] markers.",
            )
            or ""
        )
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Question:\n{question}\n\nEvidence:\n{evidence_text}",
                },
            ],
            "temperature": float(self.config_json.get("temperature", 0.0) or 0.0),
        }
        if "max_tokens" in self.config_json:
            payload["max_tokens"] = int(self.config_json["max_tokens"])

        try:
            response = _post_json(
                _chat_url(self.config_json),
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
            return LLMResult(
                self.provider_name,
                self.model_name,
                latency_ms,
                error_message=error_detail or f"OpenAI-compatible LLM request failed with HTTP {exc.code}.",
                answer_text="Answer generation failed because the configured LLM provider returned an error.",
            )
        except (TimeoutError, URLError, OSError) as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            return LLMResult(
                self.provider_name,
                self.model_name,
                latency_ms,
                error_message=str(exc) or exc.__class__.__name__,
                answer_text="Answer generation failed because the configured LLM provider is unavailable.",
            )

        latency_ms = int((time.monotonic() - started) * 1000)
        answer_text = (
            response.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not answer_text:
            return LLMResult(
                self.provider_name,
                self.model_name,
                latency_ms,
                error_message="OpenAI-compatible LLM response did not include message content.",
                answer_text="Answer generation failed because the configured LLM provider returned an empty answer.",
            )
        return LLMResult(self.provider_name, self.model_name, latency_ms, answer_text=answer_text)


class OpenAICompatibleEmbeddingProvider:
    def __init__(self, provider_name: str, model_name: str, config_json: dict[str, Any]) -> None:
        self.provider_name = provider_name
        self.model_name = model_name
        self.config_json = config_json

    def embed(self, text: str) -> EmbeddingResult:
        started = time.monotonic()
        api_key = _api_key(self.config_json)
        if not api_key:
            return EmbeddingResult(
                self.provider_name,
                self.model_name,
                0,
                error_message="OpenAI-compatible embedding provider is configured but no API key is available.",
                vector=[],
            )

        try:
            response = _post_json(
                _embeddings_url(self.config_json),
                {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                {
                    "model": self.model_name,
                    "input": text,
                },
                float(self.config_json.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS) or DEFAULT_TIMEOUT_SECONDS),
            )
        except HTTPError as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            error_detail = exc.read().decode("utf-8", errors="replace").strip()
            return EmbeddingResult(
                self.provider_name,
                self.model_name,
                latency_ms,
                error_message=error_detail or f"OpenAI-compatible embedding request failed with HTTP {exc.code}.",
                vector=[],
            )
        except (TimeoutError, URLError, OSError) as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            return EmbeddingResult(
                self.provider_name,
                self.model_name,
                latency_ms,
                error_message=str(exc) or exc.__class__.__name__,
                vector=[],
            )

        latency_ms = int((time.monotonic() - started) * 1000)
        vector = response.get("data", [{}])[0].get("embedding", [])
        if not vector:
            return EmbeddingResult(
                self.provider_name,
                self.model_name,
                latency_ms,
                error_message="OpenAI-compatible embedding response did not include a vector.",
                vector=[],
            )
        return EmbeddingResult(self.provider_name, self.model_name, latency_ms, vector=[float(value) for value in vector])
