import logging
from uuid import UUID, uuid4
from typing import List
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.database import Document
from app.models.schemas import DocumentCreate, DocumentUpdate, DocumentResponse
from app.core.qdrant_client import QdrantStore
from app.core.embeddings import embed_text
from app.retrieval.chunker import Chunker
from app.retrieval.bm25 import shared_bm25

logger = logging.getLogger(__name__)

class KnowledgeService:
    def __init__(self):
        self.db_session: Session | None = None
        self.store = QdrantStore()
        self.chunker = Chunker()
        self.bm25 = shared_bm25

    def set_db(self, db: Session):
        self.db_session = db

    def create_document(self, payload: DocumentCreate) -> tuple[DocumentResponse, int]:
        doc = Document(
            id=uuid4(),
            title=payload.title,
            content=payload.content,
            metadata_=payload.metadata,
        )
        self.db_session.add(doc)
        self.db_session.commit()
        self.db_session.refresh(doc)
        try:
            chunk_count = self._index_document(doc)
        except Exception:
            # Don't leave a document in PostgreSQL that retrieval can never find
            self.db_session.delete(doc)
            self.db_session.commit()
            raise
        return self._to_schema(doc), chunk_count

    def _chunks_for(self, doc: Document) -> List[dict]:
        return self.chunker.chunk_document(
            document_id=str(doc.id),
            title=doc.title,
            content=doc.content,
            metadata=doc.metadata_ or {},
        )

    def _index_document(self, doc: Document) -> int:
        chunks = self._chunks_for(doc)
        if not chunks:
            return 0
        ids = [c["chunk_id"] for c in chunks]
        texts = [c["chunk"] for c in chunks]
        vectors = embed_text(texts)
        self.store.upsert(ids=ids, vectors=vectors, payloads=chunks)
        self.bm25.from_qdrant_payloads(chunks, texts)
        return len(chunks)

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
        self.bm25.remove_document(str(document_id))
        self._index_document(doc)
        return self._to_schema(doc)

    def get_document(self, document_id: UUID) -> DocumentResponse:
        doc = self.db_session.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError("Document not found")
        return self._to_schema(doc)

    def list_documents(self, skip: int = 0, limit: int = 50) -> List[DocumentResponse]:
        docs = (
            self.db_session.query(Document)
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [self._to_schema(d) for d in docs]

    def count_documents(self) -> int:
        return self.db_session.query(func.count(Document.id)).scalar() or 0

    def delete_document(self, document_id: UUID) -> bool:
        doc = self.db_session.query(Document).filter(Document.id == document_id).first()
        if doc:
            self.db_session.delete(doc)
            self.db_session.commit()
        self.bm25.remove_document(str(document_id))
        try:
            self.store.delete_by_document_id(str(document_id))
        except Exception as e:
            logger.warning("Could not delete vectors for %s: %s", document_id, e)
        return doc is not None

    def stats(self) -> dict:
        try:
            vectors = self.store.count()
        except Exception:
            vectors = None
        return {
            "documents": self.count_documents(),
            "sparse_chunks": len(self.bm25),
            "vectors": vectors,
        }

    def _to_schema(self, doc: Document) -> DocumentResponse:
        return DocumentResponse(
            id=doc.id,
            title=doc.title,
            content=doc.content,
            metadata=doc.metadata_ or {},
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )

    def reindex(self, force: bool = False) -> dict:
        """Bring Qdrant and BM25 back in line with PostgreSQL.

        By default only chunks missing from Qdrant are embedded, which repairs
        documents added while Qdrant was unreachable. `force` re-embeds
        everything, e.g. after changing the embedding model.
        """
        docs = self.db_session.query(Document).all()
        all_chunks = []
        missing = []
        for doc in docs:
            chunks = self._chunks_for(doc)
            all_chunks.extend(chunks)
            if force:
                self.store.delete_by_document_id(str(doc.id))
        if force:
            missing = all_chunks
        elif all_chunks:
            existing = self.store.existing_ids([c["chunk_id"] for c in all_chunks])
            missing = [c for c in all_chunks if c["chunk_id"] not in existing]
        if missing:
            self.store.upsert(
                ids=[c["chunk_id"] for c in missing],
                vectors=embed_text([c["chunk"] for c in missing]),
                payloads=missing,
            )
        self.warm_retrieval_index()
        return {
            "documents": len(docs),
            "chunks": len(all_chunks),
            "vectors_written": len(missing),
        }

    def warm_retrieval_index(self) -> int:
        """Rebuild the in-memory BM25 index from every document in PostgreSQL."""
        all_chunks = []
        for doc in self.db_session.query(Document).all():
            all_chunks.extend(self._chunks_for(doc))
        self.bm25.clear()
        if all_chunks:
            self.bm25.from_qdrant_payloads(all_chunks, [c["chunk"] for c in all_chunks])
        return len(all_chunks)
