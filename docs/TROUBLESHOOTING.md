# Troubleshooting

| Symptom | Check | Action |
|---|---|---|
| UI unavailable | `docker compose ps` | `docker compose logs ui` |
| API unavailable | `curl http://localhost:8000/health` | `docker compose logs api` |
| Ollama error | `docker compose exec ollama ollama list` | `docker compose exec ollama ollama pull llama3.2:1b` |
| Ingestion fails | `docker compose logs api` | Use UTF-8 TXT, MD or readable PDF under 10 MB |
| No search results | Check ingestion response | Upload the source document again |
| Slow first query | Check logs and disk | Wait for initial model download and embedding initialization |
| CI failure | GitHub Actions job log | Run `ruff check src api.py app.py tests` and `pytest -q` |

Full instructions are in [the runbook](RAG_OPERATIONS_RUNBOOK.md).
