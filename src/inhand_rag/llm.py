"""Gọi LLM chạy local qua Ollama (mặc định IBM Granite 4.2 8B).

Chỉ dùng thư viện chuẩn để chạy được ngay, chưa cần cài gói nào.
Cấu hình đọc từ biến môi trường hoặc file .env ở gốc repo.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_env() -> None:
    env = REPO_ROOT / ".env"
    if not env.is_file():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_env()
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
LLM_MODEL = os.environ.get("LLM_MODEL", "granite4.2:8b")
# 6144 thay vì 8192: RTX 5070 Laptop 8 GB, Windows giữ ~1 GB; Granite 8B ở 8192 cần ~6,9 GB và bị
# Ollama đẩy một phần sang CPU (đo 12/11/2026: bước trả lời từ ~9 s lên ~100 s).
LLM_NUM_CTX = int(os.environ.get("LLM_NUM_CTX", "6144"))
# Giữ model trong VRAM lâu hơn mặc định của Ollama, tránh nạp lại giữa buổi demo.
LLM_KEEP_ALIVE = os.environ.get("LLM_KEEP_ALIVE", "2h")


class LLMError(RuntimeError):
    pass


@dataclass
class LLMResult:
    text: str
    thinking: str
    model: str
    prompt_tokens: int
    output_tokens: int
    load_seconds: float
    total_seconds: float
    done_reason: str = ""  # "stop" hoặc "length" (hết max_tokens)

    @property
    def tokens_per_second(self) -> float:
        gen = self.total_seconds - self.load_seconds
        return self.output_tokens / gen if gen > 0 else 0.0


def _request(path: str, payload: dict | None = None, timeout: float = 600) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        OLLAMA_HOST + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise LLMError("Ollama trả lỗi %s: %s" % (e.code, e.read().decode("utf-8", "replace"))) from e
    except urllib.error.URLError as e:
        raise LLMError("Không kết nối được Ollama tại %s. Đã chạy `ollama serve` chưa?" % OLLAMA_HOST) from e


def server_version() -> str:
    return _request("/api/version", timeout=5)["version"]


def loaded_models() -> list[dict]:
    """Model đang nằm trong bộ nhớ: name, size, size_vram (byte), context_length."""
    return _request("/api/ps", timeout=5).get("models", [])


def warm_up(model: str = LLM_MODEL) -> dict:
    """Nạp model vào VRAM trước khi nạp model khác lên GPU; trả về thông tin nạp (size, size_vram)."""
    chat([{"role": "user", "content": "ok"}], model=model, max_tokens=1)
    return next((m for m in loaded_models() if m["name"] == model), {})


def installed_models() -> list[str]:
    return [m["name"] for m in _request("/api/tags", timeout=10).get("models", [])]


def chat(
    messages: list[dict],
    model: str = LLM_MODEL,
    temperature: float = 0.0,
    think: bool = False,
    num_ctx: int = LLM_NUM_CTX,
    max_tokens: int | None = None,
    fmt: dict | str | None = None,
) -> LLMResult:
    """Gửi hội thoại, trả về câu trả lời và số liệu tốc độ.

    think=False tắt chế độ suy luận của Granite 4.2 để trả lời nhanh;
    bật lên khi cần câu trả lời cẩn thận hơn (chậm hơn đáng kể).
    max_tokens tính cả phần suy luận, nên khi bật suy luận mặc định cho nhiều hơn.
    fmt: JSON schema (hoặc "json") để Ollama ép đầu ra đúng cấu trúc.
    """
    if max_tokens is None:
        max_tokens = 4096 if think else 1024
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": think,
        "keep_alive": LLM_KEEP_ALIVE,
        "options": {"temperature": temperature, "num_ctx": num_ctx, "num_predict": max_tokens},
    }
    if fmt is not None:
        payload["format"] = fmt
    start = time.perf_counter()
    out = _request("/api/chat", payload)
    total = time.perf_counter() - start
    message = out.get("message", {})
    return LLMResult(
        text=message.get("content", "").strip(),
        thinking=(message.get("thinking") or "").strip(),
        model=out.get("model", model),
        prompt_tokens=out.get("prompt_eval_count", 0),
        output_tokens=out.get("eval_count", 0),
        load_seconds=out.get("load_duration", 0) / 1e9,
        total_seconds=total,
        done_reason=out.get("done_reason", ""),
    )


SYSTEM_PROMPT_VI = (
    "Bạn là trợ lý hồ sơ cho nhân viên kinh doanh bất động sản. "
    "Chỉ trả lời bằng thông tin trong phần TÀI LIỆU được cung cấp, viết bằng tiếng Việt có dấu, ngắn gọn. "
    "Trả lời thẳng vào câu hỏi, không nhắc lại câu hỏi. "
    "Nếu tài liệu nêu một tổng số và các khoản thành phần, câu trả lời chính là tổng số theo đúng điều khoản; "
    "các khoản thành phần chỉ nêu thêm để giải thích. "
    "Sau mỗi ý, ghi mã tài liệu làm nguồn trong ngoặc vuông, ví dụ [KH002-G1-011]. "
    "Nếu tài liệu không có thông tin để trả lời, chỉ trả lời đúng câu: "
    "\"Không đủ căn cứ trong tài liệu được cung cấp.\" Không suy đoán, không bịa số liệu."
)


def answer_with_context(question: str, docs: list[dict], **kwargs) -> LLMResult:
    """docs: danh sách {"id": mã tài liệu, "text": nội dung}."""
    context = "\n\n".join("[%s]\n%s" % (d["id"], d["text"].strip()) for d in docs)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_VI},
        {"role": "user", "content": "TÀI LIỆU:\n%s\n\nCÂU HỎI: %s" % (context, question)},
    ]
    return chat(messages, **kwargs)
