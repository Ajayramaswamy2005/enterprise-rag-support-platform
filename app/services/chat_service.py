from datetime import datetime
from typing import List
from uuid import UUID, uuid4
from app.models.schemas import ChatRequest, ChatResponse, SourceChunk
from app.graph.state import GraphState
from app.graph.workflow import workflow
from app.retrieval.hybrid import HybridSearch
from app.core.opik_tracker import get_trace_id, update_trace_metadata

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

        sources = [
            SourceChunk(
                chunk_id=r.get("chunk_id", str(r.get("id"))),
                document_id=r.get("document_id", ""),
                title=r.get("title"),
                content=r.get("chunk", ""),
                score=r.get("rerank_score", r.get("rrf_score", r.get("score", 0.0))),
                rank=r.get("rank"),
            )
            for r in final_state.retrieval_results
        ]

        trace_id = get_trace_id()
        update_trace_metadata({
            "conversation_id": str(conversation_id),
            "query_type": final_state.query_type or "unknown",
            "confidence": final_state.confidence,
            "fallback_triggered": final_state.fallback_triggered,
            "retry_count": final_state.retry_count,
        })

        return ChatResponse(
            conversation_id=conversation_id,
            answer=final_state.answer,
            sources=sources,
            confidence=final_state.confidence,
            model=final_state.model or "groq",
            took_ms=elapsed_ms,
        )
