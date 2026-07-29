from langgraph.graph import StateGraph, END
from app.graph.state import GraphState
from app.graph.nodes import (
    classify_query,
    retrieve,
    check_ambiguity,
    generate_answer,
    validate_answer,
    generate_clarification,
    fallback,
    should_clarify_or_answer,
    should_retry_or_fallback,
)

class CustomerSupportWorkflow:
    def __init__(self):
        self.builder = StateGraph(GraphState)
        self._build()

    def _build(self):
        self.builder.add_node("classify", classify_query)
        self.builder.add_node("retrieve", retrieve)
        self.builder.add_node("check_ambiguity", check_ambiguity)
        self.builder.add_node("generate", generate_answer)
        self.builder.add_node("validate", validate_answer)
        self.builder.add_node("clarify", generate_clarification)
        self.builder.add_node("fallback", fallback)

        self.builder.set_entry_point("classify")
        self.builder.add_edge("classify", "retrieve")
        self.builder.add_edge("retrieve", "check_ambiguity")
        self.builder.add_conditional_edges(
            "check_ambiguity",
            should_clarify_or_answer,
            {"clarify": "clarify", "generate": "generate"},
        )
        self.builder.add_edge("generate", "validate")
        self.builder.add_conditional_edges(
            "validate",
            should_retry_or_fallback,
            {"retrieve": "retrieve", "fallback": "fallback", "end": END},
        )
        self.builder.add_edge("clarify", END)
        self.builder.add_edge("fallback", END)

        self.app = self.builder.compile()

    def invoke(self, state: GraphState) -> GraphState:
        return self.app.invoke(state)

    def stream(self, state: GraphState):
        return self.app.stream(state)

workflow = CustomerSupportWorkflow()

__all__ = ["CustomerSupportWorkflow", "workflow"]
