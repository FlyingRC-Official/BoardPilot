from uuid import UUID


def merge_candidates(keyword_hits: list[tuple[object, float]], vector_hits: list[tuple[object, float]]) -> list[dict]:
    merged: dict[UUID, dict] = {}
    for chunk, score in keyword_hits:
        merged.setdefault(chunk.id, {"chunk": chunk, "keyword_score": 0.0, "vector_score": 0.0})
        merged[chunk.id]["keyword_score"] = max(merged[chunk.id]["keyword_score"], score)
    for chunk, score in vector_hits:
        merged.setdefault(chunk.id, {"chunk": chunk, "keyword_score": 0.0, "vector_score": 0.0})
        merged[chunk.id]["vector_score"] = max(merged[chunk.id]["vector_score"], score)
    for item in merged.values():
        item["merged_score"] = (item["keyword_score"] * 0.65) + (item["vector_score"] * 0.35)
    return sorted(merged.values(), key=lambda item: item["merged_score"], reverse=True)[:50]

