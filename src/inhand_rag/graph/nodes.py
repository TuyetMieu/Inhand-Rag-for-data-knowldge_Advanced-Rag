"""Các node của đồ thị trả lời (xem graph.py để biết thứ tự).

① understand  LLM phân loại nguồn (hoso / luat / ca_hai / ngoai_pham_vi), viết câu hỏi độc lập
               và truy vấn pháp lý riêng cho collection luat.
② retrieve    hybrid (vector + BM25, RRF) trên Qdrant, lọc theo mã hồ sơ; câu hỏi nêu thẳng
               "Điều N Luật X" thì lấy đúng Điều đó (citation.lookup) và ghim lên đầu.
③ rerank      jina-reranker-v3.5 trên GPU, giữ 6 (hoặc 4 mỗi nguồn khi hỏi cả hai).
④ expand      đổi chunk con thành chunk cha, gắn mã trích dẫn, cắt theo ngân sách ký tự.
⑤ answer      LLM trả lời, mỗi ý kèm [mã nguồn]; tài liệu không đủ thì trả câu "Không đủ căn cứ…".
⑥ grade       (cạnh điều kiện sau answer) không đủ căn cứ thì rewrite truy vấn, tìm lại (tối đa 1 lần),
               vẫn không đủ thì từ chối. Bản đầu chấm bằng một lượt LLM riêng trước answer, tốn 3,7 s mỗi
               câu (đọc lại toàn bộ tài liệu), nên gộp vào answer.
⑦ verify      code kiểm từng dòng: mã nguồn không có trong tài liệu, hoặc nêu "Điều N" mà trích Điều khác,
               thì bỏ dòng đó; dòng cuối bị cắt do hết token cũng bỏ.
"""
from __future__ import annotations

import json
import os
import re
import time
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import TypedDict

from inhand_rag import llm
from inhand_rag.graph import prompts as P
from inhand_rag.retrieve import citation, parent
from inhand_rag.retrieve.hybrid import INSTRUCT, search
from inhand_rag.retrieve.rerank import CANDIDATES

ROOT = Path(__file__).resolve().parents[3]
EMBED_MODEL = os.environ.get("EMBED_MODEL", "microsoft/harrier-oss-v1-0.6b")
MA_HO_SO = os.environ.get("MA_HO_SO", "KH002")  # hồ sơ mặc định khi câu hỏi không nêu mã
TOP_N = 6  # số chunk giữ sau rerank khi hỏi một nguồn
TOP_N_EACH = 4  # mỗi nguồn khi hỏi cả hai
# Granite chạy với num_ctx 6144 (llm.LLM_NUM_CTX). Đo 12/11/2026: tiếng Việt khoảng 2 ký tự/token
# (14.000 ký tự đã thành 8.323 token). 9.000 ký tự ~4.500 token, chừa ~1.600 cho prompt và câu trả lời.
MAX_CONTEXT_CHARS = int(os.environ.get("MAX_CONTEXT_CHARS", "9000"))
# Mặc định TẮT rerank khi trả lời. Đo 12/11/2026 (15 câu, Granite trọn GPU): reranker trên CPU thêm 8,9 s
# mỗi câu (trung vị 22,9 s so với 14,7 s) mà số câu trích đúng nguồn vàng như nhau (7/15). GPU 8 GB không
# đủ chỗ cho reranker cạnh Granite. Bật lại: RERANK=on (CPU) hoặc thêm RERANK_DEVICE=cuda trên GPU lớn hơn.
USE_RERANK = os.environ.get("RERANK", "off") == "on"
ANSWER_MAX_TOKENS = 350  # Granite sinh ~47 token/s trên RTX 5070 Laptop: 350 token ~7,5 s
# Từ thường ngày -> từ trong văn bản luật, áp vào truy vấn luật (LLM đôi khi vẫn giữ từ thường ngày).
LEGAL_TERMS = {
    "sổ hồng": "giấy chứng nhận quyền sử dụng đất, quyền sở hữu nhà ở",
    "sổ đỏ": "giấy chứng nhận quyền sử dụng đất",
    "nhà đang xây": "nhà ở hình thành trong tương lai",
}
RE_HOI_MAU = re.compile(r"\b(mẫu|phụ lục)\b", re.I)
MAX_REWRITES = 1
SOURCES = {"hoso": ("hoso",), "luat": ("luat",), "ca_hai": ("hoso", "luat")}
RE_MA_HO_SO = re.compile(r"\bKH\d{3,}\b")


