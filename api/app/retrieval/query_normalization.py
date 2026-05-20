import re
from typing import Optional


def normalize_query(text: str, expansions: Optional[list[str]] = None) -> str:
    normalized = re.sub(r"\s+", " ", text.strip()).lower()
    expansion_text = " ".join(expansion.lower() for expansion in expansions or [] if expansion.strip())
    if expansion_text:
        return f"{normalized} {expansion_text}"
    return normalized


def product_alias_expansions(detected_entities: dict) -> list[str]:
    expansions: list[str] = []
    for product in detected_entities.get("products", []):
        expansions.extend([product.get("product_name", ""), product.get("alias", "")])
    return sorted({item for item in expansions if item})
