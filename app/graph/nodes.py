from typing import Dict, List
from app.config import settings
from app.core.groq_client import GroqLLM
from app.core.embeddings import embed_text
from app.retrieval.hybrid import HybridSearch
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.chunker import Chunker
from app.graph.state import GraphState

_llm: GroqLLM | None = None
_hybrid: HybridSearch | None = None
_reranker: CrossEncoderReranker | None = None
chunker = Chunker()

def get_llm() -> GroqLLM:
    global _llm
    if _llm is None:
        _llm = GroqLLM()
    return _llm

def get_hybrid() -> HybridSearch:
    global _hybrid
    if _hybrid is None:
        _hybrid = HybridSearch()
    return _hybrid

def get_reranker() -> CrossEncoderReranker:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoderReranker()
    return _reranker

CLASSIFICATION_LABELS = ["support", "billing", "technical", "general", "escalate"]

SYSTEM_PROMPT = """You are a helpful enterprise customer support assistant.
Answer based ONLY on the provided context. If the context does not contain enough information, say so honestly and offer to escalate.
Cite sources when possible. Be concise, professional, and accurate."""

CLARIFICATION_PROMPT = """The user's query is ambiguous or missing critical details.
Ask a short, clear follow-up question to gather the information needed to answer accurately."""

FALLBACK_PROMPT = """I couldn't find a reliable answer in our knowledge base.
Please provide a brief, empathetic response that offers to connect the user with a human support agent or asks for clarification."""

VALIDATION_PROMPT = """You are a quality reviewer.
Given the user question, retrieved context, and the proposed answer, determine if the answer is accurate and supported by the context.
Respond only Yes or No."""


def classify_query(state: GraphState) -> GraphState:
    prompt = f"Classify this customer support query into one category: {', '.join(CLASSIFICATION_LABELS)}.\n\nQuery: {state.query}"
    state.query_type = get_llm().classify(prompt, CLASSIFICATION_LABELS)
    return state


def retrieve(state: GraphState) -> GraphState:
    # Build filters from query classification if it maps to metadata
    filters = None
    if state.query_type:
        filters = {"category": state.query_type}

    candidates = get_hybrid().search(state.query, top_k=settings.retrieval_top_k, filters=filters)
    if not candidates:
        # Try without filters as fallback
        candidates = get_hybrid().search(state.query, top_k=settings.retrieval_top_k)

    reranked = get_reranker().rerank(state.query, candidates, top_k=settings.reranker_top_k)
    state.retrieval_results = reranked
    state.context = "\n\n---\n\n".join(
        f"Source {i+1} ({r.get('title', 'Unknown')}):\n{r['chunk']}"
        for i, r in enumerate(reranked)
    )
    return state


def check_ambiguity(state: GraphState) -> GraphState:
    if not state.retrieval_results:
        state.needs_clarification = True
        return state

    prompt = (
        f"User question: {state.query}\n\n"
        "Is this question clear enough to answer with a knowledge base, or does it need clarification? "
        "Respond only Yes if it is clear, or No if clarification is needed."
    )
    state.needs_clarification = not get_llm().judge_yes_no(prompt)
    return state


def generate_answer(state: GraphState) -> GraphState:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    # Add recent conversation memory
    for msg in state.messages[-6:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    user_prompt = (
        f"Context:\n{state.context}\n\n"
        f"User question: {state.query}\n\n"
        "Provide a helpful answer based on the context above."
    )
    messages.append({"role": "user", "content": user_prompt})

    state.answer = get_llm().chat(messages)
    state.model = settings.groq_model
    return state


def validate_answer(state: GraphState) -> GraphState:
    if not state.retrieval_results:
        state.confidence = "fallback"
        return state

    prompt = (
        f"Question: {state.query}\n\n"
        f"Context:\n{state.context}\n\n"
        f"Proposed answer: {state.answer}\n\n"
        + VALIDATION_PROMPT
    )
    is_valid = get_llm().judge_yes_no(prompt)

    if is_valid and len(state.retrieval_results) >= 3:
        state.confidence = "high"
    elif is_valid:
        state.confidence = "medium"
    else:
        state.confidence = "low"
        if state.retry_count < settings.max_retries:
            state.retry_count += 1
    return state


def generate_clarification(state: GraphState) -> GraphState:
    messages = [
        {"role": "system", "content": CLARIFICATION_PROMPT},
        {"role": "user", "content": state.query},
    ]
    state.answer = get_llm().chat(messages)
    state.confidence = "low"
    state.model = settings.groq_model
    return state


def fallback(state: GraphState) -> GraphState:
    messages = [
        {"role": "system", "content": FALLBACK_PROMPT},
        {"role": "user", "content": state.query},
    ]
    state.answer = get_llm().chat(messages)
    state.confidence = "fallback"
    state.fallback_triggered = True
    state.model = settings.groq_model
    return state


def should_clarify_or_answer(state: GraphState) -> str:
    if state.needs_clarification:
        return "clarify"
    return "generate"


def should_retry_or_fallback(state: GraphState) -> str:
    if state.confidence == "low" and state.retry_count < settings.max_retries:
        return "retrieve"
    if state.confidence == "low" or state.confidence == "fallback":
        return "fallback"
    return "end"


NODE_FUNCTIONS = {
    "classify": classify_query,
    "retrieve": retrieve,
    "check_ambiguity": check_ambiguity,
    "generate": generate_answer,
    "validate": validate_answer,
    "clarify": generate_clarification,
    "fallback": fallback,
}
