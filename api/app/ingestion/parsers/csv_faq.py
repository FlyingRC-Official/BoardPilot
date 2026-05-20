import csv
from io import StringIO


def parse_csv_faq(content: str) -> str:
    rows = csv.DictReader(StringIO(content))
    blocks = []
    for row in rows:
        question = row.get("question") or row.get("q") or row.get("Question") or ""
        answer = row.get("answer") or row.get("a") or row.get("Answer") or ""
        if question or answer:
            blocks.append(f"Question: {question}\nAnswer: {answer}")
    return "\n\n".join(blocks) if blocks else content

