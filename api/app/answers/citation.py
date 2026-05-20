from uuid import UUID

from app.models.schemas import Evidence


def citation_map(evidence: list[Evidence], answer_text: str = "") -> dict[str, list[UUID]]:
    citations: dict[str, list[UUID]] = {}
    for index, item in enumerate(evidence, start=1):
        marker = f"E{index}"
        if answer_text and f"[{marker}]" not in answer_text:
            continue
        citations[marker] = [item.id]
    return citations


def verify_citations(citation_map_json: dict, evidence: list[Evidence]) -> bool:
    valid_ids = {str(item.id) for item in evidence}
    for ids in citation_map_json.values():
        for evidence_id in ids:
            if str(evidence_id) not in valid_ids:
                return False
    return True


def has_visible_citations(answer_text: str, citation_map_json: dict) -> bool:
    return all(f"[{marker}]" in answer_text for marker in citation_map_json)
