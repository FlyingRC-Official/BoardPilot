from .fake import FakeEmbeddingProvider
from .openai_compatible import OpenAICompatibleEmbeddingProvider

embedding_provider = FakeEmbeddingProvider()


def is_openai_compatible_embedding_config(provider_config) -> bool:
    return bool(
        provider_config
        and (
            provider_config.provider_name in {"openai", "openai_compatible", "openai-compatible"}
            or provider_config.config_json.get("adapter") == "openai_compatible"
        )
    )


def run_configured_embedding(provider_config, text: str):
    if is_openai_compatible_embedding_config(provider_config):
        return OpenAICompatibleEmbeddingProvider(
            provider_config.provider_name,
            provider_config.model_name,
            provider_config.config_json,
        ).embed(text)
    if provider_config and provider_config.provider_name != embedding_provider.provider_name:
        result = embedding_provider.embed("")
        result.provider_name = provider_config.provider_name
        result.model_name = provider_config.model_name
        result.vector = []
        result.error_message = f"Embedding provider '{provider_config.provider_name}' is configured but no adapter is installed."
        return result
    result = embedding_provider.embed(text)
    if provider_config:
        result.provider_name = provider_config.provider_name
        result.model_name = provider_config.model_name
    return result
