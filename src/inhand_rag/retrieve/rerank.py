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
# Thiết bị mặc định là CPU: khi trả lời, GPU 8 GB dành cho Granite (5,8 GB ở num_ctx 6144, Windows giữ
# ~1 GB), chỉ còn ~1 GB, không đủ cho reranker (2,15 GB). Đo 12/11/2026: để reranker trên GPU làm Granite
# bị đẩy một phần sang CPU, bước trả lời từ ~9 s lên ~100 s. Đặt RERANK_DEVICE=cuda khi GPU còn trống.
DEVICE = os.environ.get("RERANK_DEVICE") or "cpu"
# Số ứng viên hybrid đưa vào reranker và độ dài mỗi đoạn. GPU (đo 12/11/2026): 20 ứng viên ~1,0 s,
# 30 ứng viên ~1,9 s, MRR gần như bằng nhau. CPU: 30 ứng viên x 1.500 ký tự mất ~33 s, nên rút còn 12 x 800.
CANDIDATES = int(os.environ.get("RERANK_K", "20" if DEVICE == "cuda" else "12"))
MAX_DOC_CHARS = int(os.environ.get("RERANK_DOC_CHARS", "1500" if DEVICE == "cuda" else "800"))


class Reranker:
    def __init__(self, device: str | None = None):
        import torch
        from transformers import AutoModel

        self.device = device or DEVICE
        if self.device == "cuda" and not torch.cuda.is_available():
            self.device = "cpu"
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
