from app.providers.reranker import reranker_provider, run_configured_reranker


def rerank(query: str, merged: list[dict], provider_config=None) -> list[dict]:
    result = run_configured_reranker(provider_config, query, [item["chunk"].content for item in merged])
    if result.error_message or len(result.scores) != len(merged):
        error_message = result.error_message or "reranker returned an invalid score count"
        for item in merged:
            item["rerank_score"] = item["merged_score"]
            item["reranker_provider_name"] = "fallback_merged"
            item["reranker_model_name"] = provider_config.model_name if provider_config else reranker_provider.model_name
            item["reranker_configured_provider_name"] = provider_config.provider_name if provider_config else reranker_provider.provider_name
            item["reranker_error"] = error_message
        return sorted(merged, key=lambda item: (item["rerank_score"], item["merged_score"]), reverse=True)

    provider_name = provider_config.provider_name if provider_config else result.provider_name
    model_name = provider_config.model_name if provider_config else result.model_name
    for item, score in zip(merged, result.scores):
        item["rerank_score"] = score
        item["reranker_provider_name"] = provider_name
        item["reranker_model_name"] = model_name
    return sorted(merged, key=lambda item: (item["rerank_score"], item["merged_score"]), reverse=True)
