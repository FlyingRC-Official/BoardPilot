from app.providers.reranker import reranker_provider


def rerank(query: str, merged: list[dict], provider_config=None) -> list[dict]:
    if provider_config and provider_config.provider_name != reranker_provider.provider_name:
        error_message = f"Reranker provider '{provider_config.provider_name}' is configured but no adapter is installed."
        for item in merged:
            item["rerank_score"] = item["merged_score"]
            item["reranker_provider_name"] = "fallback_merged"
            item["reranker_model_name"] = provider_config.model_name
            item["reranker_configured_provider_name"] = provider_config.provider_name
            item["reranker_error"] = error_message
        return sorted(merged, key=lambda item: (item["rerank_score"], item["merged_score"]), reverse=True)

    result = reranker_provider.rerank(query, [item["chunk"].content for item in merged])
    provider_name = provider_config.provider_name if provider_config else result.provider_name
    model_name = provider_config.model_name if provider_config else result.model_name
    for item, score in zip(merged, result.scores):
        item["rerank_score"] = score
        item["reranker_provider_name"] = provider_name
        item["reranker_model_name"] = model_name
    return sorted(merged, key=lambda item: (item["rerank_score"], item["merged_score"]), reverse=True)
