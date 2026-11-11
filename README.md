# Inhand-Rag-for-data-knowldge_Advanced-Rag

Advanced RAG hỗ trợ nhân viên bất động sản tra cứu hồ sơ giao dịch và nhận gợi ý pháp lý theo từng văn bản.
Dữ liệu là hồ sơ mô phỏng, không có giá trị pháp lý.

Mọi thứ tải về (model, thư viện, dữ liệu, chỉ mục) đều nằm trong thư mục repo và không lên git:
`models/` (Ollama), `.venv/`, `.cache/` (Hugging Face), `tools/qdrant/`, `qdrant_storage/`, `data/`.

## Dựng môi trường (Windows, cmd)

Cần `uv` và Python 3.12. Torch bản CUDA 13.0 được lấy từ kho của PyTorch (cấu hình sẵn trong `pyproject.toml`).

```bat
uv venv --python 3.12 .venv
```

```bat
uv pip install --python .venv\Scripts\python.exe -r pyproject.toml
```

Qdrant 1.20.0: tải `qdrant-x86_64-pc-windows-msvc.zip` từ trang phát hành của qdrant/qdrant, giải nén vào `tools\qdrant\`, rồi chạy trong một cửa sổ riêng:

```bat
set QDRANT__STORAGE__STORAGE_PATH=%CD%\qdrant_storage
```

```bat
set QDRANT__TELEMETRY_DISABLED=true
```

```bat
tools\qdrant\qdrant.exe
```

Kiểm tra torch nhận GPU, embed được tiếng Việt và ghi được vào Qdrant:

```bat
.venv\Scripts\python scripts\check_env.py
```

## LLM chạy local

**IBM Granite 4.2 8B** (`granite4.2:8b`, ra ngày 25/08/2026, Apache 2.0) qua Ollama, model lưu trong `models\`. Chạy trong một cửa sổ riêng:

```bat
set OLLAMA_MODELS=%CD%\models
```

```bat
ollama serve
```

```bat
ollama pull granite4.2:8b
```

```bat
python scripts\smoke_llm.py
```

```bat
python scripts\eval_llm_vi.py
```

- `smoke_llm.py`: kiểm Ollama, model, một câu hỏi tiếng Việt, tốc độ và VRAM.
- `eval_llm_vi.py`: 10 câu hỏi tiếng Việt trên đoạn trích hồ sơ KH002; đạt khi từ 8/10. Thêm `--think` để bật chế độ suy luận (chậm hơn khoảng 10 lần, không chính xác hơn). Kết quả lưu ở `eval\results\`.
- Kết quả trên RTX 5070 Laptop 8 GB: 9/10 khi tắt suy luận, khoảng 38 token/s, chiếm 6,1 GB VRAM.

## Dữ liệu hồ sơ

Bộ chuẩn KH002 nằm ở `data\hoso\KH002\` (không lên git), dựng từ file zip đã qua chuyên gia sửa:

```bat
python scripts\build_kh002.py "..\KH002 (1).zip" data\hoso\KH002
```

```bat
python scripts\validate_dataset.py data\hoso\KH002
```

## Cấu trúc

```
src/inhand_rag/llm.py        gọi LLM local, prompt trả lời có trích dẫn
scripts/check_env.py         kiểm GPU, embedding, Qdrant
scripts/smoke_llm.py         kiểm nhanh LLM
scripts/eval_llm_vi.py       bài thử tiếng Việt cho LLM
scripts/build_kh002.py       dựng bộ hồ sơ KH002 chuẩn (schema 1.0)
scripts/validate_dataset.py  kiểm một bộ hồ sơ theo schema 1.0
eval/llm_vi_test.jsonl       10 câu hỏi thử
baseline/                    RAGdemo (native RAG) để so sánh, đã gỡ API key
```
