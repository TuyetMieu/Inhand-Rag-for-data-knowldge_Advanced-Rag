"""Prompt và JSON schema cho các bước dùng LLM của đồ thị.

Bước chấm context không còn là một lượt LLM riêng: answer tự trả câu NOT_ENOUGH khi tài liệu không đủ
(xem nodes.grade).
"""

SYSTEM = (
    "Bạn là trợ lý cho nhân viên kinh doanh bất động sản tại Việt Nam: tra cứu hồ sơ khách hàng "
    "và gợi ý căn cứ pháp lý. Luôn viết tiếng Việt có dấu, ngắn gọn, chính xác."
)

# ① Hiểu câu hỏi -------------------------------------------------------------------------------
UNDERSTAND = """Phân loại câu hỏi của nhân viên và chuẩn bị truy vấn tìm kiếm.

Nguồn dữ liệu có:
- "hoso": hồ sơ giao dịch của khách hàng (mã hồ sơ dạng KH002): phiếu thông tin, hợp đồng đặt cọc, hợp đồng mua bán, phụ lục tiến độ thanh toán, hồ sơ vay ngân hàng, biên bản bàn giao, giấy tờ cấp sổ, hoa hồng môi giới.
- "luat": văn bản pháp luật bất động sản: Luật Kinh doanh bất động sản 2023, Luật Nhà ở 2023, Luật Đất đai 2024, Bộ luật Dân sự 2015 và các nghị định hướng dẫn.

Trả về JSON:
- "nguon": "hoso" nếu chỉ hỏi nội dung hồ sơ; "luat" nếu chỉ hỏi quy định pháp luật; "ca_hai" nếu cần đối chiếu hồ sơ với quy định (ví dụ "có đúng quy định không", "có vượt mức không", "đã làm đúng hạn chưa"); "ngoai_pham_vi" nếu không liên quan tới hồ sơ khách hàng hay pháp luật bất động sản.
- "cau_hoi_doc_lap": viết lại câu hỏi cho đủ nghĩa khi đọc riêng (thay "khách này", "căn đó"... bằng thông tin trong hội thoại trước). Nếu câu hỏi đã đủ nghĩa thì giữ nguyên.
- "truy_van_luat": nếu nguon là "luat" hoặc "ca_hai", viết một câu tìm kiếm bằng thuật ngữ pháp lý chung cho ĐÚNG nội dung câu hỏi này, không chứa mã hồ sơ hay tên người. Ví dụ với câu hỏi "Hợp đồng thuê của khách X có được chuyển nhượng cho người khác không?" thì viết "điều kiện chuyển nhượng hợp đồng thuê nhà ở". Dùng từ trong văn bản luật thay cho từ thường ngày: "sổ hồng", "sổ đỏ" là "giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất"; "cọc" là "đặt cọc"; "nhà đang xây" là "nhà ở hình thành trong tương lai". Nếu không cần thì để chuỗi rỗng.
"""

UNDERSTAND_SCHEMA = {
    "type": "object",
    "properties": {
        "nguon": {"type": "string", "enum": ["hoso", "luat", "ca_hai", "ngoai_pham_vi"]},
        "cau_hoi_doc_lap": {"type": "string"},
        "truy_van_luat": {"type": "string"},
    },
    "required": ["nguon", "cau_hoi_doc_lap", "truy_van_luat"],
}

# Viết lại truy vấn ------------------------------------------------------------------------------
REWRITE = """Lần tìm kiếm trước không đủ thông tin để trả lời câu hỏi.
CÂU HỎI: {question}
TRUY VẤN ĐÃ DÙNG: hồ sơ: "{q_hoso}"; luật: "{q_luat}"
TÀI LIỆU ĐÃ TÌM ĐƯỢC (không đủ để trả lời): {tim_thay}

Viết lại truy vấn tìm kiếm theo cách khác: dùng từ đồng nghĩa, tên loại giấy tờ hoặc thuật ngữ pháp lý có thể xuất hiện trong văn bản.
Trả về JSON với "truy_van_hoso" và "truy_van_luat" (để chuỗi rỗng nếu không tìm nguồn đó)."""

REWRITE_SCHEMA = {
    "type": "object",
    "properties": {"truy_van_hoso": {"type": "string"}, "truy_van_luat": {"type": "string"}},
    "required": ["truy_van_hoso", "truy_van_luat"],
}

# ⑥ Trả lời --------------------------------------------------------------------------------------
ANSWER = """NHIỆM VỤ: Trả lời CÂU HỎI chỉ bằng thông tin trong TÀI LIỆU ở trên.
Quy tắc:
- Trả lời thẳng vào câu hỏi, không nhắc lại câu hỏi. Tối đa 4 ý, mỗi ý một dòng bắt đầu bằng "- ", mỗi ý không quá 2 câu.
- Cuối mỗi ý ghi mã nguồn trong ngoặc vuông, chép đúng mã ở đầu đoạn tài liệu, ví dụ [KH002-G1-011] hoặc [LKDBDS-2023-D25]. Không dùng mã không có trong tài liệu. Ý nêu "Điều N" thì phải trích đúng mã của Điều N.
- Chép nguyên số tiền, tỷ lệ, ngày tháng như trong tài liệu. KHÔNG tự cộng, nhân, chia hay so sánh số: nếu tài liệu chưa có sẵn phép tính thì chỉ nêu các số liệu và mức luật quy định để người đọc đối chiếu.
- Nếu tài liệu nêu một tổng số và các khoản thành phần, câu trả lời chính là tổng số.
- Khi đối chiếu hồ sơ với luật: nêu số liệu trong hồ sơ, nêu mức luật quy định (Điều, khoản). Chỉ kết luận đạt hay vượt khi tài liệu đã ghi sẵn kết luận đó.
- Nếu tài liệu không có thông tin để trả lời, chỉ viết đúng câu: "Không đủ căn cứ trong tài liệu được cung cấp." Không suy đoán, không bịa.

CÂU HỎI: {question}"""

NOT_ENOUGH = "Không đủ căn cứ trong tài liệu được cung cấp."
OUT_OF_SCOPE = ("Câu hỏi nằm ngoài phạm vi hỗ trợ. Tôi chỉ trả lời về hồ sơ khách hàng và quy định pháp luật "
                "bất động sản có trong kho tài liệu.")
LEGAL_NOTE = "Gợi ý pháp lý dựa trên văn bản trong kho, không thay thế ý kiến của luật sư hoặc pháp chế."
