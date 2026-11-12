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

## Dữ liệu bảng (Excel → SQLite)

```bat
set PYTHONPATH=src
```

```bat
.venv\Scripts\python -m inhand_rag.ingest.bang "..\Data\Du_lieu_mau_100_final.xlsx" data\bang\bang.sqlite3
```

```bat
.venv\Scripts\python scripts\check_hoso_vs_bang.py data\hoso\KH002 data\bang\bang.sqlite3
```

- `bang.py`: 6 sheet thành 6 bảng (`bang_gia`, `khach_hang`, `mua_ban`, `ban_giao`, `tien_do_thanh_toan`, `giao_dich`), tên cột không dấu, tiền là số nguyên, ngày theo ISO; in báo cáo khóa nối, tổng các đợt, căn bán trùng, CCCD.
- `check_hoso_vs_bang.py`: kiểm mọi số liệu của một khách trong SQLite đều xuất hiện trong hồ sơ docx của khách đó.

## Văn bản luật

`schemas/luat_catalog.csv` liệt kê 12 văn bản trong `Dataset Luật`: số hiệu, ngày thông qua, ngày hiệu lực (đã tính Luật 43/2024/QH15 đưa ba luật lên 01/08/2024), file nguồn và trạng thái. Luật Nhà ở và Luật Đất đai là nhiều số Công báo nối tiếp, không phải bản trùng; các phần được ghép theo thứ tự trong cột `files`.

Tách 4 luật có text thành Điều và Khoản (bỏ header Công báo, chữ ký số; ghi chú các khoản bị Luật 43 sửa):

```bat
.venv\Scripts\python -m inhand_rag.ingest.luat "..\Dataset Luật" data\luat
```

Kết quả: `data\luat\dieu.jsonl` và `data\luat\chunks.jsonl` (4 luật có text: 546 Điều, 2.429 chunk; cộng 7 văn bản scan bên dưới: 1.500 Điều, 5.268 chunk). Chunk theo khoản, mỗi chunk có tiêu đề vị trí "Luật › Chương › Điều › Khoản"). `src/inhand_rag/retrieve/citation.py` tra thẳng câu hỏi có trích dẫn như "khoản 5 Điều 23 Luật KDBĐS".

```bat
.venv\Scripts\python scripts\check_luat_search.py
```

```bat
.venv\Scripts\python scripts\check_ocr.py "..\Dataset Luật\nghị định 96_2024_NĐ-CP.pdf" 1-5
```

- `check_luat_search.py`: 10 câu hỏi tự nhiên, đo đáp án có trong top 6 khi chỉ dùng vector (hiện 10/10 trên 5.268 chunk).
- `check_ocr.py`: OCR thử vài trang bản scan bằng EasyOCR (model lưu trong `.cache\easyocr`) và ước lượng chất lượng tiếng Việt.

### Văn bản scan: OCR, sửa dấu, tách Điều

7 văn bản scan (Bộ luật Dân sự và 6 nghị định, 898 trang) đi qua ba bước. Bước OCR chạy khoảng 1 giờ trên GPU, nên tắt Ollama trước; dừng giữa chừng thì chạy lại sẽ làm tiếp từ trang chưa có.

```bat
.venv\Scripts\python -W ignore scripts\ocr_batch.py "..\Dataset Luật"
```

```bat
.venv\Scripts\python scripts\sua_dau_ocr.py
```

```bat
.venv\Scripts\python -W ignore -m inhand_rag.ingest.luat "..\Dataset Luật" data\luat
```

