from typing import Optional
from uuid import UUID


def build_filter_plan(product_id: Optional[UUID]) -> dict:
    if product_id:
        return {"filters": [{"type": "hard_filter", "field": "product_id", "value": str(product_id)}]}
    return {"filters": [], "notes": ["No product hard filter; all enabled chunks are eligible."]}
