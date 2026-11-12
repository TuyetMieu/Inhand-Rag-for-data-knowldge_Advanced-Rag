"""Dựng lại hai collection Qdrant "luat" và "hoso" từ các file chunk.

Cần Qdrant đang chạy (xem README) và GPU trống khoảng 2 GB: tắt Ollama trước khi chạy.
Embed khoảng 6.000 chunk mất chừng 1,5–2 phút trên RTX 5070 Laptop.

Cách chạy (từ gốc repo):
    .venv\\Scripts\\python scripts/build_index.py            (cả hai)
    .venv\\Scripts\\python scripts/build_index.py hoso       (một collection)
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))

from inhand_rag.index import qdrant_store as qs  # noqa: E402
from inhand_rag.index import sparse  # noqa: E402


def main(names: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    import torch
    from sentence_transformers import SentenceTransformer

    cl = qs.client()
    cl.get_collections()  # báo lỗi sớm nếu Qdrant chưa chạy
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(os.environ.get("EMBED_MODEL", "microsoft/harrier-oss-v1-0.6b"), device=device,
                                model_kwargs={"torch_dtype": torch.float16} if device == "cuda" else {})
    model.max_seq_length = 1024
    for name in names:
        chunks = qs.load(name)
        texts = [qs.embed_text(c) for c in chunks]
        t = time.perf_counter()
        dense = model.encode(texts, batch_size=16, normalize_embeddings=True, show_progress_bar=True)
        t_emb = time.perf_counter() - t
        avgdl = sparse.avg_len(texts)
        qs.recreate(cl, name)
        qs.upsert(cl, name, chunks, dense, avgdl)
        qs.save_stats({name: {"avgdl": avgdl, "points": len(chunks)}})
        n = cl.count(name, exact=True).count
        print("%s: %d chunk, embed %.0fs trên %s, Qdrant có %d điểm" % (name, len(chunks), t_emb, device, n))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["luat", "hoso"]))
