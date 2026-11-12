"""Xếp hạng lại ứng viên bằng jina-reranker-v3.5 (0,6B, ra 27/07/2026, giấy phép CC BY-NC 4.0).

Model xếp hạng kiểu listwise: đưa câu hỏi và cả danh sách ứng viên vào một lượt chạy, mỗi đoạn được
chấm bằng độ tương đồng cosine với câu hỏi. Code của model (modeling.py, trust_remote_code) đã đọc:
chỉ dựng prompt và tính điểm, không gọi mạng.

Giấy phép không cho dùng thương mại: đủ cho demo; khi đưa vào sản phẩm phải mua giấy phép hoặc đổi sang
Qwen/Qwen3-Reranker-0.6B (Apache 2.0) qua biến môi trường RERANK_MODEL (chưa viết nhánh này).
"""
from __future__ import annotations

import os
import time

MODEL = os.environ.get("RERANK_MODEL", "jinaai/jina-reranker-v3.5")
MAX_DOC_CHARS = 1500  # chunk luật tối đa 3000 ký tự: cắt bớt cho nhanh
# Số ứng viên hybrid đưa vào reranker. Đo 12/11/2026 trên RTX 5070 8 GB, Granite đang nạp:
# 30 ứng viên ~1,9 s, VRAM 2,9 GB; 20 ứng viên ~1,0 s, VRAM 2,15 GB, MRR gần như bằng nhau.
CANDIDATES = int(os.environ.get("RERANK_K", "20"))


class Reranker:
    def __init__(self, device: str | None = None):
        import torch
        from transformers import AutoModel

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
        self.model = AutoModel.from_pretrained(MODEL, dtype=dtype, trust_remote_code=True).to(self.device).eval()
        self.last_ms = 0.0

    @staticmethod
    def doc_text(hit: dict) -> str:
        return hit["vi_tri"] + "\n" + hit["text"][:MAX_DOC_CHARS]

    def rerank(self, query: str, hits: list[dict], top_n: int = 6) -> list[dict]:
        if not hits:
            return []
        t = time.perf_counter()
        res = self.model.rerank(query, [self.doc_text(h) for h in hits], top_n=top_n)
        self.last_ms = 1000 * (time.perf_counter() - t)
        return [{**hits[int(r["index"])], "_rerank": float(r["relevance_score"])} for r in res]
