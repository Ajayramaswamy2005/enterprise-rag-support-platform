from typing import List, Dict
from collections import defaultdict
from app.config import settings
from app.retrieval.bm25 import BM25Index, shared_bm25
from app.retrieval.dense import DenseRetriever

class HybridSearch:
    """
    Combines BM25 sparse retrieval and dense vector retrieval using Reciprocal Rank Fusion (RRF).
    """

    def __init__(self, bm25: BM25Index | None = None):
        self.bm25 = bm25 if bm25 is not None else shared_bm25
        self.dense = DenseRetriever()
        self.rrf_k = settings.rrf_k
        self.dense_weight = settings.hybrid_dense_weight
        self.sparse_weight = settings.hybrid_sparse_weight

    def rrf_fuse(self, dense_results: List[Dict], sparse_results: List[Dict], top_k: int = 20) -> List[Dict]:
        scores = defaultdict(float)
        metadata = {}

        for r in dense_results:
            key = r["chunk_id"]
            scores[key] += self.dense_weight / (self.rrf_k + r["rank"])
            metadata[key] = r

        for r in sparse_results:
            key = r["chunk_id"]
            scores[key] += self.sparse_weight / (self.rrf_k + r["rank"])
            if key not in metadata:
                metadata[key] = r

        fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        output = []
        for rank, (key, score) in enumerate(fused[:top_k]):
            item = {**metadata[key], "rrf_score": score, "rank": rank + 1}
            output.append(item)
        return output

    def search(self, query: str, top_k: int = 20, filters: Dict | None = None) -> List[Dict]:
        dense_results = self.dense.search(query, top_k=top_k, filters=filters)
        sparse_results = self.bm25.search(query, top_k=top_k)
        # Filter sparse results by same metadata filters if needed
        if filters:
            sparse_results = [r for r in sparse_results if all(r.get(k) == v for k, v in filters.items())]
            for rank, r in enumerate(sparse_results):
                r["rank"] = rank + 1
        fused = self.rrf_fuse(dense_results, sparse_results, top_k=top_k)
        return fused

    def warm(self, payloads: List[dict], chunks: List[str]):
        self.bm25.from_qdrant_payloads(payloads, chunks)
