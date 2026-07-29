from app.retrieval.chunker import Chunker
from app.retrieval.bm25 import BM25Index
from app.retrieval.hybrid import HybridSearch

class MockDenseRetriever:
    def __init__(self):
        pass
    def search(self, query, top_k=20, filters=None):
        return []

def test_chunker():
    text = "This is sentence one. This is sentence two. This is sentence three."
    chunker = Chunker(chunk_size=10, overlap=2)
    chunks = chunker.split_text(text)
    assert len(chunks) > 0
    assert all(len(c) > 0 for c in chunks)

def test_bm25_ranking():
    idx = BM25Index()
    idx.add_documents([
        {
            "document_id": "doc-1",
            "title": "Refund policy",
            "chunks": ["How do I get a refund?", "Refunds are processed within 5 days."],
            "metadata": {"category": "billing"},
        },
        {
            "document_id": "doc-2",
            "title": "Password reset",
            "chunks": ["How do I reset my password?", "Use the forgot password link."],
            "metadata": {"category": "technical"},
        }
    ])
    results = idx.search("refund", top_k=5)
    assert len(results) > 0
    assert any("refund" in r["chunk"].lower() for r in results)

def test_rrf_fusion():
    dense = [
        {"chunk_id": "a", "rank": 1, "score": 0.9},
        {"chunk_id": "b", "rank": 2, "score": 0.8},
    ]
    sparse = [
        {"chunk_id": "b", "rank": 1, "score": 0.95},
        {"chunk_id": "c", "rank": 2, "score": 0.85},
    ]
    hybrid = HybridSearch()
    hybrid.dense = MockDenseRetriever()
    fused = hybrid.rrf_fuse(dense, sparse, top_k=10)
    assert len(fused) == 3
    assert fused[0]["chunk_id"] == "b"  # appears in both lists
