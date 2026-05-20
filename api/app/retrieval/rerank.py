from app.providers.reranker import reranker_provider


def rerank(query: str, merged: list[dict]) -> list[dict]:
    scores = reranker_provider.rerank(query, [item["chunk"].content for item in merged]).scores
    for item, score in zip(merged, scores):
        item["rerank_score"] = score
    return sorted(merged, key=lambda item: (item["rerank_score"], item["merged_score"]), reverse=True)

