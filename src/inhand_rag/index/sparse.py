"""Vector thưa kiểu BM25 cho tiếng Việt, dùng làm nhánh từ khóa trong Qdrant.

Tiếng Việt viết theo âm tiết, một từ thường gồm 2–3 âm tiết ("chuyển nhượng"), nên lấy cả âm tiết lẫn cặp
âm tiết liền nhau. Mã và số giữ nguyên cả cụm ("ct2-04", "29/2023/qh15", "30.386.864.888") để tra đúng
mã căn, số hiệu văn bản, số tiền.

Phía tài liệu: trọng số tf của BM25 (k1, b) với độ dài trung bình của collection. Phía câu hỏi: mỗi
term trọng số 1. IDF do Qdrant tính (sparse vector với modifier IDF).
"""
from __future__ import annotations

import re
import unicodedata
import zlib
from collections import Counter

K1, B = 1.2, 0.75
WORD = re.compile(r"\w+", re.UNICODE)
COMPOUND = re.compile(r"\w+(?:[./\-]\w+)+", re.UNICODE)


def tokens(text: str) -> list[str]:
    t = unicodedata.normalize("NFC", text.lower())
    words = WORD.findall(t)
    out = list(words)
    out += ["%s_%s" % (a, b) for a, b in zip(words, words[1:])]
    out += COMPOUND.findall(t)
    return out


def _tid(tok: str) -> int:
    return zlib.crc32(tok.encode("utf-8")) & 0x7FFFFFFF


def doc_vector(text: str, avgdl: float) -> tuple[list[int], list[float]]:
    toks = tokens(text)
    n = len(toks) or 1
    tf = Counter(_tid(x) for x in toks)
    idx = sorted(tf)
    vals = [tf[i] * (K1 + 1) / (tf[i] + K1 * (1 - B + B * n / avgdl)) for i in idx]
    return idx, vals


def query_vector(text: str) -> tuple[list[int], list[float]]:
    idx = sorted({_tid(x) for x in tokens(text)})
    return idx, [1.0] * len(idx)


def avg_len(texts: list[str]) -> float:
    return sum(len(tokens(t)) for t in texts) / max(len(texts), 1)
