"""Persistent vector storage using ChromaDB."""
import hashlib
import chromadb

class VectorStore:
    def __init__(self, path="./storage/chroma"):
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection("rag_demo")

    def save(self, source: str, chunks: list[str], vectors: list[list[float]]) -> int:
        if len(chunks) != len(vectors):
            raise ValueError("Chunks and vectors length mismatch")
        previous = self.collection.get(where={"source": source})
        if previous["ids"]:
            self.collection.delete(ids=previous["ids"])
        if chunks:
            ids = [hashlib.sha256(f"{source}:{i}".encode()).hexdigest() for i in range(len(chunks))]
            self.collection.upsert(
                ids=ids, documents=chunks, embeddings=vectors,
                metadatas=[{"source": source, "chunk": i} for i in range(len(chunks))],
            )
        return len(chunks)

    def search(self, vector: list[float], top_k=4) -> list[dict]:
        count = self.collection.count()
        if count == 0:
            return []
        result = self.collection.query(
            query_embeddings=[vector], n_results=min(count, top_k),
            include=["documents", "metadatas", "distances"],
        )
        return [{"text": text, "source": meta["source"], "chunk": meta["chunk"],
                 "distance": dist} for text, meta, dist in zip(
                     result["documents"][0], result["metadatas"][0], result["distances"][0])]
