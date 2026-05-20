from typing import Any, Optional
from uuid import UUID


def build_filter_plan(
    product_id: Optional[UUID],
    detected_entities: Optional[dict] = None,
    metadata_filters: Optional[dict[str, Any]] = None,
) -> dict:
    filters = []
    if product_id:
        filters.append({"type": "hard_filter", "field": "product_id", "value": str(product_id)})
    for field, value in (metadata_filters or {}).items():
        filters.append({"type": "hard_filter", "field": field, "value": value})
    if product_id:
        return {"filters": filters}
    soft_boosts = [
        {"type": "soft_boost", "field": "product_id", "value": item["product_id"], "confidence": item["confidence"]}
        for item in (detected_entities or {}).get("products", [])
    ]
    return {"filters": filters + soft_boosts, "notes": ["No product hard filter; all enabled chunks are eligible."]}
