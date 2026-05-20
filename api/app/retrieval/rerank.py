from app.providers.reranker import reranker_provider


def rerank(query: str, merged: list[dict], provider_config=None) -> list[dict]:
    result = reranker_provider.rerank(query, [item["chunk"].content for item in merged])
    provider_name = provider_config.provider_name if provider_config else result.provider_name
    model_name = provider_config.model_name if provider_config else result.model_name
    for item, score in zip(merged, result.scores):
        item["rerank_score"] = score
        item["reranker_provider_name"] = provider_name
        item["reranker_model_name"] = model_name
    return sorted(merged, key=lambda item: (item["rerank_score"], item["merged_score"]), reverse=True)
