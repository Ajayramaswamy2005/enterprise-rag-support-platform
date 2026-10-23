"""
Ragas evaluation: semantic-only retrieval vs. the hybrid pipeline.

Both configurations index the same chunked corpus with the app's own retrieval
classes and answer with the same Groq prompt the LangGraph ``generate`` node uses,
so the only variable is retrieval:

- ``dense``  — Qdrant cosine search only (top-k)
- ``hybrid`` — BM25 + dense fused with RRF, then Cross-Encoder re-ranking (top-k)

Run from the repo root (needs GROQ_API_KEY):

    pip install -r requirements-eval.txt
    python -m evaluation.run_ragas
"""
import argparse
import json
import time
from pathlib import Path
from statistics import mean
from typing import Dict, List

from qdrant_client import QdrantClient

from app.config import settings
from app.core.embeddings import embed_text
from app.core.groq_client import GroqLLM
from app.core.qdrant_client import QdrantStore
from app.graph.nodes import build_answer_messages
from app.graph.state import GraphState
from app.retrieval.bm25 import BM25Index
from app.retrieval.chunker import Chunker
from app.retrieval.dense import DenseRetriever
from app.retrieval.hybrid import HybridSearch
from app.retrieval.reranker import CrossEncoderReranker

DATA_DIR = Path(__file__).parent / "data"
RESULTS_DIR = Path(__file__).parent / "results"


def build_indexes(chunk_size: int) -> tuple[DenseRetriever, HybridSearch]:
    corpus = json.loads((DATA_DIR / "corpus.json").read_text(encoding="utf-8"))
    chunker = Chunker(chunk_size=chunk_size)
    chunks = [
        c
        for doc in corpus
        for c in chunker.chunk_document(doc["document_id"], doc["title"], doc["content"], doc["metadata"])
    ]

    # In-memory Qdrant so the evaluation needs no running services
    store = QdrantStore()
    store.collection = "ragas_eval"
    store._client = QdrantClient(":memory:")
    store.upsert(
        ids=[c["chunk_id"] for c in chunks],
        vectors=embed_text([c["chunk"] for c in chunks]),
        payloads=chunks,
    )
    dense = DenseRetriever(store=store)

    bm25 = BM25Index()
    bm25.add_documents(chunks)
    hybrid = HybridSearch(bm25=bm25)
    hybrid.dense = dense
    print(f"Indexed {len(corpus)} documents as {len(chunks)} chunks")
    return dense, hybrid


def retrieve(config: str, query: str, dense: DenseRetriever, hybrid: HybridSearch,
             reranker: CrossEncoderReranker, top_k: int) -> List[Dict]:
    if config == "dense":
        return dense.search(query, top_k=top_k)
    candidates = hybrid.search(query, top_k=settings.retrieval_top_k)
    return reranker.rerank(query, candidates, top_k=top_k)


def answer(llm: GroqLLM, query: str, results: List[Dict]) -> str:
    # Same context format as the retrieve node, same prompt as the generate node
    context = "\n\n---\n\n".join(
        f"[{i+1}] {r.get('title') or 'Untitled'}:\n{r['chunk']}" for i, r in enumerate(results)
    )
    state = GraphState(query=query, conversation_id="ragas-eval", context=context, messages=[{"role": "user", "content": query}])
    for attempt in range(5):
        try:
            return llm.chat(build_answer_messages(state), temperature=0.0)
        except Exception as e:  # Groq rate limits on free tiers
            wait = 10 * (attempt + 1)
            print(f"  generation failed ({e.__class__.__name__}), retrying in {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"Generation failed for: {query}")


def build_samples(config: str, testset: List[Dict], dense, hybrid, reranker, llm, top_k: int) -> List[Dict]:
    samples = []
    for i, item in enumerate(testset, 1):
        results = retrieve(config, item["question"], dense, hybrid, reranker, top_k)
        samples.append({
            "user_input": item["question"],
            "retrieved_contexts": [r["chunk"] for r in results],
            "response": answer(llm, item["question"], results),
            "reference": item["reference"],
        })
        print(f"  [{config}] {i}/{len(testset)} generated")
    return samples


def score(samples: List[Dict], judge_model: str) -> List[Dict]:
    from langchain_groq import ChatGroq
    from langchain_huggingface import HuggingFaceEmbeddings
    from ragas import EvaluationDataset, RunConfig, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import LLMContextPrecisionWithReference, ResponseRelevancy

    llm = LangchainLLMWrapper(ChatGroq(model=judge_model, temperature=0.0, api_key=settings.groq_api_key))
    embeddings = LangchainEmbeddingsWrapper(HuggingFaceEmbeddings(model_name=settings.embedding_model))
    result = evaluate(
        dataset=EvaluationDataset.from_list(samples),
        metrics=[LLMContextPrecisionWithReference(), ResponseRelevancy()],
        llm=llm,
        embeddings=embeddings,
        run_config=RunConfig(max_workers=4, max_retries=10, max_wait=120, timeout=300),
    )
    return result.to_pandas().to_dict(orient="records")


def summarize(rows: List[Dict]) -> Dict[str, float]:
    def avg(key: str) -> float:
        values = [r[key] for r in rows if r.get(key) is not None and r[key] == r[key]]  # drop NaN
        return round(mean(values), 4) if values else float("nan")
    return {"context_precision": avg("llm_context_precision_with_reference"), "answer_relevancy": avg("answer_relevancy")}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--top-k", type=int, default=settings.reranker_top_k, help="contexts passed to the LLM")
    parser.add_argument("--chunk-size", type=int, default=40, help="chunker size in words")
    parser.add_argument("--judge-model", default=settings.groq_model, help="Groq model used by Ragas as judge")
    parser.add_argument("--limit", type=int, default=None, help="evaluate only the first N questions")
    args = parser.parse_args()

    testset = json.loads((DATA_DIR / "testset.json").read_text(encoding="utf-8"))[: args.limit]
    dense, hybrid = build_indexes(args.chunk_size)
    reranker = CrossEncoderReranker()
    llm = GroqLLM()

    RESULTS_DIR.mkdir(exist_ok=True)
    report = {
        "generator_model": settings.groq_model,
        "judge_model": args.judge_model,
        "embedding_model": settings.embedding_model,
        "reranker_model": settings.reranker_model,
        "top_k": args.top_k,
        "candidates_before_rerank": settings.retrieval_top_k,
        "chunk_size": args.chunk_size,
        "questions": len(testset),
        "configs": {},
    }
    for config in ("dense", "hybrid"):
        samples = build_samples(config, testset, dense, hybrid, reranker, llm, args.top_k)
        rows = score(samples, args.judge_model)
        report["configs"][config] = summarize(rows)
        (RESULTS_DIR / f"{config}_samples.json").write_text(
            json.dumps(rows, indent=2, default=str), encoding="utf-8"
        )
        print(f"{config}: {report['configs'][config]}")

    (RESULTS_DIR / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n| Retrieval | Context Precision | Answer Relevancy |\n|---|---|---|")
    for config, label in (("dense", "Dense only (semantic)"), ("hybrid", "BM25 + Dense + RRF + Cross-Encoder")):
        m = report["configs"][config]
        print(f"| {label} | {m['context_precision']:.2f} | {m['answer_relevancy']:.2f} |")


if __name__ == "__main__":
    main()
