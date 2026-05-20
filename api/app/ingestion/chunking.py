import hashlib
import re
from typing import List
from uuid import UUID

from app.models.schemas import Chunk


def content_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def chunk_text(source_version_id: UUID, product_id: UUID, text: str, target_chars: int = 900) -> List[Chunk]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs and text.strip():
        paragraphs = [text.strip()]

    chunks: List[Chunk] = []
    buffer = ""
    start = 0
    index = 0

    def flush(content: str, char_start: int) -> None:
        nonlocal index
        if not content.strip():
            return
        clean = content.strip()
        chunks.append(
            Chunk(
                source_version_id=source_version_id,
                product_id=product_id,
                chunk_index=index,
                content=clean,
                content_hash=content_hash(clean),
                token_count=len(clean.split()),
                char_start=char_start,
                char_end=char_start + len(clean),
                section_name=clean.splitlines()[0][:80] if clean else "",
            )
        )
        index += 1

    cursor = 0
    for paragraph in paragraphs:
        paragraph_start = text.find(paragraph, cursor)
        cursor = paragraph_start + len(paragraph) if paragraph_start >= 0 else cursor
        if len(buffer) + len(paragraph) + 2 > target_chars and buffer:
            flush(buffer, start)
            buffer = paragraph
            start = paragraph_start if paragraph_start >= 0 else cursor
        else:
            if not buffer:
                start = paragraph_start if paragraph_start >= 0 else cursor
            buffer = f"{buffer}\n\n{paragraph}" if buffer else paragraph
    flush(buffer, start)
    return chunks

