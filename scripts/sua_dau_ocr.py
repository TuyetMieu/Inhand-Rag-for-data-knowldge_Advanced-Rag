"""Sửa dấu cho văn bản OCR trong data/ocr/<mã>/ và ghi data/ocr_sua/<mã>.txt.

Mỗi trang giữ một dòng đánh dấu "<<<trang FILE_TRANG>>>" để bộ tách Điều biết số trang.
Báo cáo cho từng văn bản: số chữ đã sửa, tỷ lệ âm tiết có trong từ vựng trước/sau, và tỷ lệ sai
trên nhóm từ có ư/ơ hay gặp (đo được vì dạng đúng và dạng sai đều xuất hiện).

Cách chạy (từ gốc repo):
    .venv\\Scripts\\python scripts/sua_dau_ocr.py
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from inhand_rag.ingest.corpus import build  # noqa: E402
from inhand_rag.ingest.sua_dau import TOKEN, DiacriticCorrector, _is_word  # noqa: E402

# (dạng sai thường gặp, dạng đúng) để đo trước/sau
PAIRS = [("tu", "tư"), ("đuợc", "được"), ("truờng", "trường"), ("nuớc", "nước"), ("thuong", "thương"),
         ("phuong", "phương"), ("dụ", "dự"), ("dung", "dụng"), ("đua", "đưa"), ("tuơng", "tương"),
         ("nguời", "người"), ("buớc", "bước"), ("huớng", "hướng"), ("thuờng", "thường")]


# Khối chữ ký số của Cổng thông tin Chính phủ ở trang đầu: chỉ xóa đúng cụm này, không xóa cả đoạn.
SIGNATURE = re.compile(r"Người ký\s*[:;].{0,200}?Thời gian ký\s*[:;]\s*[\d.,:\s+]{10,40}", re.I | re.S)


def pair_error(text: str) -> tuple[int, int]:
    words = Counter(w.lower() for w in TOKEN.findall(text) if _is_word(w))
    bad = sum(words[b] for b, _ in PAIRS)
    good = sum(words[g] for _, g in PAIRS)
    return bad, bad + good


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    # Học từ luật có text + mọi docx gõ máy (biểu mẫu, hồ sơ mô phỏng) để có vốn từ rộng ngoài lĩnh vực đất đai.
    train = build([ROOT.parent / "Form Data", ROOT.parent / "Mock Data", ROOT / "data" / "hoso" / "KH002"])
    corr = DiacriticCorrector(train)
    vocab = corr.uni
    out_dir = ROOT / "data" / "ocr_sua"
    out_dir.mkdir(parents=True, exist_ok=True)
    for doc_dir in sorted((ROOT / "data" / "ocr").iterdir()):
        pages = sorted(doc_dir.glob("*.txt"), key=lambda p: tuple(int(x) for x in p.stem.split("_")))
        if not pages:
            continue
        raw_parts, fixed_parts, all_changes = [], [], Counter()
        for p in pages:
            raw = SIGNATURE.sub(" ", p.read_text(encoding="utf-8"))
            fixed, changes = corr.correct(raw)
            all_changes.update(changes)
            raw_parts.append(raw)
            fixed_parts.append("<<<trang %s>>>\n%s" % (p.stem, fixed))
        raw_all, fixed_all = "\n".join(raw_parts), "\n".join(fixed_parts)
        (out_dir / (doc_dir.name + ".txt")).write_text(fixed_all, encoding="utf-8")

        def coverage(t):
            ws = [w.lower() for w in TOKEN.findall(t) if _is_word(w)]
            return 100 * sum(w in vocab for w in ws) / max(len(ws), 1), len(ws)

        cb, n = coverage(raw_all)
        ca, _ = coverage(re.sub(r"<<<trang [\d_]+>>>", "", fixed_all))
        pb, pt = pair_error(raw_all)
        pa, _ = pair_error(fixed_all)
        print("%-12s %3d trang, %6d âm tiết | sửa %5d chữ | trong từ vựng %.1f%% -> %.1f%% | nhóm ư/ơ sai %d/%d (%.0f%%) -> %d (%.0f%%)"
              % (doc_dir.name, len(pages), n, sum(all_changes.values()), cb, ca, pb, pt, 100 * pb / max(pt, 1), pa, 100 * pa / max(pt, 1)))
        print("    hay sửa nhất:", ", ".join("%s→%s ×%d" % (a, b, c) for (a, b), c in all_changes.most_common(12)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
