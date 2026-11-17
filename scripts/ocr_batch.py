"""OCR toàn bộ các văn bản luật dạng scan trong schemas/luat_catalog.csv.

Mỗi trang ghi một file data/ocr/<mã>/<số thứ tự file>_<trang>.txt; chạy lại thì bỏ qua trang đã có,
nên dừng giữa chừng không mất công. Lưu nguyên kết quả OCR, không lọc gì: OCR gộp cả trang thành
một đoạn, nên lọc theo đoạn có thể xóa mất cả trang. Khối chữ ký số được bỏ ở bước sửa dấu
(scripts/sua_dau_ocr.py), chỉ xóa đúng cụm "Người ký: ... Thời gian ký: ...".

Cách chạy (từ gốc repo):
    .venv\\Scripts\\python scripts/ocr_batch.py "..\\Dataset Luật"
"""
import csv
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / ".cache" / "easyocr"


def main(base_dir: str) -> int:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    import easyocr
    import numpy as np
    import pymupdf
    import torch

    reader = easyocr.Reader(["vi"], gpu=torch.cuda.is_available(), model_storage_directory=str(MODEL_DIR),
                            user_network_directory=str(MODEL_DIR), verbose=False)
    rows = [r for r in csv.DictReader((ROOT / "schemas" / "luat_catalog.csv").open(encoding="utf-8"))
            if r["dinh_dang"] == "pdf_scan"]
    total_pages = sum(len(pymupdf.open(Path(base_dir) / f)) for r in rows for f in r["files"].split(";"))
    done = 0
    start = time.perf_counter()
    for r in rows:
        out = ROOT / "data" / "ocr" / r["ma"]
        out.mkdir(parents=True, exist_ok=True)
        for fi, f in enumerate(r["files"].split(";"), start=1):
            doc = pymupdf.open(Path(base_dir) / f)
            for p in range(len(doc)):
                target = out / ("%d_%03d.txt" % (fi, p + 1))
                done += 1
                if target.exists():
                    continue
                pix = doc[p].get_pixmap(dpi=300)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                paras = reader.readtext(img, detail=0, paragraph=True)
                target.write_text("\n".join(paras), encoding="utf-8")
                if done % 25 == 0:
                    el = time.perf_counter() - start
                    print("%s: %d/%d trang, %.0f giây" % (r["ma"], done, total_pages, el))
        print("XONG %s" % r["ma"])
    print("HOÀN TẤT %d trang trong %.0f giây" % (total_pages, time.perf_counter() - start))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
