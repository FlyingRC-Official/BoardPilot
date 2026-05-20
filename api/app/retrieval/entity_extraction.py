import re
from typing import Any

from app.db.store import InMemoryStore
from app.models.schemas import ProductAlias


def _contains_alias(text: str, alias: str) -> bool:
    normalized_text = text.lower()
    normalized_alias = alias.lower().strip()
    if not normalized_alias:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(normalized_alias) + r"(?![a-z0-9])"
    return re.search(pattern, normalized_text) is not None


def detect_product_aliases(store: InMemoryStore, text: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for alias in store.product_aliases.values():
        if _contains_alias(text, alias.alias):
            product = store.products.get(alias.product_id)
            matches.append(
                {
                    "product_id": str(alias.product_id),
                    "product_name": product.name if product else "",
                    "alias": alias.alias,
                    "alias_type": alias.alias_type,
                    "confidence": alias.confidence,
                }
            )
    matches.sort(key=lambda item: item["confidence"], reverse=True)
    return {"products": matches}


def aliases_for_product(store: InMemoryStore, product_id) -> list[ProductAlias]:
    return [alias for alias in store.product_aliases.values() if alias.product_id == product_id]

