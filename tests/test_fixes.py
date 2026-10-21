import asyncio

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.config import settings
from app.core.auth import get_current_user
from app.graph.nodes import (
    build_answer_messages,
    should_clarify_or_answer,
    should_retry_or_fallback,
)
from app.graph.state import GraphState
from app.retrieval.bm25 import BM25Index


def test_bm25_indexes_single_chunk_payloads():
    # The ingestion path passes one chunk per item; this used to index nothing
    idx = BM25Index()
    idx.from_qdrant_payloads(
        [{"document_id": "d1", "chunk_id": "c1", "title": "Refunds", "metadata": {"category": "billing"}}],
        ["Refunds are processed within 5 business days."],
    )
    results = idx.search("refund processed")
    assert len(results) == 1
    assert results[0]["chunk_id"] == "c1"
    assert results[0]["category"] == "billing"


def test_bm25_reindex_replaces_and_remove_deletes():
    idx = BM25Index()
    payload = [{"document_id": "d1", "chunk_id": "c1", "title": "T"}]
    idx.from_qdrant_payloads(payload, ["password reset link"])
    idx.from_qdrant_payloads(payload, ["password reset link"])
    assert len(idx) == 1
    idx.remove_document("d1")
    assert idx.search("password") == []


def test_bm25_skips_zero_score_chunks():
    idx = BM25Index()
    idx.add_documents([
        {"document_id": "a", "chunks": ["billing invoices"]},
        {"document_id": "b", "chunks": ["shipping times"]},
        {"document_id": "c", "chunks": ["account security"]},
    ])
    assert [r["document_id"] for r in idx.search("invoices")] == ["a"]


def test_answer_prompt_does_not_duplicate_current_question():
    state = GraphState(
        query="How do refunds work?",
        conversation_id="x",
        messages=[
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "How do refunds work?"},
        ],
        context="[1] Refunds: within 5 days",
    )
    msgs = build_answer_messages(state)
    assert sum("How do refunds work?" in m["content"] for m in msgs) == 1
    assert msgs[-1]["content"].startswith("Context:")


def test_routing_empty_retrieval_falls_back_not_clarifies():
    state = GraphState(query="q", conversation_id="x", needs_clarification=True)
    assert should_clarify_or_answer(state) == "fallback"


def test_retry_is_bounded():
    state = GraphState(query="q", conversation_id="x", confidence="low", retry_count=0)
    assert should_retry_or_fallback(state) == "retry"
    state.retry_count = settings.max_retries
    assert should_retry_or_fallback(state) == "fallback"


def test_unsigned_jwt_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_key", "real-key")
    monkeypatch.setattr(settings, "supabase_jwt_secret", None)
    forged = jwt.encode({"sub": "attacker"}, "whatever-secret", algorithm="HS256")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=forged)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_current_user(api_key=None, credentials=creds))
    assert exc.value.status_code == 401


def test_api_key_accepted(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_key", "real-key")
    user = asyncio.run(get_current_user(api_key="real-key", credentials=None))
    assert user.auth_type == "api_key"


def test_backend_api_key_env_alias(monkeypatch):
    from app.config import Settings
    # A local .env (loaded into os.environ by app.config) must not mask the aliases
    for name in ("API_KEY", "GROQ_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BACKEND_API_KEY", "from-render")
    monkeypatch.setenv("MODEL_NAME", "llama-3.3-70b-versatile")
    s = Settings(_env_file=None)
    assert s.api_key == "from-render"
    assert s.groq_model == "llama-3.3-70b-versatile"


def test_qdrant_upsert_is_batched():
    from app.core.qdrant_client import QdrantStore

    class FakeClient:
        def __init__(self):
            self.calls = []

        def upsert(self, collection_name, points):
            self.calls.append(len(points))

    store = QdrantStore()
    store._client = FakeClient()
    store._ready = True
    n = 130
    store.upsert(
        ids=[f"00000000-0000-0000-0000-{i:012d}" for i in range(n)],
        vectors=[[0.0] * 3] * n,
        payloads=[{}] * n,
        batch_size=64,
    )
    assert store._client.calls == [64, 64, 2]


def test_stream_survives_ambiguity_check_failure(monkeypatch):
    import json

    from app.models.schemas import ChatMessage, ChatRequest
    from app.services import chat_service

    def fake_retrieve(state):
        state.retrieval_results = [{"chunk_id": "c1", "chunk": "Refunds take 5 days.", "title": "Refunds", "rerank_score": 4.0}]
        state.context = "[1] Refunds: Refunds take 5 days."
        return state

    def failing_check(state):
        raise RuntimeError("Connection error.")

    class FakeLLM:
        async def chat_stream(self, messages):
            yield "Five days."

    monkeypatch.setattr(chat_service, "classify_query", lambda s: s)
    monkeypatch.setattr(chat_service, "retrieve", fake_retrieve)
    monkeypatch.setattr(chat_service, "check_ambiguity", failing_check)
    monkeypatch.setattr(chat_service, "get_llm", lambda: FakeLLM())

    async def collect():
        req = ChatRequest(messages=[ChatMessage(role="user", content="How long do refunds take?")])
        return [json.loads(e[6:]) async for e in chat_service.ChatService().chat_stream(req)]

    events = asyncio.run(collect())
    types = [e["type"] for e in events]
    assert "error" not in types
    assert next(e for e in events if e["type"] == "meta")["mode"] == "answer"
    assert "".join(e["content"] for e in events if e["type"] == "token") == "Five days."


def test_reindex_only_embeds_chunks_missing_from_qdrant(monkeypatch):
    from types import SimpleNamespace
    from uuid import uuid4

    import app.services.knowledge_service as ks
    from app.retrieval.bm25 import BM25Index

    docs = [
        SimpleNamespace(id=uuid4(), title=f"Doc {i}", content=f"Policy text number {i}.", metadata_={})
        for i in range(3)
    ]

    class FakeQuery:
        def all(self):
            return docs

    class FakeDB:
        def query(self, _model):
            return FakeQuery()

    class FakeStore:
        def __init__(self):
            self.points = {}

        def existing_ids(self, ids):
            return {i for i in ids if i in self.points}

        def upsert(self, ids, vectors, payloads):
            self.points.update(zip(ids, payloads))

        def delete_by_document_id(self, document_id):
            self.points = {k: v for k, v in self.points.items() if v["document_id"] != document_id}

    embedded = []
    monkeypatch.setattr(ks, "embed_text", lambda texts: embedded.extend(texts) or [[0.0]] * len(texts))

    service = ks.KnowledgeService.__new__(ks.KnowledgeService)
    service.db_session = FakeDB()
    service.store = FakeStore()
    service.chunker = ks.Chunker()
    service.bm25 = BM25Index()

    # Pretend the first document was indexed but the other two never reached Qdrant
    first = service._chunks_for(docs[0])
    service.store.upsert([c["chunk_id"] for c in first], None, first)

    result = service.reindex()
    assert result["vectors_written"] == result["chunks"] - len(first)
    assert len(service.store.points) == result["chunks"]
    assert len(service.bm25) == result["chunks"]

    # Nothing missing: no embedding work on the next startup
    embedded.clear()
    assert service.reindex()["vectors_written"] == 0
    assert embedded == []

    # Forced rebuild re-embeds everything
    assert service.reindex(force=True)["vectors_written"] == result["chunks"]
