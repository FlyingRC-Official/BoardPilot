from uuid import uuid4

from app.models.schemas import Chunk
from app.providers.fake import tokenize
from app.retrieval.keyword import keyword_score
from app.retrieval.merge import merge_candidates


def make_chunk(
    *,
    content: str = "USB power is for configuration.",
    content_hash: str = "hash-a",
    source_version_id=None,
    char_start: int = 0,
    char_end: int = 32,
    section_name: str = "Power",
) -> Chunk:
    return Chunk(
        source_version_id=source_version_id or uuid4(),
        product_id=uuid4(),
        chunk_index=0,
        content=content,
        content_hash=content_hash,
        token_count=len(content.split()),
        char_start=char_start,
        char_end=char_end,
        section_name=section_name,
    )


def test_merge_candidates_deduplicates_by_content_hash():
    first = make_chunk(content_hash="same-hash")
    second = make_chunk(content="USB power is configuration only.", content_hash="same-hash")

    merged = merge_candidates([(first, 0.4), (second, 0.9)], [(first, 0.7), (second, 0.1)])

    assert len(merged) == 1
    assert merged[0]["chunk"].id == second.id
    assert merged[0]["keyword_score"] == 0.9
    assert merged[0]["vector_score"] == 0.7
    assert merged[0]["deduped_chunk_ids"] == [str(first.id)]


def test_merge_candidates_deduplicates_near_source_positions():
    version_id = uuid4()
    first = make_chunk(source_version_id=version_id, content_hash="hash-a", char_start=100, char_end=200)
    second = make_chunk(source_version_id=version_id, content_hash="hash-b", char_start=110, char_end=190)
    separate = make_chunk(source_version_id=version_id, content_hash="hash-c", char_start=260, char_end=340)

    merged = merge_candidates([(first, 0.8), (second, 0.7), (separate, 0.6)], [])

    assert [item["chunk"].id for item in merged] == [first.id, separate.id]
    assert merged[0]["deduped_chunk_ids"] == [str(second.id)]


def test_tokenize_preserves_hardware_compound_tokens():
    tokens = tokenize("ERR-42 on USB-C with CAN-FD")

    assert "err-42" in tokens
    assert "usb-c" in tokens
    assert "can-fd" in tokens
    assert {"err", "42", "usb", "c", "can", "fd"} <= set(tokens)
    assert keyword_score("ERR-42 USB-C", "Known ERR-42 condition on USB-C") > 0.9
