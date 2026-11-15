"""Extract text from PDFs, Markdown and plain text."""
from pathlib import Path

def extract_text(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in {".txt", ".md", ".pdf"}:
        raise ValueError("Only PDF, TXT and Markdown are supported")
    if not content:
        raise ValueError("Empty document")
    if ext == ".pdf":
        import fitz
        try:
            with fitz.open(stream=content, filetype="pdf") as document:
                text = "\n".join(page.get_text() for page in document)
        except Exception as exc:
            raise ValueError("PDF could not be read") from exc
    else:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeError as exc:
            raise ValueError("Text must be UTF-8") from exc
    if not text.strip():
        raise ValueError("Document has no extractable text")
    return text
