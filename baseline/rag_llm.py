import os
from langchain_google_genai import ChatGoogleGenerativeAI

# Key đọc từ biến môi trường GOOGLE_API_KEY (không ghi cứng trong code).

if not os.environ.get("GOOGLE_API_KEY"):

    raise SystemExit("Thiếu biến môi trường GOOGLE_API_KEY")
model="gemini-3.6-flash"
temparature=0
llm = ChatGoogleGenerativeAI(model=model, temperature=temparature)

cau_hoi = "Hãy viết một bài thơ về mùa xuân bằng tiếng Việt."
cau_tra_loi = llm.invoke(cau_hoi)

print(cau_tra_loi.content[0]['text'])