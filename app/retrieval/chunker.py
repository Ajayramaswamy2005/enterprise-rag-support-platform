import re
import uuid
from typing import List, Dict

class Chunker:
    def __init__(self, chunk_size: int = 512, overlap: int = 64):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split_text(self, text: str) -> List[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks = []
        current = []
        current_len = 0
        for sentence in sentences:
            length = len(sentence.split())
            if current_len + length > self.chunk_size and current:
                chunks.append(" ".join(current))
                overlap_sentences = current[-2:] if len(current) > 2 else current
                current = overlap_sentences + [sentence]
                current_len = sum(len(s.split()) for s in current)
            else:
                current.append(sentence)
                current_len += length
        if current:
            chunks.append(" ".join(current))
        return chunks

    def chunk_document(self, document_id: str, title: str, content: str, metadata: Dict) -> List[Dict]:
        texts = self.split_text(content)
        return [
            {
                "chunk_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{document_id}-{i}")),
                "document_id": document_id,
                "title": title,
                "chunk": text,
                "metadata": metadata,
                "order": i,
            }
            for i, text in enumerate(texts)
        ]
