import json
import logging
import time
from typing import AsyncIterator, List
from uuid import uuid4

import anyio
from app.config import settings
from app.models.schemas import ChatRequest, ChatResponse, SourceChunk
from app.graph.state import GraphState
from app.graph.workflow import workflow
from app.core.opik_tracker import traced, update_trace_metadata
from app.graph.nodes import (
    classify_query,
    retrieve,
    check_ambiguity,
    build_answer_messages,
    build_clarification_messages,
    build_fallback_messages,
    get_llm,
)

logger = logging.getLogger(__name__)

# ms-marco cross-encoder logits: > 3 is a strong match, > 0 a plausible one
HIGH_RERANK_SCORE = 3.0

def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"

def _to_sources(results: List[dict]) -> List[SourceChunk]:
    return [
        SourceChunk(
            chunk_id=str(r.get("chunk_id") or r.get("id")),
            document_id=str(r.get("document_id") or ""),
            title=r.get("title"),
            content=r.get("chunk", ""),
            score=float(r.get("rerank_score", r.get("rrf_score", r.get("score", 0.0)))),
            rank=i + 1,
        )
        for i, r in enumerate(results)
    ]

def _retrieval_confidence(results: List[dict]) -> str:
    """Streaming skips the post-hoc validation pass, so estimate confidence from retrieval quality."""
    if not results:
        return "fallback"
    top = float(results[0].get("rerank_score", 0.0))
    if top >= HIGH_RERANK_SCORE and len(results) >= 2:
        return "high"
    if top > 0:
        return "medium"
    return "low"

def _initial_state(request: ChatRequest) -> tuple[GraphState, str]:
    user_messages = [m for m in request.messages if m.role == "user"]
    query = user_messages[-1].content if user_messages else request.messages[-1].content
    conversation_id = str(request.conversation_id or uuid4())
    state = GraphState(
        query=query,
        conversation_id=conversation_id,
        messages=[{"role": m.role, "content": m.content} for m in request.messages],
    )
    return state, conversation_id

class ChatService:
    def __init__(self):
        self.workflow = workflow

    @traced("chat")
    def chat(self, request: ChatRequest) -> ChatResponse:
        state, conversation_id = _initial_state(request)

        start = time.perf_counter()
        final_state = self.workflow.invoke(state)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        get = final_state.get if isinstance(final_state, dict) else (lambda k: getattr(final_state, k, None))
        retrieval_results = get("retrieval_results") or []
        confidence = get("confidence") or "medium"

        update_trace_metadata({
            "conversation_id": conversation_id,
            "query_type": get("query_type") or "unknown",
            "confidence": confidence,
            "fallback_triggered": bool(get("fallback_triggered")),
            "retry_count": get("retry_count") or 0,
        })

        return ChatResponse(
            conversation_id=conversation_id,
            answer=get("answer") or "",
            sources=_to_sources(retrieval_results),
            confidence=confidence,
            model=get("model") or "groq",
            took_ms=elapsed_ms,
        )

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Server-sent events: stage* -> meta -> token* -> done (or error)."""
        state, conversation_id = _initial_state(request)
        start = time.perf_counter()

        # Classification, retrieval, and re-ranking are blocking (LLM calls and
        # model inference), so run them off the event loop.
        steps = [("classify", classify_query), ("retrieve", retrieve), ("check_ambiguity", check_ambiguity)]
        for name, step in steps:
            yield _sse({"type": "stage", "stage": name})
            try:
                state = await anyio.to_thread.run_sync(step, state)
            except Exception as e:
                logger.warning("Stream step %s failed: %s", name, e)
                if name == "classify":
                    # Retrieval works without a label
                    continue
                if name == "check_ambiguity":
                    # The clarity check is advisory: assume the question is clear
                    # rather than discarding retrieved context over a transient LLM error
                    state.needs_clarification = False
                    continue
                yield _sse({"type": "error", "error": f"{name} failed: {e}"})
                yield _sse({"type": "done", "took_ms": int((time.perf_counter() - start) * 1000)})
                return

        results = state.retrieval_results or []
        if not results:
            mode, messages = "fallback", build_fallback_messages(state)
        elif state.needs_clarification:
            mode, messages = "clarify", build_clarification_messages(state)
        else:
            mode, messages = "answer", build_answer_messages(state)

        yield _sse({
            "type": "meta",
            "conversation_id": conversation_id,
            "sources": [s.model_dump() for s in _to_sources(results)],
            "query_type": state.query_type or "general",
            "needs_clarification": state.needs_clarification,
            "mode": mode,
            "confidence": "low" if mode == "clarify" else _retrieval_confidence(results),
            "model": settings.groq_model,
        })
        yield _sse({"type": "stage", "stage": "generate"})

        try:
            async for token in get_llm().chat_stream(messages):
                yield _sse({"type": "token", "content": token})
        except Exception as e:
            yield _sse({"type": "error", "error": str(e)})

        yield _sse({"type": "done", "took_ms": int((time.perf_counter() - start) * 1000)})