class State(TypedDict, total=False):
    question: str
    history: list[dict]  # các lượt trước: {"role": "user" | "assistant", "content": str}
    nguon: str
    cau_hoi: str
    ma_ho_so: str
    queries: dict[str, str]  # truy vấn theo collection
    hits: dict[str, list[dict]]
    pinned: list[dict]
    ranked: dict[str, list[dict]]
    contexts: list[dict]
    rewrites: int
    raw_answer: str
    truncated: bool  # câu trả lời bị cắt vì hết max_tokens
    answer: str
    citations: list[dict]
    removed: list[str]
    timing: dict[str, float]


@lru_cache(maxsize=1)
def resources() -> SimpleNamespace:
    """Nạp model một lần. Nạp Granite vào VRAM TRƯỚC: Ollama chia lớp GPU/CPU theo VRAM trống lúc nạp,
    nạp sau model khác thì Granite bị đẩy một phần sang CPU. Embedding và reranker mặc định chạy CPU."""
    os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))
    os.environ.setdefault("HF_HUB_OFFLINE", "1")  # model đã tải sẵn, không gọi mạng
    llm_info = llm.warm_up()
    import torch
    from sentence_transformers import SentenceTransformer

    from inhand_rag.index.qdrant_store import client
    from inhand_rag.retrieve.rerank import Reranker

    emb = SentenceTransformer(EMBED_MODEL, device=os.environ.get("EMBED_DEVICE", "cpu"),
                              model_kwargs={"torch_dtype": torch.float32})
    return SimpleNamespace(emb=emb, cl=client(), rr=Reranker() if USE_RERANK else None, llm_info=llm_info)


def timed(name: str):
    """Cộng thời gian chạy node (ms) vào state["timing"]; node chạy lại (sau rewrite) thì cộng dồn."""
    def deco(fn):
        def run(state: State) -> dict:
            t = time.perf_counter()
            out = fn(state) or {}
            timing = dict(state.get("timing") or {})
            timing[name] = timing.get(name, 0.0) + 1000 * (time.perf_counter() - t)
            return {**out, "timing": timing}
        run.__name__ = fn.__name__
        return run
    return deco


def _json(text: str) -> dict:
    try:
        d = json.loads(text)
        return d if isinstance(d, dict) else {}
    except json.JSONDecodeError:
        return {}


def _ask_json(user: str, schema: dict, max_tokens: int = 300) -> dict:
    r = llm.chat([{"role": "system", "content": P.SYSTEM}, {"role": "user", "content": user}],
                 fmt=schema, max_tokens=max_tokens)
    return _json(r.text)


# ① ------------------------------------------------------------------------------------------------
@timed("understand")
def understand(state: State) -> dict:
    q = state["question"].strip()
    hist = "\n".join("%s: %s" % ("Nhân viên" if m["role"] == "user" else "Trợ lý", m["content"][:500])
                     for m in (state.get("history") or [])[-4:])
    user = P.UNDERSTAND + ("\nHỘI THOẠI TRƯỚC:\n%s\n" % hist if hist else "") + "\nCÂU HỎI MỚI: " + q
    d = _ask_json(user, P.UNDERSTAND_SCHEMA)
    nguon = d.get("nguon") if d.get("nguon") in ("hoso", "luat", "ca_hai", "ngoai_pham_vi") else "ca_hai"
    cau_hoi = (d.get("cau_hoi_doc_lap") or "").strip() or q
    if citation.parse_citation(q) and nguon in ("hoso", "ngoai_pham_vi"):
        nguon = "ca_hai" if nguon == "hoso" else "luat"  # nêu thẳng Điều/Luật thì chắc chắn cần luật
    m = RE_MA_HO_SO.search(cau_hoi) or RE_MA_HO_SO.search(q)
    queries = {}
    if nguon in ("hoso", "ca_hai"):
        queries["hoso"] = cau_hoi
    if nguon in ("luat", "ca_hai"):
        ql = (d.get("truy_van_luat") or "").strip() or cau_hoi
        for word, term in LEGAL_TERMS.items():
            ql = re.sub(word, term, ql, flags=re.I)
        queries["luat"] = ql
    return {"nguon": nguon, "cau_hoi": cau_hoi, "ma_ho_so": m.group(0) if m else MA_HO_SO,
            "queries": queries, "rewrites": state.get("rewrites", 0)}


