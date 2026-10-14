from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from typing import List, Optional, Tuple
from uuid import uuid4, UUID
import numpy as np
from app.config import settings

_qdrant_client: QdrantClient | None = None

def get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        kwargs = {"url": settings.qdrant_url}
        if settings.qdrant_api_key:
            kwargs["api_key"] = settings.qdrant_api_key
        _qdrant_client = QdrantClient(**kwargs)
    return _qdrant_client

class QdrantStore:
    def __init__(self):
        self.collection = settings.qdrant_collection
        self._client = None
        self._ready = False

    @property
    def client(self):
        if self._client is None:
            self._client = get_qdrant_client()
        return self._client

    def _ensure_collection(self):
        if self._ready:
            return
        collections = self.client.get_collections().collections
        names = [c.name for c in collections]
        if self.collection not in names:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=settings.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
        try:
            self.client.create_payload_index(
                collection_name=self.collection,
                field_name="category",
                field_schema="keyword",
            )
        except Exception:
            pass
        self._ready = True

    def upsert(self, ids: List[str], vectors: List[List[float]], payloads: List[dict], batch_size: int = 64):
        self._ensure_collection()
        points = [
            PointStruct(id=ids[i], vector=vectors[i], payload=payloads[i])
            for i in range(len(ids))
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    def search(self, vector: List[float], top_k: int = 20, filters: Optional[dict] = None) -> List[dict]:
        self._ensure_collection()
        qdrant_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
            qdrant_filter = Filter(must=conditions)

        # Support both new (query_points) and legacy (search) qdrant-client versions
        try:
            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=self.collection,
                    query=vector,
                    limit=top_k,
                    query_filter=qdrant_filter,
                    with_payload=True,
                )
                points = response.points
            else:
                points = self.client.search(
                    collection_name=self.collection,
                    query_vector=vector,
                    limit=top_k,
                    query_filter=qdrant_filter,
                    with_payload=True,
                )
        except Exception:
            # Fallback without filter if index is not ready or missing
            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=self.collection,
                    query=vector,
                    limit=top_k,
                    with_payload=True,
                )
                points = response.points
            else:
                points = self.client.search(
                    collection_name=self.collection,
                    query_vector=vector,
                    limit=top_k,
                    with_payload=True,
                )

        return [
            {
                "id": r.id,
                "score": r.score,
                "payload": r.payload,
            }
            for r in points
        ]

    def delete_by_document_id(self, document_id: str):
        self.client.delete(
            collection_name=self.collection,
            points_selector=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
            ),
        )

    def count(self) -> int:
        return self.client.count(collection_name=self.collection).count
