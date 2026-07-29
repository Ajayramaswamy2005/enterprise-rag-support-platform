from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from app.config import settings

_model: SentenceTransformer | None = None

def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model

def embed_text(text: str | List[str]) -> List[List[float]] | List[float]:
    model = get_embedding_model()
    embeddings = model.encode(text, convert_to_numpy=True, show_progress_bar=False)
    if isinstance(text, str):
        return embeddings.tolist()
    return [e.tolist() for e in embeddings]

def normalize(vector: List[float]) -> List[float]:
    arr = np.array(vector, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm == 0:
        return arr.tolist()
    return (arr / norm).tolist()
