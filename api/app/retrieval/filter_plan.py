from typing import Optional
from uuid import UUID


def build_filter_plan(product_id: Optional[UUID], detected_entities: Optional[dict] = None) -> dict:
    if product_id:
        return {"filters": [{"type": "hard_filter", "field": "product_id", "value": str(product_id)}]}
    soft_boosts = [
        {"type": "soft_boost", "field": "product_id", "value": item["product_id"], "confidence": item["confidence"]}
        for item in (detected_entities or {}).get("products", [])
    ]
    return {"filters": soft_boosts, "notes": ["No product hard filter; all enabled chunks are eligible."]}
