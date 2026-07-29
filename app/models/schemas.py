from datetime import datetime
from typing import List, Optional, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: str = Field(..., min_length=1)

class ChatRequest(BaseModel):
    conversation_id: Optional[UUID] = None
    messages: List[ChatMessage] = Field(..., min_length=1)
    stream: bool = False

class SourceChunk(BaseModel):
    chunk_id: str
    document_id: str
    title: Optional[str] = None
    content: str
    score: float
    rank: Optional[int] = None

class ChatResponse(BaseModel):
    conversation_id: UUID
    answer: str
    sources: List[SourceChunk] = []
    confidence: Literal["high", "medium", "low", "fallback"] = "medium"
    model: str
    took_ms: int

# ---------------------------------------------------------------------------
# Knowledge Base Documents
# ---------------------------------------------------------------------------

class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    metadata: dict = Field(default_factory=dict)

class DocumentResponse(BaseModel):
    id: UUID
    title: str
    content: str
    metadata: dict
    created_at: datetime
    updated_at: datetime

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    metadata: Optional[dict] = None

class DocumentList(BaseModel):
    items: List[DocumentResponse]
    total: int

class IngestResponse(BaseModel):
    document_id: UUID
    chunks_indexed: int
    message: str

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    version: str
    components: dict

# ---------------------------------------------------------------------------
# LangGraph internal state (also exposed as request/response building blocks)
# ---------------------------------------------------------------------------

class GraphStateInput(BaseModel):
    query: str
    conversation_id: str = Field(default_factory=lambda: str(uuid4()))
    messages: List[ChatMessage] = Field(default_factory=list)

class GraphStateOutput(BaseModel):
    conversation_id: UUID
    answer: str
    sources: List[SourceChunk]
    confidence: str
    model: str
    trace_id: Optional[str] = None
