"""Mở rộng chunk con thành chunk cha để LLM đọc đủ ngữ cảnh, bỏ cha trùng, giữ thứ tự xếp hạng.

- luat: cha là cả Điều (data/luat/dieu.jsonl). Điều quá dài (ví dụ Điều 3 Luật Đất đai, giải thích từ
  ngữ, hơn 10.000 ký tự) thì không đưa cả Điều mà giữ các khoản đã tìm được.
- hoso: cha là nhóm mục liền nhau của cùng tài liệu, tối đa 4.000 ký tự (data/hoso/kh002_parents.jsonl).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PARENT_FILES = {"luat": ROOT / "data" / "luat" / "dieu.jsonl", "hoso": ROOT / "data" / "hoso" / "kh002_parents.jsonl"}
MAX_PARENT_CHARS = 6000


@lru_cache(maxsize=None)
def parents(collection: str) -> dict[str, dict]:
    return {r["id"]: r for r in map(json.loads, PARENT_FILES[collection].open(encoding="utf-8"))}


def expand(collection: str, hits: list[dict]) -> list[dict]:
    """Trả về danh sách ngữ cảnh: {"id", "vi_tri", "text", "child_ids", ...metadata của cha}."""
    table = parents(collection)
    out: dict[str, dict] = {}
    for h in hits:
        p = table.get(h.get("parent_id"))
        if p is not None and len(p["text"]) <= MAX_PARENT_CHARS:
            key = p["id"]
            if key not in out:
                out[key] = {**p, "child_ids": []}
            out[key]["child_ids"].append(h["id"])
        else:
            # Cha quá dài hoặc không có: dùng chính chunk con, gộp các khoản cùng Điều vào một mục.
            key = (h.get("parent_id") or h["id"]) + "#con"
            if key not in out:
                out[key] = {**h, "id": key, "text": "", "child_ids": []}
            out[key]["text"] = (out[key]["text"] + "\n" + h["text"]).strip()
            out[key]["child_ids"].append(h["id"])
    return list(out.values())
