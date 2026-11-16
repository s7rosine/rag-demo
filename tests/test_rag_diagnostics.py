"""Sanitized cloud database diagnostics without revealing credentials."""
from types import SimpleNamespace

import rag_diagnostics


def test_missing_org():
    cfg = SimpleNamespace(mode="production", database_url="postgresql://private/secret")
    assert "RAG_ORG" in rag_diagnostics.rag_status(object(), cfg, "", "default")


def test_missing_url():
    cfg = SimpleNamespace(mode="production", database_url="")
    assert "DATABASE_URL" in rag_diagnostics.rag_status(object(), cfg, "org", "default")


def test_invalid_url_does_not_echo_secret():
    cfg = SimpleNamespace(mode="production", database_url="DATABASE_URL=private-secret")
    result = rag_diagnostics.rag_status(object(), cfg, "org", "default")
    assert "invalid URL format" in result
    assert "private-secret" not in result


def test_connection_failure_does_not_echo_password():
    class Store:
        def connect(self):
            raise RuntimeError("postgresql://user:secretpassword@host")
    cfg = SimpleNamespace(mode="production", database_url="postgresql://user:secretpassword@host")
    result = rag_diagnostics.rag_status(Store(), cfg, "org", "default")
    assert "CONNECTION FAILED" in result
    assert "secretpassword" not in result


def test_database_ready_without_table(monkeypatch):
    class Conn:
        def execute(self, query, args=None):
            if "rag_chunks" in query:
                raise RuntimeError("secret schema error")
            return SimpleNamespace(fetchone=lambda: (1,))
        def close(self):
            pass
    class Store:
        def connect(self):
            return Conn(), "%s", "postgres"
    monkeypatch.setenv("NOTION_API_TOKEN", "never-echo")
    monkeypatch.setenv("NOTION_PAGE_IDS", "page-id")
    cfg = SimpleNamespace(mode="production", database_url="postgresql://private")
    result = rag_diagnostics.rag_status(Store(), cfg, "org", "default")
    assert "Database: CONNECTED" in result
    assert "Index table: MISSING or INACCESSIBLE" in result
    assert "never-echo" not in result


def test_indexed_counts(monkeypatch):
    class Conn:
        def execute(self, query, args=None):
            if "rag_chunks" in query:
                assert args == ("org", "default")
                return SimpleNamespace(fetchone=lambda: (3,))
            return SimpleNamespace(fetchone=lambda: (1,))
        def close(self):
            pass
    class Store:
        def connect(self):
            return Conn(), "%s", "postgres"
    monkeypatch.delenv("LLM_MODEL", raising=False)
    cfg = SimpleNamespace(mode="production", database_url="postgresql://private")
    result = rag_diagnostics.rag_status(Store(), cfg, "org", "default")
    assert "Indexed chunks (default): 3" in result
    assert "Answer model: NOT CONFIGURED" in result

def test_missing_table_sqlstate_is_safe():
    class MissingTableError(Exception):
        sqlstate = "42P01"

    class Conn:
        def execute(self, query, args=None):
            if "rag_chunks" in query:
                raise MissingTableError("postgresql://secret-password@internal")
            return SimpleNamespace(fetchone=lambda: (1,))

        def close(self):
            pass

    class Store:
        def connect(self):
            return Conn(), "%s", "postgres"

    cfg = SimpleNamespace(mode="production", database_url="postgresql://private")
    result = rag_diagnostics.rag_status(Store(), cfg, "org", "default")
    assert "Index table: NOT CREATED" in result
    assert "secret-password" not in result


def test_permission_denied_sqlstate_is_safe():
    class PermissionErrorFromDb(Exception):
        sqlstate = "42501"

    class Conn:
        def execute(self, query, args=None):
            if "rag_chunks" in query:
                raise PermissionErrorFromDb("sensitive database detail")
            return SimpleNamespace(fetchone=lambda: (1,))

        def close(self):
            pass

    class Store:
        def connect(self):
            return Conn(), "%s", "postgres"

    cfg = SimpleNamespace(mode="production", database_url="postgresql://private")
    result = rag_diagnostics.rag_status(Store(), cfg, "org", "default")
    assert "Index table: PERMISSION DENIED" in result
    assert "sensitive database detail" not in result
