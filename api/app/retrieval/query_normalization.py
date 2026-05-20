import re


def normalize_query(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).lower()

