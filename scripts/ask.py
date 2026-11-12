"""Hỏi pipeline từ dòng lệnh.

Cần: Qdrant đang chạy, Ollama đang chạy với granite4.2:8b (xem README).

    .venv\\Scripts\\python scripts/ask.py "Đợt 2 KH002 bao nhiêu là vốn tự có, bao nhiêu là vốn vay?"
    .venv\\Scripts\\python scripts/ask.py --context "Tiền đặt cọc của KH002 có đúng quy định không?"
    .venv\\Scripts\\python scripts/ask.py            (không có câu hỏi: hỏi liên tục, nhớ hội thoại; gõ trống để thoát)
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from inhand_rag.graph import ask  # noqa: E402


def show(out: dict, with_context: bool) -> None:
    print("Nguồn: %s | câu hỏi độc lập: %s" % (out["nguon"], out.get("cau_hoi", "")))
    for src, q in (out.get("queries") or {}).items():
        print("  truy vấn %s: %s" % (src, q))
    if out.get("rewrites"):
        print("  đã viết lại truy vấn %d lần" % out["rewrites"])
    if with_context:
        for c in out.get("contexts", []):
            print("\n--- [%s] %s%s\n%s" % (c["key"], c["label"], " (đã cắt bớt)" if c["cat_bot"] else "", c["text"]))
    print("\n" + out["answer"] + "\n")
    for c in out.get("citations", []):
        print("  [%s] %s" % (c["key"], c["label"]))
    for line in out.get("removed", []):
        print("  ĐÃ BỎ (trích nguồn không có trong tài liệu): %s" % line)
    t = out.get("timing", {})
    print("Thời gian: " + ", ".join("%s %.1fs" % (k, v / 1000) for k, v in t.items())
          + " | tổng %.1fs" % (sum(t.values()) / 1000))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="*")
    ap.add_argument("--context", action="store_true", help="in cả tài liệu đưa vào LLM")
    a = ap.parse_args()
    if a.question:
        show(ask(" ".join(a.question)), a.context)
        return 0
    history = []
    while True:
        q = input("\nHỏi: ").strip()
        if not q:
            return 0
        out = ask(q, history)
        show(out, a.context)
        history += [{"role": "user", "content": q}, {"role": "assistant", "content": out["answer"]}]


if __name__ == "__main__":
    sys.exit(main())
