"""Truy hồi lai trên Qdrant: vector dày + BM25, gộp bằng RRF ngay trong Qdrant (Query API).

    hits = search(cl, embedder, "luat", "đặt cọc tối đa bao nhiêu", k=30)
    hits = search(cl, embedder, "hoso", "đợt 2 phải trả bao nhiêu", flt={"ma_ho_so": "KH002", "tranche": 2})

`mode` = "hybrid" (mặc định), "dense" hoặc "bm25" để so sánh.
"""
from __future__ import annotations

from qdrant_client import QdrantClient, models

from inhand_rag.index import sparse

INSTRUCT = {
    "luat": "Instruct: Given a question about Vietnamese real estate law, retrieve the legal provision that answers it\nQuery: ",
    "hoso": "Instruct: Given a question about a Vietnamese real estate transaction file, retrieve the document passage that answers it\nQuery: ",
}
PREFETCH = 30


def make_filter(flt: dict | None) -> models.Filter | None:
    if not flt:
        return None
    must = []
    for k, v in flt.items():
        if isinstance(v, (list, tuple, set)):
            must.append(models.FieldCondition(key=k, match=models.MatchAny(any=list(v))))
        else:
            must.append(models.FieldCondition(key=k, match=models.MatchValue(value=v)))
    return models.Filter(must=must)


def embed_query(embedder, collection: str, query: str) -> list[float]:
    return embedder.encode(INSTRUCT[collection] + query, normalize_embeddings=True).tolist()


def search(cl: QdrantClient, embedder, collection: str, query: str, k: int = 30,
           flt: dict | None = None, mode: str = "hybrid") -> list[dict]:
    f = make_filter(flt)
    idx, val = sparse.query_vector(query)
    sv = models.SparseVector(indices=idx, values=val)
    if mode == "bm25":
        res = cl.query_points(collection, query=sv, using="bm25", limit=k, query_filter=f, with_payload=True)
    elif mode == "dense":
        res = cl.query_points(collection, query=embed_query(embedder, collection, query), using="dense",
                              limit=k, query_filter=f, with_payload=True)
    else:
        dense = embed_query(embedder, collection, query)
        res = cl.query_points(
            collection,
            prefetch=[models.Prefetch(query=dense, using="dense", limit=max(PREFETCH, k), filter=f),
                      models.Prefetch(query=sv, using="bm25", limit=max(PREFETCH, k), filter=f)],
            query=models.FusionQuery(fusion=models.Fusion.RRF), limit=k, with_payload=True)
    return [{**p.payload, "_score": p.score} for p in res.points]
