import time
import pandas as pd
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

#nhập từ mainrag.py
from mainrag import rag_chain, retriever

#Giám khảo Local (Ollama)
print("Đang kết nối với giám khảo Ollama (qwen2.5:7b)...")
judge_llm = ChatOllama(model="qwen2.5:7b", temperature=0, num_gpu=0)

judge_prompt = ChatPromptTemplate.from_template("""
Bạn là hệ thống chấm điểm tự động. Đánh giá câu trả lời dựa trên Ngữ cảnh và Câu hỏi.
Tuyệt đối không giải thích, không viết thêm bất kỳ từ nào. Chỉ in ra đúng 2 con số từ 1 đến 5, cách nhau bởi dấu phẩy theo đúng thứ tự:
[Điểm Faithfulness (Bám sát ngữ cảnh)], [Điểm Relevance (Trúng trọng tâm câu hỏi)]

Câu hỏi: {question}
Ngữ cảnh: {context}
Câu trả lời cần chấm: {answer}
""")

evaluation_chain = judge_prompt | judge_llm | StrOutputParser()

def run_evaluation():
    # Đọc bộ dữ liệu
    print("Đang tải dữ liệu từ dataset_luat.xlsx...")
    try:
        df = pd.read_excel("dataset_luat.xlsx")
    except FileNotFoundError:
        print("Lỗi: Không tìm thấy file dataset_luat.xlsx trong thư mục!")
        return

    # Khởi tạo các cột lưu điểm
    faithfulness_scores = []
    relevance_scores = []
    generated_answers = []

    print("\nBắt đầu chạy luồng RAG và chấm điểm...\n")
    print("-" * 40)

    # Vòng lặp duyệt qua từng câu hỏi trong file Excel
    for index, row in df.iterrows():
        # Giả định cột chứa câu hỏi trong file Excel của bạn tên là 'Câu hỏi'
        question = row.get('Câu hỏi', row.iloc[0]) 
        
        #Chạy RAG để lấy câu trả lời và ngữ cảnh
        docs = retriever.invoke(question)
        context = "\n".join([doc.page_content for doc in docs])
        answer = rag_chain.invoke(question)
        
        generated_answers.append(answer)

        #Ollama chấm điểm
        score_str = evaluation_chain.invoke({
            "question": question,
            "context": context,
            "answer": answer
        })
        import re
        try:
            # Tìm tất cả câu trả lời của LLM
            numbers = re.findall(r'\d+', score_str)
            if len(numbers) >= 2:
                f_score = int(numbers[0])
                r_score = int(numbers[1])
            else:
                # Nếu LLM thực sự không trả
                f_score, r_score = None, None
                print(f"    -> [Cảnh báo] LLM trả lời lạc đề: {score_str.strip()}")
        except Exception:
            f_score, r_score = None, None
        
        faithfulness_scores.append(f_score)
        relevance_scores.append(r_score)
        
        print(f"Câu {index + 1}: Faithfulness={f_score}/5 | Relevance={r_score}/5")
        time.sleep(3)  # Nghỉ để API hồi tokens   
    print("-" * 40)
    
    #Lưu kết quả thành báo cáo
    df['Câu trả lời của RAG'] = generated_answers
    df['Điểm Faithfulness'] = faithfulness_scores
    df['Điểm Relevance'] = relevance_scores
    
    output_file = "ragas_report_custom.xlsx"
    df.to_excel(output_file, index=False)
    print(f"Hoàn tất! Báo cáo thông số đã được lưu tại: {output_file}")

if __name__ == "__main__":
    run_evaluation()