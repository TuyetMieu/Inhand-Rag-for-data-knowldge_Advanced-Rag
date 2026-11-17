"""Kiểm tra môi trường: torch nhận GPU, embed 1 câu tiếng Việt, ghi và tìm 1 điểm trong Qdrant.

Cách chạy (từ gốc repo, sau khi đã bật Qdrant):
    .venv\\Scripts\\python scripts/check_env.py

Model embedding được lưu trong .cache/huggingface của repo.
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))

EMBED_MODEL = os.environ.get("EMBED_MODEL", "microsoft/harrier-oss-v1-0.6b")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
COLLECTION = "env_check"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    import torch

    print("torch", torch.__version__, "| CUDA build", torch.version.cuda)
    if not torch.cuda.is_available():
        print("LỖI: torch không nhận GPU")
        return 1
    name = torch.cuda.get_device_name(0)
    free, total = torch.cuda.mem_get_info()
    print("GPU:", name, "| VRAM trống %.1f / %.1f GB" % (free / 1e9, total / 1e9))

    from sentence_transformers import SentenceTransformer

    t = time.perf_counter()
    model = SentenceTransformer(EMBED_MODEL, device="cuda", model_kwargs={"torch_dtype": torch.float16})
    print("Nạp %s trong %.1fs" % (EMBED_MODEL, time.perf_counter() - t))
    docs = [
        "Bên A đặt cọc bằng chuyển khoản trực tiếp CĐT 3.038.686.489 VNĐ; thời hạn đặt cọc 12/10/2026–22/10/2026.",
        "Nhà được bàn giao ngày 05/12/2027 ở trạng thái hoàn thiện thô.",
    ]
    query = "Instruct: Given a question, retrieve passages that answer the question\nQuery: Khách đặt cọc bao nhiêu tiền?"
    t = time.perf_counter()
    doc_vecs = model.encode(docs, normalize_embeddings=True)
    q_vec = model.encode([query], normalize_embeddings=True)[0]
    print("Embed xong trong %.2fs, số chiều %d" % (time.perf_counter() - t, len(q_vec)))
    print("VRAM PyTorch đang giữ: %.2f GB" % (torch.cuda.memory_allocated() / 1e9))

    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams

    client = QdrantClient(url=QDRANT_URL)
    print("Qdrant", client.info().version, "tại", QDRANT_URL)
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    client.create_collection(COLLECTION, vectors_config=VectorParams(size=len(q_vec), distance=Distance.COSINE))
    client.upsert(COLLECTION, points=[
        PointStruct(id=i, vector=v.tolist(), payload={"text": d}) for i, (d, v) in enumerate(zip(docs, doc_vecs))
    ])
    hits = client.query_points(COLLECTION, query=q_vec.tolist(), limit=2).points
    for h in hits:
        print("  điểm %.3f | %s" % (h.score, h.payload["text"][:70]))
    client.delete_collection(COLLECTION)

    ok = hits and hits[0].id == 0
    print("KẾT QUẢ:", "ĐẠT" if ok else "KHÔNG ĐẠT (câu về đặt cọc không đứng đầu)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
