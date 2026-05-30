"""
retrieval.py
============
Turns "what the user wants" into "a short list of likely catalog items".

Why TF-IDF (and not a big embedding model)?
  - It is fully offline: no API key, no network, no GPU. The retriever works
    even before you add an LLM key, which keeps the service reliable.
  - The SHL catalog is keyword-heavy ("Java", "Python", "OPQ", "personality"),
    which is exactly where TF-IDF shines.
  - It is fast (sub-millisecond) and easy to reason about in an interview.

The LLM then reads these candidates and decides which ones actually fit. So
retrieval is the "shortlist generator" and the LLM is the "final judge".
"""
from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .catalog import Assessment, Catalog


class Retriever:
    def __init__(self, catalog: Catalog):
        self.catalog = catalog
        self.docs = [a.search_document() for a in catalog.items]
        # (1,2)-grams capture phrases like "java developer" / "data analyst".
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
        )
        self.matrix = self.vectorizer.fit_transform(self.docs)

    def search(self, query: str, k: int) -> list[tuple[Assessment, float]]:
        """Return up to k (assessment, score) pairs, best first.

        We rely on the catalog documents already carrying human-readable test-
        type words (see Assessment.search_document), so a query like
        "personality test" matches P-type items without query expansion — and a
        specific term like "java" stays sharp instead of being diluted.
        """
        if not query.strip():
            return []
        q_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(q_vec, self.matrix)[0]
        # argpartition for speed, then sort just the top slice.
        top_idx = np.argpartition(scores, -min(k, len(scores)))[-k:]
        ranked = sorted(top_idx, key=lambda i: scores[i], reverse=True)
        return [(self.catalog.items[i], float(scores[i]))
                for i in ranked if scores[i] > 0]
