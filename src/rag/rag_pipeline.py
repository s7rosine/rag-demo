"""Orchestrate document indexing and grounded answers."""
from .chunker import chunk_text
from .ingestor import extract_text
from .prompt_builder import build_prompt

class RagPipeline:
    def __init__(self, embedder, store, retriever, generator):
        self.embedder, self.store = embedder, store
        self.retriever, self.generator = retriever, generator

    def ingest(self, filename: str, content: bytes) -> dict:
        chunks = chunk_text(extract_text(filename, content))
        vectors = self.embedder.encode(chunks)
        return {"source": filename, "chunks_indexed": self.store.save(filename, chunks, vectors)}

    def ask(self, question: str) -> dict:
        matches = self.retriever.search(question)
        if not matches:
            return {"answer": "No indexed documents available.", "sources": []}
        answer = self.generator.generate(build_prompt(question, matches))
        return {"answer": answer, "sources": [
            {"source": item["source"], "chunk": item["chunk"]} for item in matches]}
