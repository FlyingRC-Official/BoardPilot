import re
from typing import Any

from app.db.store import InMemoryStore
from app.models.schemas import ProductAlias


INTERFACE_TERMS = {
    "usb",
    "usb-c",
    "can",
    "can-fd",
    "uart",
    "i2c",
    "spi",
    "pwm",
    "dshot",
    "bdshot",
    "sbus",
    "crsf",
    "gps",
    "esc",
}


def _contains_alias(text: str, alias: str) -> bool:
    normalized_text = text.lower()
    normalized_alias = alias.lower().strip()
    if not normalized_alias:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(normalized_alias) + r"(?![a-z0-9])"
    return re.search(pattern, normalized_text) is not None


def _unique_matches(pattern: str, text: str, transform=None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for match in re.finditer(pattern, text, flags=re.IGNORECASE):
        value = match.group(0)
        value = transform(value) if transform else value
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def detect_hardware_entities(text: str) -> dict[str, Any]:
    firmware_versions = _unique_matches(
        r"\b(?:firmware|fw|ardupilot|px4|betaflight)?\s*v?\d+(?:\.\d+){1,3}(?:[-+][a-z0-9._-]+)?\b",
        text,
        lambda value: value.strip(),
    )
    error_codes = _unique_matches(
        r"\b(?:ERR|ERROR|E)[-_ ]?[A-Z0-9]{2,8}\b|\b0x[0-9A-F]{2,8}\b",
        text,
        lambda value: re.sub(r"\s+", " ", value.strip()).upper(),
    )
    connector_names = _unique_matches(
        r"\b(?:M[1-9]\d?|AUX[1-9]\d?|SERIAL[1-9]\d?|TELEM[1-9]\d?|JST[- ]?GH|USB[- ]?C)\b",
        text,
        lambda value: value.strip().upper().replace(" ", "-"),
    )
    interfaces = [
        term.upper()
        for term in sorted(INTERFACE_TERMS, key=len, reverse=True)
        if _contains_alias(text, term)
    ]
    return {
        "firmware_versions": firmware_versions,
        "error_codes": error_codes,
        "connectors": connector_names,
        "interfaces": interfaces,
    }


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
    return {"products": matches, **detect_hardware_entities(text)}


def aliases_for_product(store: InMemoryStore, product_id) -> list[ProductAlias]:
    return [alias for alias in store.product_aliases.values() if alias.product_id == product_id]
