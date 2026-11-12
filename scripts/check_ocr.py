"""Thử OCR vài trang của một văn bản luật dạng scan và ước lượng chất lượng tiếng Việt.

Chưa có bản text chuẩn để so, nên chất lượng được ước lượng bằng tỷ lệ âm tiết OCR ra
có xuất hiện trong từ vựng của 4 luật đã tách sạch (data/luat/chunks.jsonl). Âm tiết sai dấu
("đẩu", "quỵ"...) thường không có trong từ vựng nên kéo tỷ lệ xuống.

Cách chạy (từ gốc repo):
    .venv\\Scripts\\python scripts/check_ocr.py "..\\Dataset Luật\\nghị định 96_2024_NĐ-CP.pdf" 1-5
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / ".cache" / "easyocr"
WORD = re.compile(r"[A-Za-zÀ-ỹĐđ]+")


def vocab() -> set[str]:
    words = set()
    for line in (ROOT / "data" / "luat" / "chunks.jsonl").open(encoding="utf-8"):
        words.update(w.lower() for w in WORD.findall(json.loads(line)["text"]))
    return words


def main(pdf: str, pages: str) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    import easyocr
    import numpy as np
    import pymupdf
    import torch

    a, b = (int(x) for x in pages.split("-"))
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    reader = easyocr.Reader(["vi"], gpu=torch.cuda.is_available(), model_storage_directory=str(MODEL_DIR),
                            user_network_directory=str(MODEL_DIR), verbose=False)
    known = vocab()
    doc = pymupdf.open(pdf)
    out_dir = ROOT / "data" / "ocr_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    tot_ok = tot = 0
    for p in range(a - 1, min(b, len(doc))):
        pix = doc[p].get_pixmap(dpi=300)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        t = time.perf_counter()
        lines = reader.readtext(img, detail=0, paragraph=True)
        text = "\n".join(lines)
        words = [w.lower() for w in WORD.findall(text)]
        ok = sum(w in known for w in words)
        tot_ok += ok
        tot += len(words)
        (out_dir / ("trang_%03d.txt" % (p + 1))).write_text(text, encoding="utf-8")
        print("Trang %d: %d âm tiết, %.1f%% có trong từ vựng, %.1fs" % (p + 1, len(words), 100 * ok / max(len(words), 1), time.perf_counter() - t))
        print("   " + re.sub(r"\s+", " ", text)[:300])
    rate = 100 * tot_ok / max(tot, 1)
    print("KẾT QUẢ: %.1f%% âm tiết có trong từ vựng (%d/%d). Văn bản OCR lưu ở %s" % (rate, tot_ok, tot, out_dir))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