- `ocr_batch.py`: EasyOCR tiếng Việt 300 dpi, lưu nguyên văn từng trang vào `data\ocr\<mã>\`.
- `sua_dau_ocr.py`: bỏ khối chữ ký số, sửa dấu (`src/inhand_rag/ingest/sua_dau.py`) rồi ghi `data\ocr_sua\<mã>.txt`. Bộ sửa chỉ đổi dấu, không đổi chữ cái; học từ luật có text và mọi docx gõ máy. Kết quả: âm tiết có trong từ vựng từ 96–98% lên 98–99,7%; lỗi mất móc ư/ơ ở nhóm từ hay gặp từ 6–25% xuống 0–8%. Lấy mẫu 60 chỗ sửa thì 54 đúng; 6 chỗ sai là đổi một từ đúng thành một từ khác cũng hợp lệ ("thả rông"→"thả ròng", "đo lường"→"đo lượng").
- `luat.py` với bản OCR: chọn dãy "Điều N." tăng dần dài nhất, bỏ dẫn chiếu ("tại Điều 17.") và Điều nằm trong ngoặc kép (nội dung sửa đổi văn bản khác). Phần sau "Nơi nhận:" ở cuối văn bản (mẫu hợp đồng, mẫu đơn) thành chunk phụ lục `<mã>-PL-n`. Hai file của Bộ luật Dân sự là hai phần nối tiếp nên được ghép. Hiện đủ Điều ở cả 6 nghị định; Bộ luật Dân sự có 687/689 Điều (thiếu 416, 623).
- Chunk OCR có `nguon_text = "ocr"`: chữ có thể còn sai, khi trả lời nên dẫn chiếu Điều/Khoản thay vì trích nguyên văn.

## Hồ sơ KH002 thành chunk

```bat
.venv\Scripts\python -m inhand_rag.ingest.hoso data\hoso\KH002 data\hoso
```

Đọc 117 docx theo `manifest.json`, giữ đúng thứ tự đoạn văn và bảng (bảng thành Markdown, mỗi hàng một dòng; không dùng Docling vì với docx nó cũng chỉ đọc cùng XML này mà kéo theo rất nhiều thư viện). Tách mục tại các tiêu đề ("ĐIỀU 3: …", "II. …", đoạn in đậm hoặc in hoa).

- Chunk con (`data\hoso\kh002_chunks.jsonl`, 883 chunk, trung vị 750 ký tự): mục ngắn liền nhau được gộp; bảng dài cắt theo hàng, lặp lại hàng tiêu đề. Tiêu đề vị trí dạng "KH002 › Giai đoạn 3 – Thanh toán theo đợt › Đợt 2 › THÔNG BÁO THANH TOÁN ĐỢT 2 › …".
- Chunk cha (`kh002_parents.jsonl`, 232 chunk): các chunk con liền nhau tới 4.000 ký tự, để đưa cho LLM đọc. Payload mang `doc_id`, `doc_type`, `stage`, `tranche`, `branch`, `required`, `status` từ manifest để lọc.

## Chỉ mục Qdrant và truy hồi lai

Cần Qdrant đang chạy (mục đầu README) và tắt Ollama (embed bằng GPU, khoảng 1,5 phút):

```bat
.venv\Scripts\python -W ignore scripts\build_index.py
```

```bat
.venv\Scripts\python -W ignore scripts\check_hybrid.py
```

- Hai collection `luat` (5.268 điểm) và `hoso` (883 điểm). Mỗi điểm có vector `dense` (harrier, 1024 chiều) và vector thưa `bm25`.
- BM25 (`src/inhand_rag/index/sparse.py`): âm tiết + cặp âm tiết liền nhau + nguyên cụm mã/số ("ct2-04", "29/2023/qh15", "30.386.864.888"); trọng số tf tính ở client, IDF do Qdrant tính.
- `src/inhand_rag/retrieve/hybrid.py`: lấy 30 ứng viên mỗi nhánh rồi gộp RRF trong Qdrant; lọc theo payload (ví dụ `{"tranche": 2}`).
- `check_hybrid.py` (embed câu hỏi trên CPU) trên 10 câu luật + 10 câu hồ sơ, đáp án trong top 6: BM25 7/10 và 10/10, vector 10/10 và 9/10, **hybrid 10/10 và 10/10**.

### Rerank và mở rộng chunk cha

- `src/inhand_rag/retrieve/rerank.py`: xếp hạng lại 30 ứng viên của hybrid, giữ 6, bằng `jinaai/jina-reranker-v3.5` (0,6B, ra 27/07/2026; listwise, chấm cả danh sách trong một lượt). Model cần `trust_remote_code`; code `modeling.py` đã được đọc: chỉ dựng prompt và tính cosine, không gọi mạng. **Giấy phép CC BY-NC 4.0, chỉ dùng phi thương mại**; dùng thương mại thì đổi sang `Qwen/Qwen3-Reranker-0.6B` (Apache 2.0, nhưng ra năm 2025).
- `src/inhand_rag/retrieve/parent.py`: đổi chunk con thành chunk cha (cả Điều luật, hoặc nhóm mục của tài liệu hồ sơ), bỏ cha trùng. Điều dài hơn 6.000 ký tự thì giữ các khoản tìm được thay vì cả Điều.
- `check_hybrid.py` có thêm cột `rerank`, in MRR (trung bình 1/hạng của đáp án đúng), độ trễ rerank và VRAM đỉnh. Đặt `set RERANK_DEVICE=cpu` để đo trên CPU, `set RERANK_K=20` để đổi số ứng viên.
- Kết quả 12/11/2026 trên RTX 5070 Laptop 8 GB, Granite 4.2 8B đang nạp trong Ollama, giữ top 6 (mọi cấu hình đều có đáp án trong top 6 ở 10/10 câu, trừ BM25 luật 7/10 và vector hồ sơ 9/10):

  | MRR | BM25 | Vector | Hybrid | Rerank 30 ứng viên | **Rerank 20 ứng viên** |
  |---|---|---|---|---|---|
  | Luật (10 câu) | 0,43 | 0,77 | 0,69 | 0,77 | 0,74 |
  | Hồ sơ (10 câu) | 0,70 | 0,78 | 0,78 | 0,88 | 0,93 |
  | Độ trễ rerank (trung vị / chậm nhất) | | | | 1,9 s / 3,6 s | **1,0 s / 1,4 s** |
  | VRAM đỉnh của reranker | | | | 2,9 GB | 2,15 GB |

- **Chọn 20 ứng viên** (mặc định trong `rerank.py`, đổi bằng `RERANK_K`): nhanh gấp đôi, ít VRAM hơn, MRR tương đương 30.
- Rerank đẩy đáp án lên hạng 1 ở nhiều câu (ví dụ "thời hạn đặt cọc" từ hạng 5 lên 1) nhưng kéo câu "điều kiện đưa nhà hình thành trong tương lai vào kinh doanh" từ hạng 3 xuống 5. Vì 6 chunk đều đưa vào LLM, câu này vẫn có đủ ngữ cảnh.
- Trên CPU rerank 30 ứng viên mất trung vị 33 s, nên **reranker phải chạy trên GPU**, chung với Granite.
- Lúc đo, `ollama ps` báo Granite 5,9 GB, `100% GPU`, ngữ cảnh 4096 (do lệnh `ollama run`). Granite cộng reranker (2,15 GB) vừa khít 8 GB. Pipeline gọi Granite với `num_ctx` 8192 (`LLM_NUM_CTX`), tốn thêm VRAM; cần đo lại khi chạy pipeline thật. Ngữ cảnh đưa vào LLM cũng phải có giới hạn: 6 chunk cha có thể dài tới hơn 20.000 ký tự, vượt 8192 token.

## Quy tắc kiểm hồ sơ và câu hỏi vàng

- `schemas/legal_rules.yaml`: 15 quy tắc cho kịch bản kiểm hồ sơ và gợi ý pháp lý. Mỗi quy tắc có ngưỡng để code tính, căn cứ điều luật (đã đối chiếu PDF hay chưa), nguồn (luật, nhận xét chuyên gia, đối soát dữ liệu) và kết quả mong đợi trên KH002. Kèm danh sách giấy tờ bổ sung vào checklist theo case.
- `eval/golden.jsonl`: 12 câu hỏi vàng kèm ý chính, tài liệu nguồn và quy tắc liên quan.

Kiểm cả hai file với dữ liệu thật (tính lại tỷ lệ, thời hạn từ SQLite; dò điều khoản trong văn bản):

```bat
.venv\Scripts\python scripts\validate_rules.py data\hoso\KH002 data\bang\bang.sqlite3
```

## Cấu trúc

```
src/inhand_rag/llm.py        gọi LLM local, prompt trả lời có trích dẫn
src/inhand_rag/ingest/bang.py  nạp Excel vào SQLite, kiểm chất lượng
src/inhand_rag/ingest/hoso.py  docx hồ sơ -> chunk cha–con có tiêu đề vị trí
src/inhand_rag/ingest/luat.py  văn bản luật -> Điều/Khoản (PDF text và bản OCR)
src/inhand_rag/index/          BM25 thưa, ghi Qdrant
src/inhand_rag/retrieve/       hybrid RRF, rerank, mở rộng chunk cha, tra trích dẫn Điều/Khoản
scripts/build_index.py       dựng collection luat, hoso
scripts/check_hybrid.py      so BM25 / vector / hybrid
scripts/check_env.py         kiểm GPU, embedding, Qdrant
scripts/check_hoso_vs_bang.py  đối chiếu hồ sơ docx với SQLite
scripts/smoke_llm.py         kiểm nhanh LLM
scripts/eval_llm_vi.py       bài thử tiếng Việt cho LLM
scripts/build_kh002.py       dựng bộ hồ sơ KH002 chuẩn (schema 1.0)
scripts/validate_dataset.py  kiểm một bộ hồ sơ theo schema 1.0
eval/llm_vi_test.jsonl       10 câu hỏi thử
baseline/                    RAGdemo (native RAG) để so sánh, đã gỡ API key
```
