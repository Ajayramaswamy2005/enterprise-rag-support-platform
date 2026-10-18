import re
import threading
from typing import List, Dict
from rank_bm25 import BM25Okapi

class BM25Index:
    """In-memory BM25 index keyed by chunk_id so re-indexing a document replaces its chunks."""

    def __init__(self):
        self._entries: Dict[str, Dict] = {}
        self._keys: List[str] = []
        self._token_sets: List[set] = []
        self._index: BM25Okapi | None = None
        self._lock = threading.RLock()

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[a-zA-Z0-9]+", text.lower())

    def _rebuild(self):
        self._keys = list(self._entries.keys())
        if self._keys:
            tokenized = [self._tokenize(self._entries[k]["chunk"]) for k in self._keys]
            self._token_sets = [set(t) for t in tokenized]
            self._index = BM25Okapi(tokenized)
        else:
            self._token_sets = []
            self._index = None

    def __len__(self) -> int:
        return len(self._entries)

    def add_documents(self, documents: List[Dict]):
        """Accepts either one chunk per item (``chunk``) or several (``chunks``)."""
        with self._lock:
            for doc in documents:
                texts = doc.get("chunks") or ([doc["chunk"]] if doc.get("chunk") else [])
                for i, text in enumerate(texts):
                    chunk_id = doc.get("chunk_id") if len(texts) == 1 and doc.get("chunk_id") else f"{doc.get('document_id')}-{i}"
                    self._entries[chunk_id] = {
                        "chunk": text,
                        "document_id": doc.get("document_id"),
                        "chunk_id": chunk_id,
                        "title": doc.get("title"),
                        "metadata": doc.get("metadata", {}) or {},
                        **(doc.get("metadata", {}) or {}),
                    }
            self._rebuild()

    def remove_document(self, document_id: str):
        with self._lock:
            self._entries = {k: v for k, v in self._entries.items() if v.get("document_id") != document_id}
            self._rebuild()

    def clear(self):
        with self._lock:
            self._entries = {}
            self._rebuild()

    def search(self, query: str, top_k: int = 20) -> List[Dict]:
        with self._lock:
            if not self._index:
                return []
            tokenized_query = self._tokenize(query)
            if not tokenized_query:
                return []
            scores = self._index.get_scores(tokenized_query)
            ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
            results = []
            query_terms = set(tokenized_query)
            for idx, score in ranked:
                if len(results) >= top_k:
                    break
                # Chunks sharing no terms with the query are noise, not candidates.
                # (Checked by overlap, not score: IDF goes negative in tiny corpora.)
                if not query_terms & self._token_sets[idx]:
                    continue
                results.append({
                    **self._entries[self._keys[idx]],
                    "score": float(score),
                    "rank": len(results) + 1,
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

# Process-wide index shared by ingestion and chat so both see the same corpus
shared_bm25 = BM25Index()
