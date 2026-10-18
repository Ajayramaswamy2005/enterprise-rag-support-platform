# enterprise-rag-support-platform

A production-grade AI customer support platform powered by Retrieval-Augmented Generation (RAG) for enterprise knowledge bases. It combines hybrid retrieval (BM25 + Dense + RRF + Cross-Encoder Re-ranking), LangGraph orchestration, and Groq LLM inference to deliver fast, grounded, multi-turn support conversations with built-in observability.

Built with **FastAPI**, **LangGraph**, **PostgreSQL**, **Supabase**, **Qdrant**, **Groq**, and **Opik**.

---

## Highlights

- **Hybrid Retrieval** — replaces semantic-only search with BM25 sparse + dense vector retrieval fused via Reciprocal Rank Fusion (RRF), then refined by a Cross-Encoder re-ranker for higher context precision.
- **LangGraph Workflows** — a stateful graph for query classification, retrieval, answer generation, validation, conversational memory, clarification, and graceful fallback across multi-turn interactions.
- **Groq LLM Inference** — fast, low-latency answer generation and validation through Groq-hosted Llama 3.
- **Multi-Store Architecture** — PostgreSQL for document persistence, Qdrant for dense vectors, Supabase for auth/metadata, and an in-memory BM25 index for sparse retrieval.
- **Observability** — Opik traces every request end-to-end across the graph nodes, retrieval, and LLM calls.
- **Production API** — async FastAPI surface with chat, knowledge-base CRUD, and health endpoints, plus auto-generated OpenAPI docs.

---

## Architecture

```
            ┌────────────────┐     ┌──────────────┐
  User ───► │   FastAPI API  │ ──► │  ChatService │
            └────────────────┘     └──────┬───────┘
                                          │
                                          ▼
                            ┌──────────────────────────┐
                            │   LangGraph Workflow     │
                            │  classify → retrieve     │
                            │  → check_ambiguity       │
                            │  → generate → validate   │
                            │  → clarify / fallback    │
                            └─────────────┬────────────┘
                                          │
      ┌───────────────────────────────────┼───────────────────────────┐
      ▼                                   ▼                           ▼
┌───────────┐                      ┌──────────────┐            ┌───────────────┐
│  Groq LLM │                      │ Hybrid Search│            │     Opik      │
│ classify, │                      │  BM25 + Dense│            │  tracing     │
│ answer,   │                      │  + RRF       │            │              │
│ validate  │                      │  + Reranker  │            └───────────────┘
└───────────┘                      └──────┬───────┘
                                          │
                            ┌─────────────┼─────────────┐
                            ▼             ▼             ▼
                      ┌─────────┐   ┌──────────┐  ┌──────────┐
                      │ Qdrant  │   │ PostgreSQL│ │ Supabase │
                      │ vectors │   │ documents │ │ auth/usr │
                      └─────────┘   └──────────┘  └──────────┘
```

### LangGraph Pipeline

1. **classify** — labels the query (`support`, `billing`, `technical`, `general`, `escalate`) to drive retrieval filters.
2. **retrieve** — runs hybrid search and cross-encoder re-ranking to surface the most relevant chunks.
3. **check_ambiguity** — decides whether the query needs clarification before answering.
4. **generate** — produces a grounded answer using the context plus recent conversational memory.
5. **validate** — a judge step verifies the answer is supported by the retrieved context; low-confidence answers retry retrieval, then fall back to a human-escalation message.
6. **clarify / fallback** — terminal branches for ambiguous queries or when the knowledge base is insufficient.

### Hybrid Retrieval (RRF)

Sparse (BM25) and dense (Qdrant cosine) results are fused with Reciprocal Rank Fusion:

```
score(d) = w_dense / (k + rank_dense(d))  +  w_sparse / (k + rank_sparse(d))
```

The fused candidates are then refined by a Cross-Encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`), which jointly encodes the query and each chunk to produce a relevance score with higher precision than dot-product similarity alone.

---

## Tech Stack

| Component          | Technology                                             |
| ------------------ | ------------------------------------------------------ |
| API framework      | FastAPI + Uvicorn                                      |
| Workflow engine    | LangGraph                                              |
| Primary database   | PostgreSQL (SQLAlchemy ORM)                            |
| Auth / metadata    | Supabase                                               |
| Vector store       | Qdrant                                                 |
| Sparse retrieval   | rank-bm25                                              |
| Embeddings         | sentence-transformers (`all-MiniLM-L6-v2`)            |
| Re-ranker          | sentence-transformers Cross-Encoder                    |
| LLM inference      | Groq (Llama 3)                                         |
| Observability      | Opik                                                   |

---

## Project Structure

```
app/
  main.py                 FastAPI entry point & lifespan
  config.py               Pydantic settings
  models/
    schemas.py            Pydantic request/response models
    database.py           SQLAlchemy models & session
  core/
    groq_client.py        Groq LLM wrapper
    qdrant_client.py      Qdrant vector store
    supabase_client.py    Supabase client
    embeddings.py         Embedding utilities
    opik_tracker.py        Opik observability
  retrieval/
    chunker.py            Document chunking
    bm25.py               BM25 sparse index
    dense.py              Dense vector retrieval
    hybrid.py             RRF fusion
    reranker.py           Cross-Encoder re-ranking
  graph/
    state.py              LangGraph state
    nodes.py              Workflow nodes
    workflow.py           Compiled graph
  services/
    chat_service.py       Chat orchestration
    knowledge_service.py  Knowledge-base CRUD & indexing
  api/routes/
    chat.py               /chat endpoints
    knowledge.py          /knowledge endpoints
    health.py             /health endpoint
