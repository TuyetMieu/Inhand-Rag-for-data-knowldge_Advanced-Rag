"""So sánh BM25, vector, hybrid (RRF) và hybrid + rerank trên Qdrant: đáp án đúng có nằm trong top K không.

Luật: 10 câu của check_luat_search.py (đúng = chunk Điều/Khoản). Hồ sơ: 10 câu về KH002 (đúng = tài liệu).
Cần Qdrant đang chạy và đã chạy scripts/build_index.py. Embed câu hỏi trên CPU để chạy được cả khi
Ollama đang giữ GPU. Reranker chạy trên GPU nếu có (đặt RERANK_DEVICE=cpu để thử CPU).

Cách chạy (từ gốc repo):
    .venv\\Scripts\\python scripts/check_hybrid.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))

from check_luat_search import CASES as LUAT_CASES  # noqa: E402
from inhand_rag.index.qdrant_store import client  # noqa: E402
from inhand_rag.retrieve.hybrid import search  # noqa: E402
from inhand_rag.retrieve.rerank import CANDIDATES as RERANK_K, Reranker  # noqa: E402

TOP_K = 6
HOSO_CASES = [
    ("Số tiền đặt cọc của khách KH002 là bao nhiêu và trả bằng cách nào?", ["KH002-G1-011", "KH002-G1-012", "KH002-G2-003"]),
    ("Ai là người làm chứng khi ký hợp đồng đặt cọc?", ["KH002-G1-011"]),
    ("Thời hạn đặt cọc căn CT2-04 đến ngày nào?", ["KH002-G1-011", "KH002-G1-010"]),
    ("Đợt 2 khách phải thanh toán bao nhiêu tiền?", ["KH002-G3-006", "KH002-G3-009", "KH002-G2-032"]),
    ("Tiến độ thanh toán chia làm mấy đợt, mỗi đợt bao nhiêu phần trăm?", ["KH002-G2-032", "KH002-G1-006", "KH002-G3-001"]),
    ("Hoa hồng môi giới được tính như thế nào?", ["KH002-G1-018", "KH002-G1-019"]),
    ("Khách đăng ký vay ngân hàng bao nhiêu và ở ngân hàng nào?", ["KH002-G1-022", "KH002-G1-023", "KH002-G2-020", "KH002-G2-019"]),
    ("Diện tích đất và diện tích xây dựng của căn CT2-04 là bao nhiêu?", ["KH002-G2-033", "KH002-G2-030", "KH002-G1-004", "KH002-G1-003", "KH002-G1-011"]),
    ("Ai được phân cấp thẩm quyền ký hồ sơ giao dịch bên chủ đầu tư?", ["KH002-G2-028", "KH002-G2-027"]),
    ("Biên bản bàn giao nhà ghi nhận những thiết bị gì?", ["KH002-G4-007", "KH002-G4-008", "KH002-G2-035"]),
]


def rank_of(hits, gold, key):
    return next((r + 1 for r, h in enumerate(hits[:TOP_K]) if h[key] in gold), None)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    import torch
    from sentence_transformers import SentenceTransformer

    emb = SentenceTransformer(os.environ.get("EMBED_MODEL", "microsoft/harrier-oss-v1-0.6b"), device="cpu",
                              model_kwargs={"torch_dtype": torch.float32})
    cl = client()
    rr = Reranker(os.environ.get("RERANK_DEVICE"))
    modes = ("bm25", "dense", "hybrid", "rerank")
    lat = []
    for coll, cases, key in (("luat", LUAT_CASES, "id"), ("hoso", HOSO_CASES, "doc_id")):
        totals = dict.fromkeys(modes, 0)
        rr_sum = dict.fromkeys(modes, 0.0)  # tổng 1/hạng, để tính MRR
        print("== %s" % coll)
        for q, gold in cases:
            ranks = {}
            for m in modes:
                if m == "rerank":
                    hits = rr.rerank(q, search(cl, emb, coll, q, k=RERANK_K), top_n=TOP_K)
                    lat.append(rr.last_ms)
                else:
                    hits = search(cl, emb, coll, q, k=TOP_K, mode=m)
                ranks[m] = rank_of(hits, gold, key)
                totals[m] += ranks[m] is not None
                rr_sum[m] += 1 / ranks[m] if ranks[m] else 0
            print("  " + "  ".join("%s %-2s" % (m, ranks[m] or "-") for m in modes) + " | " + q)
        print("  KẾT QUẢ %s: " % coll + ", ".join("%s %d/%d" % (m, totals[m], len(cases)) for m in modes)
              + " (có đáp án trong top %d)" % TOP_K)
        print("  MRR %s: " % coll + ", ".join("%s %.2f" % (m, rr_sum[m] / len(cases)) for m in modes))
    lat = sorted(lat[1:])  # bỏ lần đầu (khởi động)
    print("Rerank %d ứng viên trên %s: trung vị %.0f ms, chậm nhất %.0f ms"
          % (RERANK_K, rr.device, lat[len(lat) // 2], lat[-1]))
    if rr.device == "cuda":
        import torch
        print("VRAM đỉnh của reranker: %.2f GB" % (torch.cuda.max_memory_allocated() / 2**30))
    return 0


if __name__ == "__main__":
    sys.exit(main())
