from typing import List, Dict
from app.core.qdrant_client import QdrantStore
from app.core.embeddings import embed_text

class DenseRetriever:
    def __init__(self, store: QdrantStore | None = None):
        self.store = store or QdrantStore()

    def search(self, query: str, top_k: int = 20, filters: Dict | None = None) -> List[Dict]:
        vector = embed_text(query)
        results = self.store.search(vector=vector, top_k=top_k, filters=filters)
        return [
            {
                "id": r["id"],
                "document_id": r["payload"].get("document_id"),
                "chunk_id": r["payload"].get("chunk_id"),
                "title": r["payload"].get("title"),
                "chunk": r["payload"].get("chunk"),
                "metadata": r["payload"].get("metadata", {}),
                "score": r["score"],
                "rank": rank + 1,
            }
            for rank, r in enumerate(results)
        ]
