import pytest
from src.rag.ingestor import extract_text

def test_txt():
    assert extract_text("sample.txt", b"Hello") == "Hello"

def test_markdown():
    assert extract_text("sample.md", b"# Title") == "# Title"

def test_unsupported():
    with pytest.raises(ValueError):
        extract_text("sample.exe", b"data")
