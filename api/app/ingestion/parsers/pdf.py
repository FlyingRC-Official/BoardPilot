from io import BytesIO


def parse_pdf_text(content: str) -> str:
    return content


def parse_pdf_bytes(content: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(content))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if text:
            return text
    except Exception:
        pass
    return content.decode("utf-8", errors="replace")
