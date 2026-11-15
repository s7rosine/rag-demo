from src.rag.rag_pipeline import RagPipeline

class Embedding:
    def encode(self, texts):
        return [[0.1, 0.2] for _ in texts]

class Store:
    def save(self, source, chunks, vectors):
        assert len(chunks) == len(vectors)
        return len(chunks)

class Retriever:
    def search(self, question):
        return [{"text": "RAG retrieves text.", "source": "sample.txt", "chunk": 0}]

class Generator:
    def generate(self, prompt):
        assert "sample.txt" in prompt
        return "RAG retrieves text (sample.txt)."

def test_pipeline():
    rag = RagPipeline(Embedding(), Store(), Retriever(), Generator())
    assert rag.ingest("sample.txt", b"RAG retrieves text.")["chunks_indexed"] == 1
    assert rag.ask("What is RAG?")["sources"][0]["source"] == "sample.txt"