# ② ------------------------------------------------------------------------------------------------
@timed("retrieve")
def retrieve(state: State) -> dict:
    r = resources()
    srcs = list(state["queries"])
    # Embed mọi truy vấn trong một lượt (CPU): hai lượt riêng tốn ~3,5 s mỗi câu hỏi hai nguồn.
    vecs = r.emb.encode([INSTRUCT[s] + state["queries"][s] for s in srcs], normalize_embeddings=True)
    hits = {}
    for src, vec in zip(srcs, vecs):
        q = state["queries"][src]
        flt = {"ma_ho_so": state["ma_ho_so"]} if src == "hoso" else None
        found = search(r.cl, r.emb, src, q, k=CANDIDATES + 10, flt=flt, dense=vec.tolist())
        if src == "luat" and not RE_HOI_MAU.search(state["question"]):
            # Phụ lục nghị định là mẫu hợp đồng, câu chữ giống hồ sơ nên lấn át điều luật: bỏ trừ khi hỏi về mẫu.
            found = [h for h in found if h.get("dieu") is not None]
        hits[src] = found[:CANDIDATES]
    pinned = citation.lookup(state["question"]) if "luat" in hits else []
    return {"hits": hits, "pinned": pinned}


# ③ ------------------------------------------------------------------------------------------------
@timed("rerank")
def rerank(state: State) -> dict:
    r = resources()
    top = TOP_N if len(state["hits"]) == 1 else TOP_N_EACH
    ranked = {}
    for src, hits in state["hits"].items():
        out = r.rr.rerank(state["queries"][src], hits, top_n=top) if r.rr else hits[:top]
        if src == "luat" and state.get("pinned"):
            pin_ids = {p["id"] for p in state["pinned"]}
            out = (state["pinned"] + [h for h in out if h["id"] not in pin_ids])[:max(top, len(state["pinned"]))]
        ranked[src] = out
    return {"ranked": ranked}


# ④ ------------------------------------------------------------------------------------------------
RE_LUAT_KEY = re.compile(r"^(.+?-(?:D\d+|PL))(?=-|#|$)")
RE_HOSO_KEY = re.compile(r"^([A-Z]+\d+-[A-Z]+\d*-\d+)")


def cite_key(src: str, item: dict) -> str:
    """Mã trích dẫn: hồ sơ theo mã tài liệu (KH002-G1-011), luật theo Điều (LKDBDS-2023-D25)."""
    if src == "hoso":
        return item.get("doc_id") or item["id"]
    m = RE_LUAT_KEY.match(item["id"])
    return m.group(1) if m else item["id"].split("#")[0]


def cite_label(src: str, item: dict) -> str:
    if src == "hoso":
        return "%s – %s" % (item.get("doc_id", ""), item.get("title", ""))
    vb = "%s %s" % (item.get("ten_van_ban", ""), item.get("so_hieu", ""))
    if item.get("dieu") is None:
        return "%s, Phụ lục" % vb
    return "%s, Điều %s. %s" % (vb, item["dieu"], item.get("tieu_de_dieu", ""))


@timed("expand")
def expand(state: State) -> dict:
    ranked = state["ranked"]
    budget = MAX_CONTEXT_CHARS // max(1, len(ranked))
    contexts = []
    for src, hits in ranked.items():
        left = budget
        for it in parent.expand(src, hits):
            if left < 400:
                break
            text = it["text"][:left]
            left -= len(text)
            extra = " (hiệu lực từ %s)" % it["ngay_hieu_luc"] if src == "luat" and it.get("ngay_hieu_luc") else ""
            contexts.append({"src": src, "key": cite_key(src, it), "label": cite_label(src, it) + extra,
                             "vi_tri": it.get("vi_tri", ""), "text": text, "cat_bot": len(text) < len(it["text"]),
                             "child_ids": it.get("child_ids", [])})
    return {"contexts": contexts}


def context_block(contexts: list[dict]) -> str:
    return "\n\n".join("[%s] %s\n%s" % (c["key"], c["label"], c["text"]) for c in contexts)


# ⑥ grade: cạnh điều kiện sau answer ----------------------------------------------------------------
def grade(state: State) -> str:
    if P.NOT_ENOUGH.rstrip(".") not in state.get("raw_answer", ""):
        return "verify"
    return "rewrite" if state.get("rewrites", 0) < MAX_REWRITES else "refuse"


