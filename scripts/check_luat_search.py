"""Thử tìm điều luật bằng câu hỏi tự nhiên (chỉ dùng vector, chưa có BM25 và rerank).

Embed mọi chunk trong data/luat/chunks.jsonl (kèm tiêu đề vị trí), rồi đo đáp án đúng có nằm
trong top K không. Dùng để kiểm cách tách chunk trước khi dựng chỉ mục thật trong Qdrant.

Cách chạy (từ gốc repo, GPU trống khoảng 1,5 GB):
    .venv\\Scripts\\python scripts/check_luat_search.py
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))
TOP_K = 6
INSTRUCT = "Instruct: Given a question about Vietnamese real estate law, retrieve the legal provision that answers it\nQuery: "

# (câu hỏi, các chunk được coi là đúng)
CASES = [
    ("Chủ đầu tư được thu tiền đặt cọc tối đa bao nhiêu khi bán nhà hình thành trong tương lai?", ["LKDBDS-2023-D23-K5"]),
    ("Trước khi bàn giao nhà, chủ đầu tư được thu tối đa bao nhiêu phần trăm giá trị hợp đồng?", ["LKDBDS-2023-D25-K1"]),
    ("Khi người mua chưa được cấp sổ hồng thì bên bán được thu tối đa bao nhiêu?", ["LKDBDS-2023-D25-K3"]),
    ("Sau khi bàn giao nhà bao lâu thì chủ đầu tư phải nộp hồ sơ xin cấp giấy chứng nhận cho người mua?", ["LKDBDS-2023-D17-K3"]),
    # Điều 17 khoản 4 cấm ủy quyền ký cho mọi bất động sản trong dự án; Điều 23 khoản 4 điểm d nhắc lại cho nhà hình thành trong tương lai.
    ("Chủ đầu tư có được ủy quyền cho đại lý ký hợp đồng mua bán nhà hình thành trong tương lai không?", ["LKDBDS-2023-D17-K4", "LKDBDS-2023-D23-K4"]),
    ("Nhà ở hình thành trong tương lai phải có điều kiện gì mới được đưa vào kinh doanh?", ["LKDBDS-2023-D24-K1", "LKDBDS-2023-D24-K2", "LKDBDS-2023-D24-K3"]),
    ("Ngân hàng bảo lãnh nghĩa vụ tài chính của chủ đầu tư khi bán nhà hình thành trong tương lai thế nào?", ["LKDBDS-2023-D26-K1", "LKDBDS-2023-D26-K2"]),
    ("Luật Kinh doanh bất động sản 2023 có hiệu lực từ ngày nào?", ["LKDBDS-2023-D82-K1"]),
    ("Người nước ngoài có được mua nhà ở tại Việt Nam không?", ["LNO-2023-D17-K1", "LNO-2023-D17-K2", "LNO-2023-D18-K1", "LNO-2023-D19-K1"]),
    ("Thời hạn sở hữu căn hộ chung cư là bao lâu?", ["LNO-2023-D58-K1", "LNO-2023-D58-K2", "LNO-2023-D58-K3"]),
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    import torch
    from sentence_transformers import SentenceTransformer

    chunks = [json.loads(l) for l in (ROOT / "data" / "luat" / "chunks.jsonl").open(encoding="utf-8")]
    ids = [c["id"] for c in chunks]
    for _, gold in CASES:
        missing = [g for g in gold if g not in ids]
        if missing:
            print("CẢNH BÁO: đáp án không có trong chunks:", missing)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(os.environ.get("EMBED_MODEL", "microsoft/harrier-oss-v1-0.6b"), device=device,
                                model_kwargs={"torch_dtype": torch.float16} if device == "cuda" else {})
    # Chunk tối đa 3000 ký tự (~900 token); chặn 1024 token để một chunk dài bất thường không làm tràn VRAM.
    model.max_seq_length = 1024
    t = time.perf_counter()
    docs = model.encode([c["vi_tri"] + "\n" + c["text"] for c in chunks], batch_size=16,
                        normalize_embeddings=True, convert_to_tensor=True, show_progress_bar=False)
    print("Embed %d chunk trong %.1fs trên %s" % (len(chunks), time.perf_counter() - t, device))
    qs = model.encode([INSTRUCT + q for q, _ in CASES], normalize_embeddings=True, convert_to_tensor=True)
    scores = qs @ docs.T
    hit = 0
    for (q, gold), row in zip(CASES, scores):
        top = [ids[i] for i in row.topk(TOP_K).indices.tolist()]
        rank = next((r + 1 for r, i in enumerate(top) if i in gold), None)
        hit += rank is not None
        print("%s hạng %s | %s" % ("ĐẠT " if rank else "TRƯỢT", rank or "-", q))
        if not rank:
            print("      top: %s" % ", ".join(top))
    print("KẾT QUẢ: %d/%d câu có đáp án trong top %d (chỉ vector)" % (hit, len(CASES), TOP_K))
    return 0


if __name__ == "__main__":
    sys.exit(main())
