from .fake import FakeRerankerProvider
from .cohere import CohereRerankerProvider

reranker_provider = FakeRerankerProvider()


def is_cohere_reranker_config(provider_config) -> bool:
    return bool(provider_config and (provider_config.provider_name == "cohere" or provider_config.config_json.get("adapter") == "cohere"))


def run_configured_reranker(provider_config, query: str, documents: list[str]):
    if is_cohere_reranker_config(provider_config):
        return CohereRerankerProvider(provider_config.model_name, provider_config.config_json).rerank(query, documents)
    if provider_config and provider_config.provider_name != reranker_provider.provider_name:
        result = reranker_provider.rerank("", documents)
        result.provider_name = provider_config.provider_name
        result.model_name = provider_config.model_name
        result.scores = []
        result.error_message = f"Reranker provider '{provider_config.provider_name}' is configured but no adapter is installed."
        return result
    result = reranker_provider.rerank(query, documents)
    if provider_config:
        result.provider_name = provider_config.provider_name
        result.model_name = provider_config.model_name
    return result
