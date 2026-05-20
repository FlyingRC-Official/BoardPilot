from typing import Any, Optional
from uuid import UUID

HIGH_CONFIDENCE_PRODUCT_THRESHOLD = 0.95


def high_confidence_product_id(detected_entities: Optional[dict] = None) -> Optional[str]:
    products = (detected_entities or {}).get("products", [])
    if not products:
        return None
    top = max(products, key=lambda item: item.get("confidence", 0.0))
    if top.get("confidence", 0.0) < HIGH_CONFIDENCE_PRODUCT_THRESHOLD:
        return None
    return top.get("product_id")


def build_filter_plan(
    product_id: Optional[UUID],
    detected_entities: Optional[dict] = None,
    metadata_filters: Optional[dict[str, Any]] = None,
) -> dict:
    filters = []
    detected_product_id = high_confidence_product_id(detected_entities)
    if product_id:
        filters.append({"type": "hard_filter", "field": "product_id", "value": str(product_id)})
    elif detected_product_id:
        filters.append(
            {
                "type": "hard_filter",
                "field": "product_id",
                "value": detected_product_id,
                "source": "detected_entity",
                "confidence_threshold": HIGH_CONFIDENCE_PRODUCT_THRESHOLD,
            }
        )
    for field, value in (metadata_filters or {}).items():
        filters.append({"type": "hard_filter", "field": field, "value": value})
    if product_id or detected_product_id:
        return {"filters": filters}
    soft_boosts = [
        {"type": "soft_boost", "field": "product_id", "value": item["product_id"], "confidence": item["confidence"]}
        for item in (detected_entities or {}).get("products", [])
    ]
    return {"filters": filters + soft_boosts, "notes": ["No product hard filter; all enabled chunks are eligible."]}
