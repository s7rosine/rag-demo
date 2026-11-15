"""Overlapping character chunking."""
def chunk_text(text: str, size: int = 700, overlap: int = 100) -> list[str]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Require size > overlap >= 0")
    text = text.strip()
    if not text:
        return []
    return [text[i:i + size] for i in range(0, len(text), size - overlap)
            if text[i:i + size].strip()]
