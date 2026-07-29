import re
from typing import List, Dict
from rank_bm25 import BM25Okapi

class BM25Index:
    def __init__(self):
        self._corpus: List[str] = []
        self._documents: List[Dict] = []
        self._index: BM25Okapi | None = None

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[a-zA-Z0-9]+", text.lower())

    def add_documents(self, documents: List[Dict]):
        for doc in documents:
            chunks = doc.get("chunks", [])
            for chunk in chunks:
                self._corpus.append(chunk)
                self._documents.append({
                    "chunk": chunk,
                    "document_id": doc.get("document_id"),
                    "chunk_id": doc.get("chunk_id"),
                    "title": doc.get("title"),
                    **doc.get("metadata", {}),
                })
        if self._corpus:
            tokenized = [self._tokenize(c) for c in self._corpus]
            self._index = BM25Okapi(tokenized)

    def search(self, query: str, top_k: int = 20) -> List[Dict]:
        if not self._index:
            return []
        tokenized_query = self._tokenize(query)
        scores = self._index.get_scores(tokenized_query)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results = []
        for rank, (idx, score) in enumerate(ranked[:top_k]):
            results.append({
                **self._documents[idx],
                "score": float(score),
                "rank": rank + 1,
            })
        return results

    def from_qdrant_payloads(self, payloads: List[dict], chunks: List[str]):
        docs = []
        for p, c in zip(payloads, chunks):
            docs.append({
                "chunk": c,
                "document_id": p.get("document_id"),
                "chunk_id": p.get("chunk_id"),
                "title": p.get("title"),
                "metadata": p.get("metadata", {}),
            })
        self.add_documents(docs)
