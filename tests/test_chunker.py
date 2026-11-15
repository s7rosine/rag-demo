import pytest
from src.rag.chunker import chunk_text

def test_overlap():
    assert chunk_text("abcdefghij", 6, 2) == ["abcdef", "efghij", "ij"]

def test_empty():
    assert chunk_text("  ") == []

def test_invalid():
    with pytest.raises(ValueError):
        chunk_text("hello", 5, 5)
