"""FastAPI application for indexing and querying documents."""
import logging
import os
from functools import lru_cache
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel, Field
from src.rag.embedder import Embedder
from src.rag.vector_store import VectorStore
from src.rag.retriever import Retriever
from src.rag.generator import Generator
from src.rag.rag_pipeline import RagPipeline

logger = logging.getLogger(__name__)
app = FastAPI(title="RAG Demo")

class Question(BaseModel):
    question: str = Field(min_length=1)

@lru_cache
def get_pipeline():
    embedder = Embedder()
    store = VectorStore(os.getenv("CHROMA_PATH", "./storage/chroma"))
    return RagPipeline(embedder, store, Retriever(embedder, store),
                       Generator(os.getenv("OLLAMA_URL", "http://localhost:11434")))

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    try:
        content = await file.read(10 * 1024 * 1024 + 1)
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(413, "File exceeds 10 MB limit")
        return get_pipeline().ingest(file.filename or "unknown", content)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Document ingestion failed")
        raise HTTPException(503, "Ingestion unavailable; see application logs") from exc
    finally:
        await file.close()

@app.post("/query")
def query(payload: Question):
    try:
        return get_pipeline().ask(payload.question)
    except Exception as exc:
        logger.exception("Question answering failed")
        raise HTTPException(503, "Query unavailable; see application logs") from exc
