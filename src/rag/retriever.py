"""Retrieve documents matching a query embedding."""
class Retriever:
    def __init__(self, embedder, store):
        self.embedder, self.store = embedder, store

    def search(self, question: str, top_k=4) -> list[dict]:
        if not question.strip():
            raise ValueError("Question must not be empty")
        return self.store.search(self.embedder.encode([question])[0], top_k)
