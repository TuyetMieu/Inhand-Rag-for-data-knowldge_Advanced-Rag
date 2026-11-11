"""Kiểm tra nhanh LLM local: Ollama chạy chưa, model có chưa, trả lời tiếng Việt được không.

Cách chạy (từ gốc repo):
    python scripts/smoke_llm.py
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from inhand_rag import llm  # noqa: E402


def gpu_memory() -> str:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() or "không đọc được"
    except (OSError, subprocess.TimeoutExpired):
        return "không có nvidia-smi"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        print("Ollama:", llm.server_version(), "tại", llm.OLLAMA_HOST)
        models = llm.installed_models()
    except llm.LLMError as e:
        print("LỖI:", e)
        return 1
    print("Model đã cài:", ", ".join(models) or "(chưa có)")
    if llm.LLM_MODEL not in models:
        print("LỖI: chưa có %s. Chạy: ollama pull %s" % (llm.LLM_MODEL, llm.LLM_MODEL))
        return 1

    docs = [{
        "id": "KH002-G1-011",
        "text": "HỢP ĐỒNG ĐẶT CỌC. Bên A đặt cọc bằng chuyển khoản trực tiếp CĐT 3.038.686.489 VNĐ; "
                "giữ chỗ 100.000.000 được gộp vào cọc. Thời hạn đặt cọc: 12/10/2026–22/10/2026.",
    }]
    for label, think in (("Không suy luận", False), ("Có suy luận", True)):
        res = llm.answer_with_context("Khách đặt cọc bao nhiêu tiền và hạn đặt cọc đến ngày nào?", docs, think=think)
        print("\n--- %s ---" % label)
        print(res.text)
        print("(%d token vào, %d token ra, nạp model %.1fs, tổng %.1fs, %.1f token/s)"
              % (res.prompt_tokens, res.output_tokens, res.load_seconds, res.total_seconds, res.tokens_per_second))
    print("\nVRAM đang dùng / tổng:", gpu_memory())
    return 0


if __name__ == "__main__":
    sys.exit(main())
