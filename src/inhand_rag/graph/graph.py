"""Đồ thị LangGraph của pipeline trả lời.

    understand ─┬─ ngoai_pham_vi ─► out_of_scope ─► END
                └─► retrieve ─► rerank ─► expand ─► answer ─┬─ đủ căn cứ ─────► verify ─► END
                       ▲                                     ├─ thiếu, lần 1 ─► rewrite ─┐
                       └─────────────────────────────────────┼───────────────────────────┘
                                                             └─ thiếu, lần 2 ─► refuse ─► END
    (cạnh điều kiện sau answer là bước chấm context, nodes.grade)

    from inhand_rag.graph import ask
    out = ask("Đợt 2 khách KH002 phải thanh toán bao nhiêu?")
    out["answer"], out["citations"], out["timing"]
"""
from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from inhand_rag.graph import nodes as N


@lru_cache(maxsize=1)
def build():
    g = StateGraph(N.State)
    for name in ("understand", "retrieve", "rerank", "expand", "answer", "rewrite", "verify", "refuse", "out_of_scope"):
        g.add_node(name, getattr(N, name))
    g.add_edge(START, "understand")
    g.add_conditional_edges("understand", lambda s: "out_of_scope" if s["nguon"] == "ngoai_pham_vi" else "retrieve",
                            ["out_of_scope", "retrieve"])
    g.add_edge("retrieve", "rerank")
    g.add_edge("rerank", "expand")
    g.add_edge("expand", "answer")
    g.add_conditional_edges("answer", N.grade, ["verify", "rewrite", "refuse"])
    g.add_edge("rewrite", "retrieve")
    for name in ("verify", "refuse", "out_of_scope"):
        g.add_edge(name, END)
    return g.compile()


def ask(question: str, history: list[dict] | None = None) -> dict:
    """Chạy cả đồ thị cho một câu hỏi; trả về state cuối (answer, citations, contexts, timing...)."""
    return build().invoke({"question": question, "history": history or [], "timing": {}, "rewrites": 0})