tests/                    pytest test suite
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL
- Qdrant (local or cloud)
- A Groq API key

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env with your credentials (GROQ_API_KEY, POSTGRES_URL, QDRANT_URL, etc.)
```

### 2. Install dependencies

```bash
python -m venv .venv
.\.venv\Scripts\activate        # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements-dev.txt   # runtime deps + pytest
```

### 3. Run the server

```bash
uvicorn app.main:app --reload
```

The API and interactive docs are available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health: `http://localhost:8000/health`

---

## API Reference

### Health

```
GET /health          → service & dependency status
```

### Chat

```http
POST /chat
Content-Type: application/json

{
  "messages": [
    { "role": "user", "content": "How do I reset my password?" }
  ]
}
```

Response:

```json
{
  "conversation_id": "uuid",
  "answer": "You can reset your password via the forgot password link...",
  "sources": [
    {
      "chunk_id": "doc-uuid-0",
      "document_id": "doc-uuid",
      "title": "Password reset",
      "content": "Use the forgot password link...",
      "score": 0.94,
      "rank": 1
    }
  ],
  "confidence": "high",
  "model": "llama3-70b-8192",
  "took_ms": 1840
}
```

### Knowledge Base

```http
POST   /knowledge/documents        # create & index a document
GET    /knowledge/documents         # list documents
GET    /knowledge/documents/{id}    # get a document
PUT    /knowledge/documents/{id}    # update & re-index a document
DELETE /knowledge/documents/{id}    # delete a document
POST   /knowledge/warm              # rebuild the in-memory BM25 index
```

Example ingestion:

```bash
curl -X POST http://localhost:8000/knowledge/documents \
  -H "Content-Type: application/json" \
  -d '{
        "title": "Password reset policy",
        "content": "Users can reset their password via the forgot password link on the login page. Reset emails expire after 15 minutes.",
        "metadata": { "category": "technical" }
      }'
```

---

## Configuration

All settings are read from environment variables (via `.env`). Key options:

| Variable              | Description                              | Default                                  |
| --------------------- | ---------------------------------------- | ---------------------------------------- |
| `GROQ_API_KEY`        | Groq API key                             | —                                        |
| `GROQ_MODEL`          | Groq model name                          | `llama3-70b-8192`                        |
| `POSTGRES_URL`        | PostgreSQL connection URL                | `postgresql://...`                       |
| `QDRANT_URL`          | Qdrant instance URL                      | `http://localhost:6333`                  |
| `QDRANT_COLLECTION`   | Qdrant collection name                   | `knowledge_base`                         |
| `EMBEDDING_MODEL`     | Sentence-transformers embedding model    | `all-MiniLM-L6-v2`                       |
| `RERANKER_MODEL`      | Cross-encoder re-ranker model            | `cross-encoder/ms-marco-MiniLM-L-6-v2`  |
| `RERANKER_TOP_K`      | Chunks returned after re-ranking          | `5`                                      |
| `RRF_K`               | RRF smoothing constant                    | `60`                                     |
| `RETRIEVAL_TOP_K`     | Candidates fetched before re-ranking      | `20`                                     |
| `HYBRID_DENSE_WEIGHT` | Dense contribution weight                | `0.5`                                    |
| `HYBRID_SPARSE_WEIGHT`| Sparse contribution weight               | `0.5`                                    |
| `MAX_RETRIES`         | Retrieval retries on low confidence      | `3`                                      |
| `OPIK_API_KEY`        | Opik API key (optional)                  | —                                        |

See `.env.example` for the full list.

---

## Testing

```bash
pytest tests/ -v
```

The suite covers the FastAPI endpoints, the chunker, BM25 ranking, and RRF fusion logic.

---

## Deployment & CI/CD

Both services deploy to Render from `render.yaml` (Blueprint), and GitHub Actions gates every deploy:

1. You push to `main` (or open a PR).
2. `.github/workflows/ci.yml` runs the backend tests and the frontend typecheck + production build.
3. Render waits for those checks (`autoDeployTrigger: checksPass`) and then redeploys only the service that changed: backend on `app/**`, `Dockerfile`, or `requirements.txt`; frontend on `frontend/**`.

If CI fails, nothing deploys and the live site keeps running the last good version.

Required environment variables on Render: `GROQ_API_KEY`, `POSTGRES_URL`, `QDRANT_URL`, `QDRANT_API_KEY` (backend), and `POSTGRES_URL` (frontend). `BACKEND_API_KEY` is generated by Render and shared automatically; `BACKEND_API_URL` points at the backend's public `onrender.com` URL.

---

## Observability

When `OPIK_API_KEY` (or a local `OPIK_URL`) is configured, every chat request is traced end-to-end across the LangGraph nodes, retrieval steps, and Groq LLM calls. Trace metadata includes the conversation id, query classification, confidence, retry count, and whether a fallback was triggered.

---

## Design Decisions

- **Why hybrid over semantic-only?** Dense retrieval captures semantic similarity but misses exact keyword/ID matches. BM25 handles those well; fusing both with RRF captures the strengths of each, and the cross-encoder re-ranker then orders the fused set by true query-document relevance.
- **Why LangGraph?** It makes the multi-step flow (classify → retrieve → validate → fallback) explicit, stateful, and easy to extend with new nodes or conditional edges.
- **Why lazy clients?** Module-level services connect only on first use, so the app imports cleanly without running infrastructure and tests run offline.

---

## License

This project is released under the MIT License.