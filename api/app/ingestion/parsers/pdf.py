from io import BytesIO


def parse_pdf_text(content: str) -> str:
    return content


def parse_pdf_bytes(content: bytes) -> str:
    looks_like_pdf = content.lstrip().startswith(b"%PDF")
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(content))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if text:
            return text
        if looks_like_pdf:
            raise ValueError("PDF did not contain extractable text")
    except Exception as exc:
        if looks_like_pdf:
            raise ValueError(f"PDF text extraction failed: {exc}") from exc
    return content.decode("utf-8", errors="replace")
