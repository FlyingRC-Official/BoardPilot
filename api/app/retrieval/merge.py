from uuid import UUID


def _ranges_overlap(left_start: int, left_end: int, right_start: int, right_end: int) -> bool:
    left_size = max(left_end - left_start, 1)
    right_size = max(right_end - right_start, 1)
    overlap = max(0, min(left_end, right_end) - max(left_start, right_start))
    return overlap / min(left_size, right_size) >= 0.8


def _same_source_position(left, right) -> bool:
    if left.source_version_id != right.source_version_id:
        return False
    if left.page_number is not None and right.page_number is not None and left.page_number != right.page_number:
        return False
    left_section = left.section_name or left.title_path
    right_section = right.section_name or right.title_path
    if left_section and right_section and left_section != right_section:
        return False
    if left.char_end <= left.char_start or right.char_end <= right.char_start:
        return False
    return _ranges_overlap(left.char_start, left.char_end, right.char_start, right.char_end)


def _is_duplicate_candidate(left, right) -> bool:
    if left.id == right.id:
        return True
    if left.content_hash and right.content_hash and left.content_hash == right.content_hash:
        return True
    return _same_source_position(left, right)


def _merge_duplicate_candidate(target: dict, duplicate: dict) -> None:
    target["keyword_score"] = max(target["keyword_score"], duplicate["keyword_score"])
    target["vector_score"] = max(target["vector_score"], duplicate["vector_score"])
    target["merged_score"] = (target["keyword_score"] * 0.65) + (target["vector_score"] * 0.35)
    target.setdefault("deduped_chunk_ids", [])
    duplicate_id = str(duplicate["chunk"].id)
    if duplicate_id != str(target["chunk"].id) and duplicate_id not in target["deduped_chunk_ids"]:
        target["deduped_chunk_ids"].append(duplicate_id)


def merge_candidates(keyword_hits: list[tuple[object, float]], vector_hits: list[tuple[object, float]]) -> list[dict]:
    by_chunk_id: dict[UUID, dict] = {}
    for chunk, score in keyword_hits:
        by_chunk_id.setdefault(chunk.id, {"chunk": chunk, "keyword_score": 0.0, "vector_score": 0.0})
        by_chunk_id[chunk.id]["keyword_score"] = max(by_chunk_id[chunk.id]["keyword_score"], score)
    for chunk, score in vector_hits:
        by_chunk_id.setdefault(chunk.id, {"chunk": chunk, "keyword_score": 0.0, "vector_score": 0.0})
        by_chunk_id[chunk.id]["vector_score"] = max(by_chunk_id[chunk.id]["vector_score"], score)
    for item in by_chunk_id.values():
        item["merged_score"] = (item["keyword_score"] * 0.65) + (item["vector_score"] * 0.35)

    deduped: list[dict] = []
    for item in sorted(by_chunk_id.values(), key=lambda entry: entry["merged_score"], reverse=True):
        duplicate_of = next(
            (
                existing
                for existing in deduped
                if _is_duplicate_candidate(existing["chunk"], item["chunk"])
            ),
            None,
        )
        if duplicate_of:
            _merge_duplicate_candidate(duplicate_of, item)
        else:
            item["deduped_chunk_ids"] = []
            deduped.append(item)
    return sorted(deduped, key=lambda item: item["merged_score"], reverse=True)[:50]
