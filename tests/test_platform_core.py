import pytest
from platform_core import Settings, Repository, extract, split_text

def test_txt_and_json():
    assert extract("a.txt", b"hello") == "hello"
    assert "hello" in extract("a.json", b'{"x":"hello"}')

def test_html():
    assert "hello" in extract("a.html", b"<p>hello</p>")

def test_empty_rejected():
    with pytest.raises(ValueError):
        extract("x.txt", b"")

def test_scanned_pdf_is_not_claimed_as_ocr():
    with pytest.raises(ValueError):
        extract("x.jpg", b"fake")

def test_chunking():
    assert len(split_text("hello " * 100, 100, 10)) > 1

def test_local_persistence_and_org_isolation(tmp_path):
    path = str(tmp_path / "rag.db")
    repo = Repository(Settings(database_url="", sqlite_path=path, mode="local"))
    repo.ingest("orgA", "knowledge", "a.txt", b"Patient tracking uses BLE.")
    assert repo.search("orgA", "knowledge", "BLE")
    assert repo.search("orgB", "knowledge", "BLE") == []
    assert repo.list_kbs("orgB") == []
    other = Repository(Settings(database_url="", sqlite_path=path, mode="local"))
    assert other.search("orgA", "knowledge", "BLE")

def test_production_without_database_fails(tmp_path):
    repo = Repository(Settings(database_url="", sqlite_path=str(tmp_path / "x.db"), mode="production"))
    with pytest.raises(RuntimeError):
        repo.initialize()
