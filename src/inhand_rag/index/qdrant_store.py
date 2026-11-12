"""Hai collection Qdrant "luat" và "hoso": vector dày (harrier 1024 chiều) + vector thưa BM25.

Mỗi điểm là một chunk con; payload giữ toàn bộ metadata của chunk (van_ban/dieu/khoan hoặc
ma_ho_so/doc_type/stage/tranche...) để lọc. Id điểm là uuid5 của id chunk nên ghi lại không bị trùng.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from qdrant_client import QdrantClient, models

from inhand_rag.index import sparse

ROOT = Path(__file__).resolve().parents[3]
DIM = 1024
NS = uuid.UUID("6f1c2b1e-6a52-4c7e-9a7e-5b1f3e8f0a11")
SOURCES = {
    "luat": ROOT / "data" / "luat" / "chunks.jsonl",
    "hoso": ROOT / "data" / "hoso" / "kh002_chunks.jsonl",
}
INDEXES = {
    "luat": {"van_ban": "keyword", "dieu": "integer", "khoan": "integer", "nguon_text": "keyword"},
    "hoso": {"ma_ho_so": "keyword", "doc_id": "keyword", "doc_type": "keyword", "stage": "integer",
             "tranche": "integer", "branch": "keyword", "required": "keyword"},
}
STATS = ROOT / "data" / "index_stats.json"  # avgdl của BM25 cho từng collection


def client() -> QdrantClient:
    return QdrantClient(url=os.environ.get("QDRANT_URL", "http://localhost:6333"), timeout=60)


def load(name: str) -> list[dict]:
    return [json.loads(l) for l in SOURCES[name].open(encoding="utf-8")]


def embed_text(c: dict) -> str:
    """Văn bản đem đi embed/BM25: tiêu đề vị trí + nội dung."""
    return c["vi_tri"] + "\n" + c["text"]


def point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(NS, chunk_id))


def recreate(cl: QdrantClient, name: str) -> None:
    if cl.collection_exists(name):
        cl.delete_collection(name)
    cl.create_collection(
        name,
        vectors_config={"dense": models.VectorParams(size=DIM, distance=models.Distance.COSINE)},
        sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
    )
    kinds = {"keyword": models.PayloadSchemaType.KEYWORD, "integer": models.PayloadSchemaType.INTEGER}
    for field, kind in INDEXES[name].items():
        cl.create_payload_index(name, field, field_schema=kinds[kind])


def upsert(cl: QdrantClient, name: str, chunks: list[dict], dense, avgdl: float, batch: int = 128) -> None:
    for s in range(0, len(chunks), batch):
        pts = []
        for c, v in zip(chunks[s:s + batch], dense[s:s + batch]):
            idx, val = sparse.doc_vector(embed_text(c), avgdl)
            pts.append(models.PointStruct(id=point_id(c["id"]), payload=c,
                                          vector={"dense": list(map(float, v)),
                                                  "bm25": models.SparseVector(indices=idx, values=val)}))
        cl.upsert(name, pts, wait=True)


def save_stats(stats: dict) -> None:
    old = json.loads(STATS.read_text(encoding="utf-8")) if STATS.exists() else {}
    old.update(stats)
    STATS.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding="utf-8")
