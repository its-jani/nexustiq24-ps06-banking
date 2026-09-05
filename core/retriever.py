from collections.abc import Callable

from core.config import REQUEST_TIMEOUT
from core.models import Transaction


class RetrieverError(RuntimeError):
    pass


def text_for(tx: Transaction) -> str:
    """A searchable text fingerprint of a transaction; includes row for traceability."""
    return (
        f"row {tx.row}: {tx.date:%Y-%m-%d %H:%M} | {tx.description} | {tx.payee} "
        f"| {'outflow' if tx.amount < 0 else 'inflow'} {abs(tx.amount):,.2f} | {tx.channel}"
    )


class Retriever:
    """Local FAISS index of this customer's history, so the LLM can compare a
    flagged transaction against genuinely similar historical ones."""

    def __init__(self, index, transactions: list[Transaction], vectors, model: str):
        self._index = index
        self._txs = transactions
        self._vectors = vectors
        self._position = {t.row: i for i, t in enumerate(transactions)}
        self.model = model

    def similar(self, tx: Transaction, k: int = 5) -> list[tuple[Transaction, float]]:
        """Top-k most similar OTHER transactions (never the query itself)."""
        import numpy as np

        self_pos = self._position[tx.row]
        scores, positions = self._index.search(self._vectors[self_pos][None, :], k + 1)
        hits = []
        for score, pos in zip(scores[0], positions[0]):
            if pos < 0 or pos >= len(self._txs) or pos == self_pos:
                continue
            hits.append((self._txs[pos], float(score)))
            if len(hits) == k:
                return hits
        return hits


def build_retriever(
    txs: list[Transaction],
    embed_fn: Callable | None = None,
    api_key: str | None = None,
    model: str = "gemini-embedding-001",
) -> Retriever:
    """Build a local FAISS index over the customer's history.

    `embed_fn` is the test seam: (texts: list[str]) -> list[list[float] | np.ndarray].
    Without one, embeds via the Gemini API (gemini-embedding-001), which requires
    an API key.
    """
    import numpy as np

    if embed_fn is None:
        if not api_key:
            raise RetrieverError("retriever needs an embedding function or a GEMINI_API_KEY")
        from google import genai  # deferred: avoid heavy import until needed
        from google.genai import types

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT),
        )

        def embed_fn(texts):
            # batch to bound per-request size for large histories
            return _batch_embed(client, model, texts)

    texts = [text_for(t) for t in txs]
    vectors = np.asarray(list(embed_fn(texts)), dtype="float32")
    if vectors.ndim != 2:
        raise RetrieverError("embedding function returned invalid shape")

    import faiss

    index = faiss.IndexFlatIP(vectors.shape[1])
    vectors_norm = vectors.copy()
    faiss.normalize_L2(vectors_norm)
    index.add(vectors_norm)

    r = Retriever(index, txs, vectors_norm, model)
    return r


def _batch_embed(client, model: str, texts: list[str], batch_size: int = 100) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        resp = client.models.embed_content(model=model, contents=list(texts[start:start + batch_size]))
        vectors.extend(list(e.values) for e in resp.embeddings)
    return vectors