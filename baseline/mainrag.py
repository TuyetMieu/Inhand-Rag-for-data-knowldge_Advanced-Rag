import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq

# Import các công cụ Hybrid Search và BGE-M3
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever


#CHIA NHỎ DỮ LIỆU LUẬT
print("Đang tải dữ liệu luật từ ChromaDB...")
loader = PyPDFLoader("2022-11-Luat So huu tri tue - HN lan 3.pdf") # Đổi tên file PDF của bạn nếu cần
docs_raw = loader.load()
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
docs = text_splitter.split_documents(docs_raw)

#BGE-M3
print("Đang nạp mô hình nhúng BAAI/bge-m3...")
bge_embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-m3",
    model_kwargs={'device': 'cpu'},  
    encode_kwargs={'normalize_embeddings': True}
)

#HYBRID SEARCH
print("Đang xây dựng kiến trúc Hybrid Search (BM25 + BGE-M3)...")
vectorstore = Chroma.from_documents(documents=docs, embedding=bge_embeddings)
vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

bm25_retriever = BM25Retriever.from_documents(docs)
bm25_retriever.k = 3

# Trộn 2 luồng với tỷ lệ 50-50
ensemble_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, vector_retriever], 
    weights=[0.5, 0.5]
)

#BỘ NÃO SINH CÂU TRẢ LỜI (GROQ API)
# Key đọc từ biến môi trường GROQ_API_KEY (không ghi cứng trong code).
if not os.environ.get("GROQ_API_KEY"):
    raise SystemExit("Thiếu biến môi trường GROQ_API_KEY")
llm = ChatGroq(model_name="qwen/qwen3.8-27b", temperature=0, max_tokens=800)

#RAG CHAIN
template = """Bạn là chuyên gia pháp lý. Dựa vào các điều luật được cung cấp dưới đây, hãy trả lời câu hỏi của người dùng một cách chính xác.
Nếu thông tin không có trong điều luật, hãy nói không biết, tuyệt đối không bịa đặt.

Điều luật liên quan:
{context}

Câu hỏi: {question}
Trả lời:"""
prompt = PromptTemplate.from_template(template)

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

rag_chain = (
    {"context": ensemble_retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# Biến retriever để file evaluate_rag.py gọi tới chấm điểm RAGAS
retriever = ensemble_retriever


# =====================================================================
# TÍNH NĂNG HỎI TRỰC TIẾP (CLI CHAT INTERFACE)
# =====================================================================
if __name__ == "__main__":
    print("\n=======================================================")
    print(" HỆ THỐNG RAG LUẬT SỞ HỮU TRÍ TUỆ (ADVANCED HYBRID SEARCH) ")
    print(" Gõ 'exit' hoặc 'quit' để thoát chương trình.")
    print("=======================================================\n")
    
    while True:
        try:
            query = input("\n[Người dùng hỏi]: ")
            if query.lower() in ["exit", "quit"]:
                print("Tạm biệt bạn!")
                break
            if not query.strip():
                continue
                
            print("⏳ Đang tìm kiếm và tổng hợp câu trả lời...")
            response = rag_chain.invoke(query)
            print(f"\n[AI Trả lời]:\n{response}")
            
        except Exception as e:
            print(f"[Lỗi xảy ra]: {e}")