import os
from groq import Groq

# Key đọc từ biến môi trường GROQ_API_KEY (không ghi cứng trong code).
if not os.environ.get("GROQ_API_KEY"):
    raise SystemExit("Thiếu biến môi trường GROQ_API_KEY")
client = Groq()
print("Danh sách các mô hình đang khả dụng cho tài khoản của bạn:")
for model in client.models.list().data:
    print(f"- {model.id}")