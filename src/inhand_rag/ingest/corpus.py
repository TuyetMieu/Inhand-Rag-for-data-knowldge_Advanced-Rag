"""Gom văn bản tiếng Việt sạch (gõ máy, không qua OCR) để học từ vựng cho bộ sửa dấu.

Nguồn: các luật đã tách từ PDF có text (data/luat/chunks.jsonl) và mọi file .docx trong
các thư mục được truyền vào (biểu mẫu, hồ sơ mô phỏng). Kết quả lưu đệm ở data/ocr_sua/corpus.txt.
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "data" / "ocr_sua" / "corpus.txt"


def docx_text(path: Path) -> str:
    try:
        xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8", "ignore")
    except (zipfile.BadZipFile, KeyError, OSError):
        return ""
    paras = ["".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p)) for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)]
    return "\n".join(p for p in paras if p.strip())


def build(docx_dirs: list[Path], use_cache: bool = True) -> list[str]:
    if use_cache and CACHE.exists():
        return CACHE.read_text(encoding="utf-8").split("\n\f\n")
    texts = [json.loads(l)["text"] for l in (ROOT / "data" / "luat" / "chunks.jsonl").open(encoding="utf-8")]
    seen = set()
    for d in docx_dirs:
        for p in Path(d).rglob("*.docx"):
            if p.name.startswith("~$"):
                continue
            t = docx_text(p)
            if t and t not in seen:  # nhiều hồ sơ mô phỏng dùng chung biểu mẫu, bỏ bản trùng
                seen.add(t)
                texts.append(t)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text("\n\f\n".join(texts), encoding="utf-8")
    return texts
