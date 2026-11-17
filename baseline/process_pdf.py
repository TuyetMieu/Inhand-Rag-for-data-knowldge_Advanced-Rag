import pymupdf as fitz
import re
from langchain_text_splitters import RecursiveCharacterTextSplitter

def clean_and_extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        text = page.get_text()
        cleaned_text = re.sub(r'^\d+\s+(Điều|Khoản|Điểm|Cụm từ).*$', '', text, flags=re.MULTILINE)
        
        full_text += cleaned_text + "\n"
    return full_text 

pdf_file = "2022-11-Luat So huu tri tue - HN Lan 3.pdf"
raw_text = clean_and_extract_text_from_pdf(pdf_file)
text_splitter = RecursiveCharacterTextSplitter(
    separators=[r"\nĐiều \d+\.", r"\nChương ", r"\nPhần ", "\n\n", "\n"],
    is_separator_regex=True,
    chunk_size=1500,
    chunk_overlap=150,
)
chunks = text_splitter.create_documents([raw_text])

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

print("\nĐang khởi tạo mô hình Embedding Local...")
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

print("Đang mã hóa văn bản thành Vector và lưu vào ChromaDB...")
vectorstore = Chroma.from_documents(
    documents=chunks, 
    embedding=embeddings,
    persist_directory="./chroma_db_luat"
)
print("Hoàn tất lưu trữ Database!\n")

cau_hoi = "Điều kiện để sáng chế được bảo hộ là gì?"
print(f"Câu hỏi của người dùng: '{cau_hoi}'")
print("Hệ thống đang tìm kiếm các Điều luật liên quan...\n")

ket_qua_tim_kiem = vectorstore.similarity_search(cau_hoi, k=2) 

for i, ket_qua in enumerate(ket_qua_tim_kiem):
    print(f"--- TRÍCH XUẤT {i+1} ---")
    print(ket_qua.page_content)
    print("\n")