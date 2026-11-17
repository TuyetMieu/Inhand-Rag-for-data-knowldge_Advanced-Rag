"""Tra trực tiếp điều luật khi câu hỏi nêu rõ "Điều N [khoản M] <tên luật>".

Đây là đường tắt trước truy hồi ngữ nghĩa: trích dẫn tường minh thì lấy đúng chunk theo
metadata, không cần tìm kiếm vector.
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# Tên gọi thường gặp -> mã văn bản trong schemas/luat_catalog.csv
ALIASES = {
    "LKDBDS-2023": ["luat kinh doanh bat dong san", "luat kd bds", "luat kdbds", "29/2023/qh15"],
    "LNO-2023": ["luat nha o", "27/2023/qh15"],
    "LDD-2024": ["luat dat dai", "31/2024/qh15"],
    "L43-2024": ["luat 43", "43/2024/qh15", "luat sua doi"],
}
RE_DIEU = re.compile(r"\bđiều\s+(\d{1,3})\b(?:\s*,?\s*khoản\s+(\d{1,3}))?", re.I)
RE_KHOAN_TRUOC = re.compile(r"\bkhoản\s+(\d{1,3})\s+điều\s+(\d{1,3})\b", re.I)


def _ascii(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower()).replace("đ", "d")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


@lru_cache(maxsize=1)
def _load(luat_dir: str):
    d = Path(luat_dir)
    dieu = {x["id"]: x for x in map(json.loads, (d / "dieu.jsonl").open(encoding="utf-8"))}
    chunks = {}
    for x in map(json.loads, (d / "chunks.jsonl").open(encoding="utf-8")):
        chunks.setdefault((x["van_ban"], x["dieu"], x["khoan"] or 0), []).append(x)
    return dieu, chunks


def parse_citation(question: str) -> list[tuple[str, int, int | None]]:
    """Trả về [(mã văn bản, điều, khoản hoặc None)] tìm thấy trong câu hỏi."""
    q = _ascii(question)
    van_ban = [ma for ma, names in ALIASES.items() if any(n in q for n in names)]
    refs = []
    for m in RE_KHOAN_TRUOC.finditer(question):
        refs.append((int(m.group(2)), int(m.group(1))))
    for m in RE_DIEU.finditer(question):
        ref = (int(m.group(1)), int(m.group(2)) if m.group(2) else None)
        if not any(r[0] == ref[0] for r in refs):
            refs.append(ref)
    return [(vb, dieu, khoan) for vb in van_ban for dieu, khoan in refs]


def lookup(question: str, luat_dir: str | Path = ROOT / "data" / "luat") -> list[dict]:
    """Chunk khớp trích dẫn: có khoản thì trả chunk của khoản, không có thì trả cả Điều."""
    dieu, chunks = _load(str(luat_dir))
    out = []
    for vb, so_dieu, khoan in parse_citation(question):
        if khoan is not None:
            out += chunks.get((vb, so_dieu, khoan), [])
        elif "%s-D%d" % (vb, so_dieu) in dieu:
            out.append(dieu["%s-D%d" % (vb, so_dieu)])
    return out
