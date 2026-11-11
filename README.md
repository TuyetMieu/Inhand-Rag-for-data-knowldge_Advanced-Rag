# Inhand-Rag-for-data-knowldge_Advanced-Rag

Advanced RAG hỗ trợ nhân viên bất động sản tra cứu hồ sơ giao dịch và nhận gợi ý pháp lý theo từng văn bản.
Dữ liệu là hồ sơ mô phỏng, không có giá trị pháp lý.

## LLM chạy local

Mặc định dùng **IBM Granite 4.2 8B** (`granite4.2:8b`, ra ngày 25/08/2026, Apache 2.0) qua Ollama.

```bash
ollama serve
```

```bash
ollama pull granite4.2:8b
```

```bash
python scripts/smoke_llm.py
```

```bash
python scripts/eval_llm_vi.py
```

- `smoke_llm.py`: kiểm Ollama, model, một câu hỏi tiếng Việt, tốc độ và VRAM.
- `eval_llm_vi.py`: 10 câu hỏi tiếng Việt trên đoạn trích hồ sơ KH002; đạt khi từ 8/10 câu trở lên. Kết quả lưu ở `eval/results/`.
- Đổi model hoặc địa chỉ Ollama: sao chép `.env.example` thành `.env` rồi sửa.

Code hiện chỉ dùng thư viện chuẩn của Python (3.12 trở lên).

## Cấu trúc

```
src/inhand_rag/llm.py      gọi LLM local, prompt trả lời có trích dẫn
scripts/smoke_llm.py       kiểm tra nhanh
scripts/eval_llm_vi.py     bài thử tiếng Việt
eval/llm_vi_test.jsonl     10 câu hỏi thử
```
