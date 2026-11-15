# RAG Demo — DevOps / SRE Operations Runbook

## System purpose and architecture

This learning app answers questions about uploaded documents. FastAPI receives requests, Streamlit supplies the UI, ChromaDB persists vectors, and Ollama generates answers using retrieved text. Indexing runs ingestor -> chunker -> embedder -> ChromaDB; querying runs question -> retriever -> prompt builder -> Ollama -> answer and source references. See [architecture](ARCHITECTURE.md).

## Prerequisites

Install Git and Docker with Compose, then verify each tool:

```bash
git --version
docker --version
docker compose version
```

Expected: each command displays a version. Docker must be running. Downloading the embedding and Ollama models requires network access and sufficient disk space/RAM. Alternatively install Python 3.11+ and Ollama to run locally without Docker.

## Startup

```bash
git clone https://github.com/s7rosine/rag-demo.git
cd rag-demo
docker compose up --build -d
docker compose exec ollama ollama pull llama3.2:1b
docker compose ps
curl http://localhost:8000/health
```

`up --build -d` builds images and starts containers in the background. `exec ollama` runs a command inside the Ollama container; `pull` downloads the local LLM. `ps` reports container status. The API health response should contain `"status":"ok"`. Open http://localhost:8501 for the UI; http://localhost:8000/docs for the API docs. **Health does not verify the LLM or vector database.**

## Ingest a sample file

```bash
curl -F "file=@data/sample.txt" http://localhost:8000/ingest
```

Expected: JSON reporting `source` and `chunks_indexed` greater than zero. The first ingestion may download the Sentence Transformers model. To index a different document, select it in the web UI and click **Index document**.

## Query a sample

```bash
curl -H "Content-Type: application/json" -d '{"question":"What are the indexing steps?"}' http://localhost:8000/query
```

Expected: JSON containing `answer` and `sources`. If Ollama cannot generate, check whether its model was pulled and inspect API/Ollama logs. Answers should be reviewed against the retrieved documents.

## Routine service operations

```bash
docker compose ps
docker compose logs --tail=100 api
docker compose logs --tail=100 ui
docker compose logs --tail=100 ollama
docker compose restart api
docker compose down
```

`logs --tail=100` shows recent output; `restart api` restarts the API; `down` stops and removes containers but preserves named volumes. **Do not run `docker compose down -v` unless intentionally deleting stored vectors and models.**

## Troubleshooting

| Symptom | Diagnostic | Suggested resolution | Verification |
|---|---|---|---|
| API down | `docker compose logs api` | Correct startup issue, restart API | `curl http://localhost:8000/health` |
| UI down | `docker compose logs ui` | Resolve UI process error | Browse localhost:8501 |
| Ollama unavailable | `docker compose logs ollama` | Start Ollama and download model | `docker compose exec ollama ollama list` |
| No answers | Review query response and logs | Re-ingest and check model | Query sample question |
| Unsupported file | Inspect API 400 response | Use PDF, TXT or MD | Retry upload |
| Poor answers | Examine uploaded text | Try a clearer document/question | Review source references |
| CI failure | GitHub Actions logs | Run lint/tests locally | Green CI run |
| Ports taken | `docker compose ps` | Stop conflicting process or change host mapping | Open health/UI URL |
| Disk full | `docker system df` | Free safe-to-delete unused resources | Retry after free space check |

## Backup and restore

ChromaDB and downloaded embedding model cache use the named Compose volume `rag_storage`; Ollama uses `ollama_data`. Keep a separate, secure copy of original documents, because recovery by re-indexing requires them. For a consistent backup, stop application writes before copying the volume. Never delete the volume while backup is pending. The application has no automated backup or restore scripts; implement and test a volume snapshot procedure appropriate to your host before relying on this system for important data.

## CI/CD, deployment and rollback

GitHub Actions runs linting, mocked unit tests and a Docker build on pushes/PRs. Review failures under the repository's **Actions** tab. Locally run `pip install -r requirements-dev.txt`, `ruff check src api.py app.py tests`, then `pytest -q`. Deployment is manual: `git pull` and `docker compose up --build -d`. For rollback, select a previously tested Git commit and rebuild only after backing up data. This demonstration has no automatic production deployment.

## Security

This is a localhost learning service without user authentication. Never expose ports publicly or upload confidential files. Keep credentials out of Git; use `.env` locally and exclude it from commits. Retrieved document text may contain malicious instructions; the prompt builder explicitly treats text as data, but no model behavior can be guaranteed. Apply and test dependency updates regularly.

## Incident response

1. Identify symptom and time; inspect `docker compose ps`.
2. Check `/health` and relevant container logs.
3. Determine user impact and whether data indexing is affected.
4. Preserve logs and backups before changing persistent storage.
5. Apply a scoped fix or restart; avoid deleting volumes.
6. Verify sample ingestion/query and record results.
7. Escalate unresolved problems and document cause, recovery and prevention.

Incident note template: **When / Symptom / Impact / Logs / Actions / Verification / Follow-up owner**.

## Operational checklists

**Daily:** Check API health and logs; run a simple question; verify adequate disk space.

**Weekly:** Review CI checks, test ingestion, verify a backup exists, and inspect repeated errors.

**Monthly:** Review dependencies and resource usage; test a safe restoration or re-indexing procedure; update documentation.

## Limitations

Prometheus metrics, Grafana, authenticated access, backup automation, transactional re-indexing and production resilience are future enhancements—not implemented features. Commands in this runbook require an actual local Docker/Compose environment to validate.
