# Baseline: native RAG (RAGdemo)

Bản RAG ban đầu của nhóm, giữ lại để so sánh với pipeline Advanced RAG. Không phát triển thêm.

- Nạp một PDF luật, cắt 1000 ký tự, tìm kiếm BM25 + vector BGE-M3 (trọng số 50/50, k=3), đưa vào prompt.
- LLM qua Groq (`mainrag.py`) hoặc Gemini (`rag_llm.py`); chấm điểm bằng Ollama (`evaluate_rag.py`).

Khác với bản gốc trong `RAGdemo/`: các API key ghi cứng đã được gỡ, code đọc key từ biến
môi trường `GROQ_API_KEY` và `GOOGLE_API_KEY`. Các key cũ đã từng nằm trong code nên cần đổi key mới.

Không kèm dữ liệu: file PDF luật, thư mục `chroma_db_luat/` và các báo cáo Excel vẫn nằm trong `RAGdemo/` gốc.
