import csv
from io import StringIO
from typing import Optional

QUESTION_FIELDS = {"question", "q", "question_text", "prompt", "issue", "title", "subject"}
ANSWER_FIELDS = {"answer", "a", "answer_text", "response", "resolution", "body", "content"}
NOTE_FIELDS = {"tags", "tag", "category", "product", "source", "status"}


def normalize_field(value: str) -> str:
    return value.strip().lstrip("\ufeff").lower().replace(" ", "_").replace("-", "_")


def clean_cell(value: Optional[str]) -> str:
    return (value or "").strip()


def row_to_block(question: str, answer: str, notes: list[str]) -> str:
    lines = []
    if question:
        lines.append(f"Question: {question}")
    if answer:
        lines.append(f"Answer: {answer}")
    lines.extend(notes)
    return "\n".join(lines)


def parse_csv_faq(content: str) -> str:
    reader = csv.reader(StringIO(content))
    raw_rows = [[clean_cell(cell) for cell in row] for row in reader]
    raw_rows = [row for row in raw_rows if any(row)]
    if not raw_rows:
        return content

    headers = [normalize_field(cell) for cell in raw_rows[0]]
    has_header = bool(set(headers) & (QUESTION_FIELDS | ANSWER_FIELDS))
    if not has_header:
        blocks = []
        for row in raw_rows:
            question = row[0] if len(row) > 0 else ""
            answer = row[1] if len(row) > 1 else ""
            notes = [f"Context: {cell}" for cell in row[2:] if cell]
            if question or answer:
                blocks.append(row_to_block(question, answer, notes))
        return "\n\n".join(blocks) if blocks else content

    rows = csv.DictReader(StringIO(content), fieldnames=headers)
    next(rows, None)
    blocks = []
    for row in rows:
        normalized = {normalize_field(key): clean_cell(value) for key, value in row.items() if key is not None}
        question = next((normalized[field] for field in QUESTION_FIELDS if normalized.get(field)), "")
        answer = next((normalized[field] for field in ANSWER_FIELDS if normalized.get(field)), "")
        notes = [f"{field.replace('_', ' ').title()}: {normalized[field]}" for field in NOTE_FIELDS if normalized.get(field)]
        if question or answer:
            blocks.append(row_to_block(question, answer, notes))
    return "\n\n".join(blocks) if blocks else content
