from typing import List, Dict
from sentence_transformers import CrossEncoder
from app.config import settings

_reranker: CrossEncoder | None = None

def get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(settings.reranker_model)
    return _reranker

class CrossEncoderReranker:
    def rerank(self, query: str, results: List[Dict], top_k: int | None = None) -> List[Dict]:
        valid_results = [r for r in results if r.get("chunk")]
        if not valid_results:
            return []
        reranker = get_reranker()
        pairs = [(query, str(r["chunk"])) for r in valid_results]
        scores = reranker.predict(pairs, show_progress_bar=False)
        scored = [
            {**r, "rerank_score": float(score)}
            for r, score in zip(valid_results, scores)
        ]
        ranked = sorted(scored, key=lambda x: x["rerank_score"], reverse=True)
        top = top_k or settings.reranker_top_k
        return ranked[:top]
