import json
from datetime import datetime
from typing import List, AsyncIterator
from uuid import UUID, uuid4
from app.models.schemas import ChatRequest, ChatResponse, SourceChunk
from app.graph.state import GraphState
from app.graph.workflow import workflow
from app.retrieval.hybrid import HybridSearch
from app.core.opik_tracker import get_trace_id, update_trace_metadata
from app.graph.nodes import (
    classify_query,
    retrieve,
    check_ambiguity,
    SYSTEM_PROMPT,
    CLARIFICATION_PROMPT,
    get_llm,
)

class ChatService:
    def __init__(self):
        self.workflow = workflow
        self.hybrid = HybridSearch()

    def chat(self, request: ChatRequest) -> ChatResponse:
        # Use the latest user message as the working query
        user_messages = [m for m in request.messages if m.role == "user"]
        query = user_messages[-1].content if user_messages else request.messages[-1].content

        conversation_id = request.conversation_id or uuid4()
        state = GraphState(
            query=query,
            conversation_id=str(conversation_id),
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
        )

        start = datetime.utcnow()
        final_state = self.workflow.invoke(state)
        elapsed_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

        if isinstance(final_state, dict):
            retrieval_results = final_state.get("retrieval_results") or []
            query_type = final_state.get("query_type") or "unknown"
            confidence = final_state.get("confidence") or "medium"
            fallback_triggered = final_state.get("fallback_triggered") or False
            retry_count = final_state.get("retry_count") or 0
            answer = final_state.get("answer") or ""
            model = final_state.get("model") or "groq"
        else:
            retrieval_results = getattr(final_state, "retrieval_results", None) or []
            query_type = getattr(final_state, "query_type", None) or "unknown"
            confidence = getattr(final_state, "confidence", "medium")
            fallback_triggered = getattr(final_state, "fallback_triggered", False)
            retry_count = getattr(final_state, "retry_count", 0)
            answer = getattr(final_state, "answer", "")
            model = getattr(final_state, "model", "groq")

        sources = [
            SourceChunk(
                chunk_id=r.get("chunk_id", str(r.get("id"))),
                document_id=r.get("document_id", ""),
                title=r.get("title"),
                content=r.get("chunk", ""),
                score=r.get("rerank_score", r.get("rrf_score", r.get("score", 0.0))),
                rank=r.get("rank"),
            )
            for r in retrieval_results
        ]

        trace_id = get_trace_id()
        update_trace_metadata({
            "conversation_id": str(conversation_id),
            "query_type": query_type,
            "confidence": confidence,
            "fallback_triggered": fallback_triggered,
            "retry_count": retry_count,
        })

        return ChatResponse(
            conversation_id=conversation_id,
            answer=answer,
            sources=sources,
            confidence=confidence,
            model=model,
            took_ms=elapsed_ms,
        )

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        user_messages = [m for m in request.messages if m.role == "user"]
        query = user_messages[-1].content if user_messages else request.messages[-1].content

        conversation_id = request.conversation_id or uuid4()
        state = GraphState(
            query=query,
            conversation_id=str(conversation_id),
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
        )

        try:
            state = classify_query(state)
            state = retrieve(state)
            state = check_ambiguity(state)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Preliminary graph processing warning: %s", e)

        sources = [
            SourceChunk(
                chunk_id=r.get("chunk_id", str(r.get("id"))),
                document_id=r.get("document_id", ""),
                title=r.get("title"),
                content=r.get("chunk", ""),
                score=r.get("rerank_score", r.get("rrf_score", r.get("score", 0.0))),
                rank=r.get("rank"),
            )
            for r in (state.retrieval_results or [])
        ]

        init_payload = {
            "type": "meta",
            "conversation_id": str(conversation_id),
            "sources": [s.model_dump() for s in sources],
            "query_type": state.query_type or "general",
            "needs_clarification": state.needs_clarification,
        }
        yield f"data: {json.dumps(init_payload)}\n\n"

        llm = get_llm()
        if state.needs_clarification:
            messages = [
                {"role": "system", "content": CLARIFICATION_PROMPT},
                {"role": "user", "content": state.query},
            ]
        else:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            for msg in state.messages[-6:]:
                messages.append({"role": msg["role"], "content": msg["content"]})
            user_prompt = (
                f"Context:\n{state.context}\n\n"
                f"User question: {state.query}\n\n"
                "Provide a helpful answer based on the context above."
            )
            messages.append({"role": "user", "content": user_prompt})

        try:
            async for token in llm.chat_stream(messages):
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"
