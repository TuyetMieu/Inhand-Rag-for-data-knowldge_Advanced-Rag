import pandas as pd

# Bộ dữ liệu 50 câu hỏi bao quát các chương của Luật Sở hữu trí tuệ Việt Nam
data = [
    # --- NHÓM 1: QUYỀN TÁC GIẢ VÀ QUYỀN LIÊN QUAN (15 câu) ---
    {"question": "Quyền tác giả là gì?", "ground_truth": "Quyền tác giả là quyền của tổ chức, cá nhân đối với tác phẩm do mình sáng tạo ra hoặc sở hữu."},
    {"question": "Quyền liên quan đến quyền tác giả là gì?", "ground_truth": "Là quyền của tổ chức, cá nhân đối với cuộc biểu diễn, bản ghi âm, ghi hình, chương trình phát sóng, tín hiệu vệ tinh mang chương trình được mã hóa."},
    {"question": "Tác phẩm phái sinh là gì?", "ground_truth": "Là tác phẩm được sáng tạo trên cơ sở một hoặc nhiều tác phẩm đã có thông qua việc dịch, phóng tác, biên soạn, chú giải, tuyển chọn, cải biên, chuyển thể."},
    {"question": "Quyền nhân thân của tác giả bao gồm những quyền nào?", "ground_truth": "Gồm: Đặt tên tác phẩm; đứng tên thật hoặc bút danh; công bố tác phẩm; bảo vệ sự toàn vẹn của tác phẩm."},
    {"question": "Quyền tài sản của tác giả gồm những gì?", "ground_truth": "Làm tác phẩm phái sinh; biểu diễn tác phẩm trước công chúng; sao chép; phân phối, nhập khẩu; truyền đạt tác phẩm đến công chúng; cho thuê bản gốc hoặc bản sao."},
    {"question": "Thời hạn bảo hộ quyền nhân thân của tác giả?", "ground_truth": "Các quyền đặt tên, đứng tên và bảo vệ sự toàn vẹn của tác phẩm được bảo hộ vô thời hạn. Quyền công bố tác phẩm có thời hạn theo quyền tài sản."},
    {"question": "Thời hạn bảo hộ quyền tài sản đối với tác phẩm điện ảnh là bao lâu?", "ground_truth": "Bảo hộ 75 năm kể từ khi tác phẩm được công bố lần đầu tiên."},
    {"question": "Thời hạn bảo hộ đối với tác phẩm văn học, nghệ thuật thông thường?", "ground_truth": "Bảo hộ suốt cuộc đời tác giả và 50 năm tiếp theo năm tác giả qua đời."},
    {"question": "Các loại hình tác phẩm nào được bảo hộ quyền tác giả?", "ground_truth": "Tác phẩm văn học, khoa học, bài giảng, tác phẩm âm nhạc, sân khấu, điện ảnh, tạo hình, mỹ thuật ứng dụng, nhiếp ảnh, kiến trúc, bản họa đồ, chương trình máy tính."},
    {"question": "Chương trình máy tính được bảo hộ như thế nào?", "ground_truth": "Được bảo hộ như tác phẩm văn học, dù được thể hiện dưới dạng mã nguồn hay mã máy."},
    {"question": "Những đối tượng nào không thuộc phạm vi bảo hộ quyền tác giả?", "ground_truth": "Tin tức thời sự thuần túy đưa tin; Văn bản quy phạm pháp luật, văn bản hành chính; Quy trình, hệ thống, phương pháp hoạt động, khái niệm, nguyên lý, số liệu."},
    {"question": "Quyền của người biểu diễn bao gồm những gì?", "ground_truth": "Gồm quyền nhân thân (được giới thiệu tên, bảo vệ sự toàn vẹn hình tượng biểu diễn) và quyền tài sản (định hình, sao chép, phát sóng cuộc biểu diễn)."},
    {"question": "Tổ chức phát sóng có những quyền gì?", "ground_truth": "Có quyền độc quyền thực hiện hoặc cho phép người khác: Phát sóng lại; định hình chương trình; sao chép bản định hình; phân phối đến công chúng."},
    {"question": "Hành vi xâm phạm quyền tác giả phổ biến là gì?", "ground_truth": "Xâm phạm quyền nhân thân, mạo danh tác giả, sao chép, phân phối, truyền đạt tác phẩm mà không được phép của chủ sở hữu quyền tác giả."},
    {"question": "Đăng ký quyền tác giả có phải là thủ tục bắt buộc không?", "ground_truth": "Không bắt buộc. Quyền tác giả phát sinh tự động kể từ khi tác phẩm được định hình dưới một hình thức vật chất nhất định."},

    # --- NHÓM 2: SÁNG CHẾ VÀ KIỂU DÁNG CÔNG NGHIỆP (15 câu) ---
    {"question": "Sáng chế là gì?", "ground_truth": "Sáng chế là giải pháp kỹ thuật dưới dạng sản phẩm hoặc quy trình nhằm giải quyết một vấn đề xác định bằng việc ứng dụng các quy luật tự nhiên."},
    {"question": "Điều kiện chung để sáng chế được bảo hộ?", "ground_truth": "Sáng chế được bảo hộ nếu đáp ứng đủ 3 điều kiện: Có tính mới, có trình độ sáng tạo, và có khả năng áp dụng công nghiệp."},
    {"question": "Trường hợp nào sáng chế được bảo hộ dưới hình thức giải pháp hữu ích?", "ground_truth": "Khi sáng chế có tính mới, có khả năng áp dụng công nghiệp nhưng không phải là hiểu biết thông thường (không yêu cầu trình độ sáng tạo cao như sáng chế)."},
    {"question": "Tính mới của sáng chế được hiểu như thế nào?", "ground_truth": "Sáng chế chưa bị bộc lộ công khai dưới hình thức sử dụng, mô tả bằng văn bản hoặc bất kỳ hình thức nào khác ở trong nước hoặc nước ngoài trước ngày nộp đơn."},
    {"question": "Trình độ sáng tạo của sáng chế là gì?", "ground_truth": "Sáng chế là một bước tiến sáng tạo, không thể được tạo ra một cách dễ dàng đối với người có hiểu biết trung bình về lĩnh vực kỹ thuật tương ứng."},
    {"question": "Khả năng áp dụng công nghiệp của sáng chế là gì?", "ground_truth": "Có thể thực hiện được việc chế tạo, sản xuất hàng loạt sản phẩm hoặc áp dụng lặp đi lặp lại quy trình là nội dung của sáng chế và thu được kết quả ổn định."},
    {"question": "Đối tượng nào không được bảo hộ với danh nghĩa sáng chế?", "ground_truth": "Phát minh, lý thuyết khoa học, phương pháp toán học, sơ đồ, kế hoạch, luật chơi, chương trình máy tính, cách thức thể hiện thông tin, giống cây trồng, giống động vật."},
    {"question": "Kiểu dáng công nghiệp là gì?", "ground_truth": "Kiểu dáng công nghiệp là hình dáng bên ngoài của sản phẩm được thể hiện bằng hình khối, đường nét, màu sắc hoặc sự kết hợp những yếu tố này."},
    {"question": "Điều kiện bảo hộ kiểu dáng công nghiệp?", "ground_truth": "Có tính mới, có tính sáng tạo và có khả năng áp dụng công nghiệp."},
    {"question": "Thời hạn hiệu lực của Bằng độc quyền sáng chế là bao lâu?", "ground_truth": "Bằng độc quyền sáng chế có hiệu lực từ ngày cấp và kéo dài đến hết 20 năm kể từ ngày nộp đơn."},
    {"question": "Thời hạn hiệu lực của Bằng độc quyền giải pháp hữu ích?", "ground_truth": "Có hiệu lực từ ngày cấp và kéo dài đến hết 10 năm kể từ ngày nộp đơn."},
    {"question": "Thời hạn hiệu lực của Bằng độc quyền kiểu dáng công nghiệp?", "ground_truth": "Có hiệu lực 5 năm từ ngày nộp đơn, có thể gia hạn 2 lần liên tiếp, mỗi lần 5 năm."},
    {"question": "Ai có quyền đăng ký sáng chế, kiểu dáng công nghiệp?", "ground_truth": "Tác giả tự đầu tư chi phí, phương tiện vật chất hoặc tổ chức, cá nhân đầu tư kinh phí cho tác giả dưới hình thức giao việc, thuê việc."},
    {"question": "Quyền của chủ sở hữu Bằng độc quyền sáng chế?", "ground_truth": "Độc quyền sử dụng, cho phép người khác sử dụng, ngăn cấm người khác sử dụng và định đoạt sáng chế."},
    {"question": "Sử dụng sáng chế bao gồm những hành vi nào?", "ground_truth": "Sản xuất, áp dụng quy trình, khai thác công dụng, lưu thông, quảng cáo, chào hàng, tàng trữ, nhập khẩu sản phẩm được bảo hộ."},

    # --- NHÓM 3: NHÃN HIỆU, CHỈ DẪN ĐỊA LÝ VÀ BÍ MẬT KINH DOANH (10 câu) ---
    {"question": "Nhãn hiệu là gì?", "ground_truth": "Nhãn hiệu là dấu hiệu dùng để phân biệt hàng hoá, dịch vụ của các tổ chức, cá nhân khác nhau."},
    {"question": "Nhãn hiệu tập thể là gì?", "ground_truth": "Là nhãn hiệu dùng để phân biệt hàng hóa, dịch vụ của các thành viên của tổ chức là chủ sở hữu nhãn hiệu đó với tổ chức, cá nhân không phải là thành viên."},
    {"question": "Nhãn hiệu nổi tiếng là gì?", "ground_truth": "Là nhãn hiệu được bộ phận công chúng có liên quan biết đến rộng rãi trên lãnh thổ Việt Nam."},
    {"question": "Điều kiện bảo hộ nhãn hiệu?", "ground_truth": "Là dấu hiệu nhìn thấy được (hoặc âm thanh thể hiện dưới dạng đồ họa) và có khả năng phân biệt hàng hóa, dịch vụ của chủ sở hữu với chủ thể khác."},
    {"question": "Dấu hiệu nào không được bảo hộ làm nhãn hiệu?", "ground_truth": "Quốc kỳ, quốc huy, tên cơ quan nhà nước, dấu hiệu làm hiểu sai lệch tính chất hàng hóa, dấu hiệu trùng hoặc tương tự gây nhầm lẫn với nhãn hiệu đã được bảo hộ."},
    {"question": "Thời hạn bảo hộ của Giấy chứng nhận đăng ký nhãn hiệu?", "ground_truth": "10 năm kể từ ngày nộp đơn, có thể gia hạn nhiều lần liên tiếp, mỗi lần 10 năm."},
    {"question": "Chỉ dẫn địa lý là gì?", "ground_truth": "Chỉ dẫn địa lý là dấu hiệu dùng để chỉ sản phẩm có nguồn gốc từ khu vực, địa phương, vùng lãnh thổ hay quốc gia cụ thể."},
    {"question": "Điều kiện bảo hộ chỉ dẫn địa lý?", "ground_truth": "Sản phẩm mang chỉ dẫn phải có nguồn gốc địa lý từ khu vực tương ứng, và có danh tiếng, chất lượng hoặc đặc tính chủ yếu do điều kiện địa lý quyết định."},
    {"question": "Bí mật kinh doanh là gì?", "ground_truth": "Là thông tin thu được từ hoạt động đầu tư tài chính, trí tuệ, chưa được bộc lộ và có khả năng sử dụng trong kinh doanh."},
    {"question": "Tên thương mại là gì?", "ground_truth": "Tên thương mại là tên gọi của tổ chức, cá nhân dùng trong hoạt động kinh doanh để phân biệt chủ thể kinh doanh này với chủ thể kinh doanh khác."},

    # --- NHÓM 4: BẢO VỆ QUYỀN SỞ HỮU TRÍ TUỆ (10 câu) ---
    {"question": "Nguyên tắc nộp đơn đầu tiên (First-to-file) là gì?", "ground_truth": "Trường hợp có nhiều đơn đăng ký cho cùng một sáng chế, nhãn hiệu thì văn bằng bảo hộ chỉ được cấp cho đơn hợp lệ có ngày nộp đơn hoặc ngày ưu tiên sớm nhất."},
    {"question": "Cơ quan nào có thẩm quyền quản lý nhà nước về sở hữu công nghiệp?", "ground_truth": "Cục Sở hữu trí tuệ thuộc Bộ Khoa học và Công nghệ."},
    {"question": "Biện pháp xử lý hành vi xâm phạm quyền sở hữu trí tuệ?", "ground_truth": "Tùy tính chất, mức độ mà bị xử lý bằng biện pháp dân sự, hành chính hoặc hình sự."},
    {"question": "Biện pháp khẩn cấp tạm thời trong dân sự sở hữu trí tuệ gồm những gì?", "ground_truth": "Thu giữ, kê biên, niêm phong, cấm thay đổi hiện trạng, cấm di chuyển, cấm chuyển dịch quyền sở hữu hàng hóa xâm phạm."},
    {"question": "Quyền yêu cầu bồi thường thiệt hại bao gồm những gì?", "ground_truth": "Tổn thất về tài sản, mức giảm sút thu nhập, lợi nhuận, chi phí hợp lý để ngăn chặn và khắc phục thiệt hại, chi phí thuê luật sư."},
    {"question": "Hàng hóa giả mạo về sở hữu trí tuệ là gì?", "ground_truth": "Là hàng hóa, bao bì có gắn nhãn hiệu, chỉ dẫn địa lý giả mạo hoặc bao gồm hàng hóa sao chép lậu (xâm phạm quyền tác giả)."},
    {"question": "Thẩm quyền xử phạt vi phạm hành chính về sở hữu trí tuệ thuộc cơ quan nào?", "ground_truth": "Thanh tra Khoa học Công nghệ, Quản lý thị trường, Hải quan, Công an, Ủy ban nhân dân các cấp."},
    {"question": "Giống cây trồng được bảo hộ khi đáp ứng điều kiện gì?", "ground_truth": "Có tính mới, tính khác biệt, tính đồng nhất, tính ổn định và có tên gọi phù hợp."},
    {"question": "Chứng nhận đăng ký hợp đồng chuyển giao quyền sở hữu công nghiệp ở đâu?", "ground_truth": "Hợp đồng chuyển nhượng hoặc chuyển quyền sử dụng đối với các đối tượng đã được cấp văn bằng phải được đăng ký tại cơ quan quản lý nhà nước về sở hữu công nghiệp."},
    {"question": "Phí, lệ phí sở hữu trí tuệ do ai quy định?", "ground_truth": "Do Bộ Tài chính quy định."}
]

# Tạo DataFrame và xuất ra Excel
df = pd.DataFrame(data)
df.to_excel("dataset_luat.xlsx", index=False)

print(f"Đã tạo thành công file 'dataset_luat.xlsx' với {len(data)} câu hỏi kiểm thử!")