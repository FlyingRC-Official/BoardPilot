from uuid import UUID

from app.models.schemas import Evidence


def citation_map(evidence: list[Evidence]) -> dict[str, list[UUID]]:
    return {f"E{index}": [item.id] for index, item in enumerate(evidence, start=1)}


def verify_citations(citation_map_json: dict, evidence: list[Evidence]) -> bool:
    valid_ids = {str(item.id) for item in evidence}
    for ids in citation_map_json.values():
        for evidence_id in ids:
            if str(evidence_id) not in valid_ids:
                return False
    return True

