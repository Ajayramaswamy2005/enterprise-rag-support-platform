from typing import List
from app.config import settings
from app.core.groq_client import GroqLLM
from app.core.opik_tracker import traced
from app.retrieval.hybrid import HybridSearch
from app.retrieval.reranker import CrossEncoderReranker
from app.graph.state import GraphState

_llm: GroqLLM | None = None
_hybrid: HybridSearch | None = None
_reranker: CrossEncoderReranker | None = None

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
# Only these labels correspond to document categories worth filtering on
FILTERABLE_LABELS = {"support", "billing", "technical"}
HISTORY_WINDOW = 6

SYSTEM_PROMPT = """You are a helpful enterprise customer support assistant.
Answer based ONLY on the provided context. If the context does not contain enough information, say so honestly and offer to escalate.
Cite sources inline as [1], [2], ... matching the numbered sources in the context. Be concise, professional, and accurate.
Use Markdown (short paragraphs, bullet lists, bold for key terms) when it improves readability."""

CLARIFICATION_PROMPT = """The user's query is ambiguous or missing critical details.
Ask a short, clear follow-up question to gather the information needed to answer accurately."""

FALLBACK_PROMPT = """I couldn't find a reliable answer in our knowledge base.
Please provide a brief, empathetic response that offers to connect the user with a human support agent or asks for clarification.
Do not invent policies, prices, or steps."""

VALIDATION_PROMPT = """You are a quality reviewer.
Given the user question, retrieved context, and the proposed answer, determine if the answer is accurate and supported by the context.
Respond only Yes or No."""


def _history(state: GraphState) -> List[dict]:
    """Prior turns, excluding the current question (which is sent separately with its context)."""
    msgs = [m for m in state.messages if m.get("role") in ("user", "assistant")]
    if msgs and msgs[-1].get("role") == "user" and msgs[-1].get("content") == state.query:
        msgs = msgs[:-1]
    return msgs[-HISTORY_WINDOW:]


def build_answer_messages(state: GraphState) -> List[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend({"role": m["role"], "content": m["content"]} for m in _history(state))
    messages.append({
        "role": "user",
        "content": (
            f"Context:\n{state.context}\n\n"
            f"User question: {state.query}\n\n"
            "Provide a helpful answer based on the context above."
        ),
    })
    return messages


def build_clarification_messages(state: GraphState) -> List[dict]:
    messages = [{"role": "system", "content": CLARIFICATION_PROMPT}]
    messages.extend({"role": m["role"], "content": m["content"]} for m in _history(state))
    messages.append({"role": "user", "content": state.query})
    return messages


def build_fallback_messages(state: GraphState) -> List[dict]:
    return [
        {"role": "system", "content": FALLBACK_PROMPT},
        {"role": "user", "content": state.query},
    ]


@traced("classify")
def classify_query(state: GraphState) -> GraphState:
    prompt = f"Classify this customer support query into one category: {', '.join(CLASSIFICATION_LABELS)}.\n\nQuery: {state.query}"
    state.query_type = get_llm().classify(prompt, CLASSIFICATION_LABELS)
    return state


@traced("retrieve")
def retrieve(state: GraphState) -> GraphState:
    hybrid = get_hybrid()
    # A retry after a failed validation widens the net: no category filter and more candidates
    is_retry = state.retry_count > 0
    top_k = settings.retrieval_top_k * (2 if is_retry else 1)

    filters = None
    if state.query_type in FILTERABLE_LABELS and not is_retry:
        filters = {"category": state.query_type}

    candidates = hybrid.search(state.query, top_k=top_k, filters=filters)
    if not candidates and filters:
        candidates = hybrid.search(state.query, top_k=top_k)

    reranked = get_reranker().rerank(state.query, candidates, top_k=settings.reranker_top_k)
    state.retrieval_results = reranked
    state.context = "\n\n---\n\n".join(
        f"[{i+1}] {r.get('title') or 'Untitled'}:\n{r['chunk']}"
        for i, r in enumerate(reranked)
    )
    return state


@traced("check_ambiguity")
def check_ambiguity(state: GraphState) -> GraphState:
    if not state.retrieval_results:
        # Nothing to ground an answer on: that is a fallback, not an ambiguity
        state.needs_clarification = False
        return state

    history = "\n".join(f"{m['role']}: {m['content']}" for m in _history(state)[-4:])
    prompt = (
        (f"Conversation so far:\n{history}\n\n" if history else "")
        + f"User question: {state.query}\n\n"
        "Taking the conversation into account, is this question clear enough to answer with a knowledge base? "
        "Respond only Yes if it is clear, or No if clarification is needed."
    )
    state.needs_clarification = not get_llm().judge_yes_no(prompt)
    return state


@traced("generate")
def generate_answer(state: GraphState) -> GraphState:
    state.answer = get_llm().chat(build_answer_messages(state))
    state.model = settings.groq_model
    return state


@traced("validate")
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
    return state


@traced("clarify")
def generate_clarification(state: GraphState) -> GraphState:
    state.answer = get_llm().chat(build_clarification_messages(state))
    state.confidence = "low"
    state.model = settings.groq_model
    return state


@traced("fallback")
def fallback(state: GraphState) -> GraphState:
    state.answer = get_llm().chat(build_fallback_messages(state))
    state.confidence = "fallback"
    state.fallback_triggered = True
    state.model = settings.groq_model
    return state


def increment_retry(state: GraphState) -> GraphState:
    state.retry_count += 1
    return state


def should_clarify_or_answer(state: GraphState) -> str:
    if not state.retrieval_results:
        return "fallback"
    if state.needs_clarification:
        return "clarify"
    return "generate"


def should_retry_or_fallback(state: GraphState) -> str:
    if state.confidence == "low" and state.retry_count < settings.max_retries:
        return "retry"
    if state.confidence in ("low", "fallback"):
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
    "retry": increment_retry,
}