@timed("rewrite")
def rewrite(state: State) -> dict:
    qs = state["queries"]
    d = _ask_json(P.REWRITE.format(question=state["cau_hoi"], q_hoso=qs.get("hoso", ""), q_luat=qs.get("luat", ""),
                                   tim_thay=", ".join(c["label"] for c in state.get("contexts", [])) or "không có"),
                  P.REWRITE_SCHEMA)
    new = {}
    for src, key in (("hoso", "truy_van_hoso"), ("luat", "truy_van_luat")):
        if src in qs:
            new[src] = (d.get(key) or "").strip() or qs[src]
    return {"queries": new, "rewrites": state.get("rewrites", 0) + 1}


# ⑥ ------------------------------------------------------------------------------------------------
@timed("answer")
def answer(state: State) -> dict:
    contexts = state["contexts"]
    if not contexts:
        return {"raw_answer": P.NOT_ENOUGH, "truncated": False}
    while True:
        user = "TÀI LIỆU:\n%s\n\n%s" % (context_block(contexts), P.ANSWER.format(question=state["cau_hoi"]))
        try:
            r = llm.chat([{"role": "system", "content": P.SYSTEM}, {"role": "user", "content": user}],
                         max_tokens=ANSWER_MAX_TOKENS)
            return {"raw_answer": r.text, "truncated": r.done_reason == "length", "contexts": contexts}
        except llm.LLMError as e:
            if "context size" not in str(e) or len(contexts) <= 1:
                raise
            contexts = contexts[:-1]  # vẫn quá dài: bỏ đoạn xếp hạng thấp nhất rồi thử lại


def refuse(state: State) -> dict:
    return {"answer": P.NOT_ENOUGH, "citations": [], "removed": []}


def out_of_scope(state: State) -> dict:
    return {"answer": P.OUT_OF_SCOPE, "citations": [], "removed": []}


# ⑦ ------------------------------------------------------------------------------------------------
RE_CITE = re.compile(r"\[([^\[\]]+)\]")
RE_DIEU_NAMED = re.compile(r"Điều\s+(\d+)")
RE_LUAT_TEXT = re.compile(r"^([A-Z0-9]+-\d{4})\s*(?:-D|,?\s*Điều\s*)(\d+)", re.I)


def normalize_cite(raw: str) -> str:
    """Đưa các cách viết thường gặp về mã chuẩn: KH002-G1-011-P2 -> KH002-G1-011,
    LKDBDS-2023-D25-K1 / "LKDBDS-2023 Điều 25" -> LKDBDS-2023-D25."""
    s = raw.strip()
    m = RE_LUAT_TEXT.match(s)
    if m:
        return "%s-D%s" % (m.group(1).upper(), m.group(2))
    m = RE_LUAT_KEY.match(s)
    if m:
        return m.group(1)
    m = RE_HOSO_KEY.match(s)
    return m.group(1) if m else s


@timed("verify")
def verify(state: State) -> dict:
    allowed = {}
    for c in state["contexts"]:
        allowed.setdefault(c["key"], c)
    kept, removed, used = [], [], []
    lines = [x for x in state.get("raw_answer", "").splitlines() if x.strip()]
    if state.get("truncated") and lines:
        removed.append(lines.pop())  # dòng cuối dở dang vì hết token
    for line in lines:
        cites = [x for m in RE_CITE.finditer(line) for x in re.split(r"[,;]", m.group(1)) if x.strip()]
        keys = [normalize_cite(x) for x in cites]
        if any(k not in allowed for k in keys):
            removed.append(line)
            continue
        dieu_cited = {k.rsplit("-D", 1)[1] for k in keys if allowed[k]["src"] == "luat" and "-D" in k}
        dieu_named = set(RE_DIEU_NAMED.findall(line))
        if dieu_cited and dieu_named and not dieu_named & dieu_cited:
            removed.append(line)  # nêu "Điều 25" nhưng trích mã của Điều khác
            continue
        kept.append(line)
        used += [k for k in keys if k not in used]
    text = "\n".join(kept).strip()
    if not text or P.NOT_ENOUGH.rstrip(".") in text:
        return {"answer": P.NOT_ENOUGH, "citations": [], "removed": removed}
    if state["nguon"] in ("luat", "ca_hai") and any(allowed[k]["src"] == "luat" for k in used):
        text += "\n\n_" + P.LEGAL_NOTE + "_"
    cits = [{"key": k, "src": allowed[k]["src"], "label": allowed[k]["label"], "vi_tri": allowed[k]["vi_tri"]}
            for k in used]
    return {"answer": text, "citations": cits, "removed": removed}
