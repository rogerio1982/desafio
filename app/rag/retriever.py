"""
app/rag/retriever.py

Semantic retrieval over the local knowledge-base files.

Chunking strategy:
  - Split on blank lines (\\n\\n), preserving each record as a self-contained chunk.
  - Filter out fragments shorter than 30 characters.

Retrieval strategy:
  - Embed query and all chunks with text-embedding-3-small.
  - Rank by cosine similarity; return top-k chunks above threshold 0.1.
  - TF-IDF fallback if the embedding API call fails.
  - Embedding cache avoids re-embedding identical chunks across requests.
"""

import math
import os
from collections import Counter

from agents import function_tool
from app.config import client

_KB_FILES = [
    "vehicle_catalog.txt",
    "dealership_faq.txt",
    "showroom_layouts.txt",
]

# In-process caches — populated once per server lifecycle
_chunk_cache: dict[str, list[str]] = {}
_embed_cache: dict[str, list[float]] = {}


# ── Chunking ─────────────────────────────────────────────────────────────────

def _load_all_chunks() -> list[str]:
    """Load and cache all knowledge-base chunks across all three files."""
    if not _chunk_cache:
        for fname in _KB_FILES:
            path = os.path.join("data", fname)
            try:
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                chunks = [c.strip() for c in content.split("\n\n") if len(c.strip()) > 30]
                _chunk_cache[fname] = chunks
            except FileNotFoundError:
                _chunk_cache[fname] = []
    return [chunk for chunks in _chunk_cache.values() for chunk in chunks]


# ── Similarity utilities ──────────────────────────────────────────────────────

def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / ((norm_a * norm_b) or 1.0)


def _tfidf_score(query: str, chunk: str) -> float:
    query_tokens = query.lower().split()
    chunk_tokens = chunk.lower().split()
    freq = Counter(chunk_tokens)
    return sum(freq.get(t, 0) / (len(chunk_tokens) or 1) for t in query_tokens)


# ── Embedding ─────────────────────────────────────────────────────────────────

def _embed(texts: list[str]) -> list[list[float]]:
    """Batch-embed texts, using the in-process cache to avoid duplicate API calls."""
    uncached = [t for t in texts if t not in _embed_cache]
    if uncached:
        for i in range(0, len(uncached), 100):
            batch = uncached[i : i + 100]
            resp = client.embeddings.create(model="text-embedding-3-small", input=batch)
            for text, item in zip(batch, resp.data):
                _embed_cache[text] = item.embedding
    return [_embed_cache[t] for t in texts]


# ── Public interface ──────────────────────────────────────────────────────────

def search_local_kb(query: str, top_k: int = 4) -> str:
    """
    Return the top-k most semantically relevant knowledge-base chunks for *query*.
    Falls back to TF-IDF ranking if the embedding API call fails.
    Returns an empty string when no relevant chunks are found.
    """
    all_chunks = _load_all_chunks()
    if not all_chunks:
        return ""

    try:
        query_emb = _embed([query])[0]
        chunk_embs = _embed(all_chunks)
        scored = sorted(
            zip(all_chunks, (_cosine(query_emb, e) for e in chunk_embs)),
            key=lambda x: x[1],
            reverse=True,
        )
        top = [chunk for chunk, score in scored[:top_k] if score > 0.1]
    except Exception:
        top = sorted(all_chunks, key=lambda c: _tfidf_score(query, c), reverse=True)[:top_k]

    return "\n\n---\n\n".join(top)


@function_tool
def search_knowledge_base(query: str) -> str:
    """
    Search the 3D digital showroom knowledge base.
    Covers vehicles, showroom layouts, financing options, and dealership FAQs.
    Call this when you need specific facts from the knowledge base.
    """
    result = search_local_kb(query)
    return result or "No relevant information found for this query."
