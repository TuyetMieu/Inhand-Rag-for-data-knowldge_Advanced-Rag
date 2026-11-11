"""Bài thử tiếng Việt cho LLM local: 10 câu hỏi có kèm đoạn trích hồ sơ KH002.

Mỗi câu đạt khi: có đủ số liệu/ý mong đợi, viết tiếng Việt có dấu, trích đúng mã tài liệu
(câu 10 thì phải từ chối vì tài liệu không có thông tin). Ngưỡng đạt của cả bài: 8/10.

Cách chạy (từ gốc repo):
    python scripts/eval_llm_vi.py              # tắt chế độ suy luận
    python scripts/eval_llm_vi.py --think      # bật chế độ suy luận
    python scripts/eval_llm_vi.py --model granite4.2:3b
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from inhand_rag import llm  # noqa: E402

VI_MARKS = set("àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ")
PASS_MARK = 8


def grade(item: dict, answer: str) -> tuple[bool, list[str]]:
    reasons = []
    low = answer.lower()
    digits = re.sub(r"\D", "", answer)
    for num in item.get("expect_numbers", []):
        if num not in digits:
            reasons.append("thiếu số %s" % num)
    for group in item.get("expect_any", []):
        if not any(opt.lower() in low for opt in group):
            reasons.append("thiếu ý: %s" % " / ".join(group))
    for pattern in item.get("forbid_regex", []):
        if re.search(pattern, low):
            reasons.append("kết luận sai: khớp mẫu cấm %s" % pattern)
    if not answer.strip():
        reasons.append("câu trả lời trống")
    # Câu trả lời chỉ gồm số/ngày + mã nguồn thì không cần chữ có dấu.
    letters = re.sub(r"\[[^\]]*\]", "", low)
    if sum(c.isalpha() for c in letters) >= 30 and sum(c in VI_MARKS for c in low) < 3:
        reasons.append("không phải tiếng Việt có dấu")
    cite = item.get("expect_cite")
    if cite and cite not in answer:
        reasons.append("không trích %s" % cite)
    if item.get("expect_refusal") and re.search(r"\d+([.,]\d+)?\s*%", answer):
        reasons.append("bịa ra tỷ lệ phần trăm")
    return not reasons, reasons


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=llm.LLM_MODEL)
    ap.add_argument("--think", action="store_true")
    args = ap.parse_args()

    items = [json.loads(l) for l in (ROOT / "eval" / "llm_vi_test.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    rows, passed, speeds = [], 0, []
    for item in items:
        res = llm.answer_with_context(item["question"], item["docs"], model=args.model, think=args.think)
        ok, reasons = grade(item, res.text)
        passed += ok
        speeds.append(res.tokens_per_second)
        print("[%s] %s  %s" % ("ĐẠT " if ok else "TRƯỢT", item["id"], item["question"]))
        print("      " + res.text.replace("\n", "\n      "))
        if reasons:
            print("      -> " + "; ".join(reasons))
        print("      (%.1fs, %d token ra%s, %.1f token/s)" % (
            res.total_seconds, res.output_tokens,
            ", suy luận %d ký tự" % len(res.thinking) if args.think else "", res.tokens_per_second))
        rows.append({**{k: item[k] for k in ("id", "question")}, "answer": res.text,
                     "thinking_chars": len(res.thinking), "output_tokens": res.output_tokens, "pass": ok,
                     "reasons": reasons, "seconds": round(res.total_seconds, 2),
                     "tokens_per_second": round(res.tokens_per_second, 1)})

    verdict = "ĐẠT" if passed >= PASS_MARK else "KHÔNG ĐẠT"
    avg_speed = sum(speeds[1:]) / max(len(speeds) - 1, 1)  # bỏ câu đầu vì có thời gian nạp model
    print("\nKẾT QUẢ: %d/%d câu đạt -> %s (ngưỡng %d/10). Tốc độ trung bình %.1f token/s."
          % (passed, len(items), verdict, PASS_MARK, avg_speed))

    out_dir = ROOT / "eval" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = "%s_%s_%s" % (args.model.replace(":", "-").replace("/", "-"), "think" if args.think else "nothink",
                        time.strftime("%Y%m%d_%H%M%S"))
    (out_dir / ("llm_vi_%s.json" % tag)).write_text(json.dumps(
        {"model": args.model, "think": args.think, "passed": passed, "total": len(items),
         "verdict": verdict, "avg_tokens_per_second": round(avg_speed, 1), "rows": rows},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if passed >= PASS_MARK else 1


if __name__ == "__main__":
    sys.exit(main())
