from datetime import datetime

import numpy as np
import pytest

from app.models import Transaction
from app.retriever import RetrieverError, text_for, Retriever, build_retriever


def _tx(row, amount, payee):
    return Transaction(row=row, date=datetime(2024, 1, row, 9, 0), description="d",
                       payee=payee, amount=amount, channel="card")


def _fake_embedder(texts):
    """Deterministic stub: hash the amount sign to two distinct vectors."""
    return [np.array([1.0, 0.0]) if "$" not in t and "-" not in t else np.array([0.0, 1.0]) for t in texts]


def test_text_for_includes_traceable_fields():
    t = _tx(7, -42.5, "Market")
    s = text_for(t)
    assert "7" in s and "42.5" in s and "Market" in s


def test_build_retriever_and_find_similar():
    txs = [
        _tx(1, -10.0, "Market"),
        _tx(2, -10.5, "Market"),   # similar to row 1
        _tx(3, -9.8, "Market"),    # similar to row 1
        _tx(4, -3000.0, "Wire Co"),
    ]
    emb = {text_for(t): np.array([1.0, 0.0]) if t.amount > -100 else np.array([1.0, 1.0]) for t in txs}

    def stub(texts):
        return [emb[t] for t in texts]

    r = build_retriever(txs, embed_fn=stub)
    assert r is not None
    # row 1 should match rows 3, 2 (small amounts) — not row 4
    similar = [t.row for t, _ in r.similar(txs[0], k=2)]
    assert 3 in similar and 2 in similar


def test_similar_never_returns_self():
    txs = [_tx(i, float(-i * 10), "P") for i in range(1, 6)]
    r = build_retriever(txs, embed_fn=_fake_embedder)
    for t in txs:
        assert all(other.row != t.row for other, _ in r.similar(t, k=4))


def test_build_retriever_needs_embed_fn_or_api_key():
    with pytest.raises(RetrieverError):
        build_retriever([_tx(1, -1, "P")], embed_fn=None, api_key=None)