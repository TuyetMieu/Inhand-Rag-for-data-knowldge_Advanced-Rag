"""Chạy pipeline trên câu vàng (eval/golden.jsonl), câu kịch bản A và câu ngoài phạm vi.

Đo cho từng câu: nguồn được chọn, mã trích dẫn có khớp nguồn vàng không, số dòng bị verify loại,
thời gian từng bước. Câu ngoài phạm vi phải bị từ chối.
Cần Qdrant và Ollama (granite4.2:8b) đang chạy.

    .venv\\Scripts\\python -W ignore scripts/check_graph.py
    .venv\\Scripts\\python -W ignore scripts/check_graph.py --answers   (in cả câu trả lời)
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from inhand_rag.graph import ask, prompts  # noqa: E402
from inhand_rag.graph.nodes import normalize_cite, resources  # noqa: E402
from inhand_rag.retrieve.rerank import CANDIDATES as RERANK_K  # noqa: E402

EXTRA = [  # (id, câu hỏi, nguồn vàng)
    ("a1", "Đợt 2 KH002 bao nhiêu là vốn tự có, bao nhiêu là vốn vay?", ["KH002-G3-006", "KH002-G3-009", "KH002-G2-032"]),
    ("a2", "Ai là người làm chứng khi ký hợp đồng đặt cọc của KH002?", ["KH002-G1-011"]),
    ("a3", "Biên bản bàn giao căn CT2-04 ghi nhận những thiết bị gì?", ["KH002-G4-007", "KH002-G4-008"]),
]
OUT_OF_SCOPE = [
    ("o1", "Thời tiết Hà Nội ngày mai thế nào?"),
    ("o2", "Viết giúp tôi một bài thơ về mùa thu."),
    ("o3", "Giá vàng SJC hôm nay bao nhiêu?"),
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", action="store_true")
    a = ap.parse_args()
    golden = [json.loads(x) for x in (ROOT / "eval" / "golden.jsonl").open(encoding="utf-8")]
    cases = [(g["id"], g["cau_hoi"], g["nguon"]) for g in golden] + EXTRA
    t = time.perf_counter()
    r = resources()
    m = r.llm_info
    print("Nạp model: %.1fs | Granite %s: %.2f GB, trên GPU %.2f GB, ngữ cảnh %s | reranker: %s" % (
        time.perf_counter() - t, m.get("name", "?"), m.get("size", 0) / 2**30, m.get("size_vram", 0) / 2**30,
        m.get("context_length", "?"), "%s, %d ứng viên" % (r.rr.device, RERANK_K) if r.rr else "tắt"))
    if m.get("size") and m.get("size_vram", 0) < m["size"]:
        print("CẢNH BÁO: Granite không nằm trọn trên GPU, trả lời sẽ rất chậm. Đóng bớt ứng dụng dùng GPU.")

    hit = refused = removed = 0
    totals = []
    steps: dict[str, list[float]] = {}
    for cid, q, gold in cases:
        try:
            out = ask(q)
        except Exception as e:  # một câu lỗi không dừng cả lượt đo
            print("%-3s LỖI %s | %s" % (cid, e, q))
            continue
        for k, v in out["timing"].items():
            steps.setdefault(k, []).append(v / 1000)
        gold_keys = {normalize_cite(x) for x in gold}
        got = [c["key"] for c in out["citations"]]
        ok = bool(gold_keys & set(got))
        hit += ok
        refused += out["answer"].startswith(prompts.NOT_ENOUGH)
        removed += len(out.get("removed", []))
        total = sum(out["timing"].values()) / 1000
        totals.append(total)
        print("%-3s %-6s %s trích %d/%d vàng, bỏ %d dòng, %4.1fs | %s" % (
            cid, out["nguon"], "ĐÚNG" if ok else "sai ", len(gold_keys & set(got)), len(gold_keys),
            len(out.get("removed", [])), total, q))
        if not ok:
            print("      trích: %s | vàng: %s" % (", ".join(got) or "-", ", ".join(sorted(gold_keys))))
        if a.answers:
            print("      " + out["answer"].replace("\n", "\n      "))
            for line in out.get("removed", []):
                print("      ĐÃ BỎ: " + line)
    oos_ok = 0
    for cid, q in OUT_OF_SCOPE:
        out = ask(q)
        ok = out["answer"] in (prompts.OUT_OF_SCOPE,) or out["answer"].startswith(prompts.NOT_ENOUGH)
        oos_ok += ok
        print("%-3s %-13s %s %4.1fs | %s" % (cid, out["nguon"], "TỪ CHỐI" if ok else "TRẢ LỜI (sai)",
                                            sum(out["timing"].values()) / 1000, q))
    totals.sort()
    print("\nKẾT QUẢ: trích đúng ít nhất 1 nguồn vàng %d/%d; trả 'không đủ căn cứ' %d; dòng bị verify loại %d; "
          "từ chối câu ngoài phạm vi %d/%d" % (hit, len(cases), refused, removed, oos_ok, len(OUT_OF_SCOPE)))
    print("Thời gian mỗi câu: trung vị %.1fs, chậm nhất %.1fs" % (totals[len(totals) // 2], totals[-1]))
    print("Trung bình từng bước: " + ", ".join("%s %.1fs" % (k, sum(v) / len(v)) for k, v in steps.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
