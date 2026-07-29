from uuid import UUID, uuid4
from typing import List
from sqlalchemy.orm import Session
from app.models.database import Document
from app.models.schemas import DocumentCreate, DocumentUpdate, DocumentResponse
from app.core.qdrant_client import QdrantStore
from app.core.embeddings import embed_text
from app.retrieval.chunker import Chunker
from app.retrieval.hybrid import HybridSearch
from app.retrieval.bm25 import BM25Index

class KnowledgeService:
    def __init__(self):
        self.db_session: Session | None = None
        self.store = QdrantStore()
        self.chunker = Chunker()
        self.hybrid = HybridSearch()

    def set_db(self, db: Session):
        self.db_session = db

    def create_document(self, payload: DocumentCreate) -> DocumentResponse:
        doc = Document(
            id=uuid4(),
            title=payload.title,
            content=payload.content,
            metadata_=payload.metadata,
        )
        self.db_session.add(doc)
        self.db_session.commit()
        self.db_session.refresh(doc)
        self._index_document(doc)
        return self._to_schema(doc)

    def _index_document(self, doc: Document):
        chunks = self.chunker.chunk_document(
            document_id=str(doc.id),
            title=doc.title,
            content=doc.content,
            metadata=doc.metadata_,
        )
        if not chunks:
            return
        ids = [c["chunk_id"] for c in chunks]
        texts = [c["chunk"] for c in chunks]
        vectors = embed_text(texts)
        self.store.upsert(ids=ids, vectors=vectors, payloads=chunks)
        # Re-warm BM25 in-memory index with the latest state
        payloads = [c for c in chunks]
        self.hybrid.warm(payloads, texts)

    def update_document(self, document_id: UUID, payload: DocumentUpdate) -> DocumentResponse:
        doc = self.db_session.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError("Document not found")
        if payload.title is not None:
            doc.title = payload.title
        if payload.content is not None:
            doc.content = payload.content
        if payload.metadata is not None:
            doc.metadata_ = payload.metadata
        self.db_session.commit()
        self.db_session.refresh(doc)
        self.store.delete_by_document_id(str(document_id))
        self._index_document(doc)
        return self._to_schema(doc)

    def get_document(self, document_id: UUID) -> DocumentResponse:
        doc = self.db_session.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError("Document not found")
        return self._to_schema(doc)

    def list_documents(self, skip: int = 0, limit: int = 50) -> List[DocumentResponse]:
        docs = self.db_session.query(Document).offset(skip).limit(limit).all()
        return [self._to_schema(d) for d in docs]

    def delete_document(self, document_id: UUID):
        doc = self.db_session.query(Document).filter(Document.id == document_id).first()
        if doc:
            self.db_session.delete(doc)
            self.db_session.commit()
        self.store.delete_by_document_id(str(document_id))

    def _to_schema(self, doc: Document) -> DocumentResponse:
        return DocumentResponse(
            id=doc.id,
            title=doc.title,
            content=doc.content,
            metadata=doc.metadata_,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )

    def warm_retrieval_index(self):
        docs = self.db_session.query(Document).all()
        all_chunks = []
        all_payloads = []
        for doc in docs:
            chunks = self.chunker.chunk_document(
                document_id=str(doc.id),
                title=doc.title,
                content=doc.content,
                metadata=doc.metadata_,
            )
            all_chunks.extend([c["chunk"] for c in chunks])
            all_payloads.extend(chunks)
        self.hybrid.warm(all_payloads, all_chunks)
