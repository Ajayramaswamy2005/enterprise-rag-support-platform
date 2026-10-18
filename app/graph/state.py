from typing import List, Optional, Literal
from dataclasses import dataclass, field

@dataclass
class GraphState:
    query: str
    conversation_id: str
    # Plain list (no reducer): nodes return the whole state, and an additive
    # reducer would duplicate the conversation history on every node.
    messages: List[dict] = field(default_factory=list)
    query_type: Optional[str] = None
    retrieval_results: List[dict] = field(default_factory=list)
    context: str = ""
    answer: str = ""
    confidence: Literal["high", "medium", "low", "fallback"] = "medium"
    needs_clarification: bool = False
    fallback_triggered: bool = False
    retry_count: int = 0
    model: str = ""
    trace_id: Optional[str] = None
    error: Optional[str] = None
