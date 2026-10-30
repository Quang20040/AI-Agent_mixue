# OCR nhiều ảnh chốt ca — 22/10/2026

Người dùng đã đồng ý rõ việc gửi ba ảnh được cung cấp tới OpenRouter và nhà cung cấp mô hình phía sau để kiểm tra OCR. Các lần thử chỉ lưu kết quả chẩn đoán trong `data/agent_private/`, không tạo hoặc duyệt báo cáo chốt ca, không nhập số liệu vào PostgreSQL/JSON nghiệp vụ.

## Kết quả chẩn đoán

Cấu hình hiện dùng `dots-studio/dots-3-note-preview:free`. Lần thử lại ban đầu đã nhận JSON, chưa tái hiện chính xác lỗi dịch vụ người dùng gặp trước đó. Tuy nhiên kết quả có nhiều trường sai nguồn/sai dòng, ví dụ trộn Cash trên POS với tiền mặt sổ và nhầm BeFood/GrabFood. Không thể kết luận do ảnh mờ: kiểm tra ảnh cục bộ không đánh dấu ba ảnh này là mờ. Mô hình trả kết quả không đồng nghĩa số liệu đã đúng.

Các lỗi nội bộ đã xác định và sửa:

- Đọc nhiều ảnh cùng một yêu cầu dễ trộn ca/nguồn: giờ đọc từng ảnh độc lập, đối soát sau; tối đa 5 ảnh, 2 yêu cầu đồng thời.
- Trùng ảnh không cộng thành hai khoản thu. Số khác nhau giữa các ảnh giữ nguyên các ứng viên và yêu cầu kiểm tra. Ưu tiên nguồn sổ cho khoản thu ca, nguồn POS cho các tổng POS.
- Ngày `20/10/26` và `2026-10-20` được chuẩn hóa cùng ngày; không tự thay bằng ngày người dùng chọn. Nếu ngày giữa các ảnh thực sự khác nhau thì yêu cầu kiểm tra.
- Có chỉ dấu `requested_shift_present` để loại tiền của ca khác khỏi ca đang chọn. Đây vẫn là kết quả nhận diện của mô hình, không phải bảo đảm mô hình hiểu đúng mọi ảnh.
- Bổ sung hướng dẫn tách số dư tài khoản, két cố định, tiền dư/thiếu và nhãn từng dòng. Không tự cộng biểu thức hoặc nhân 1.000 khi đơn vị chưa rõ.
- Tách lỗi giới hạn lượt gọi, timeout, quyền API, JSON không hợp lệ và phản hồi bị cắt; không công khai exception chứa dữ liệu riêng/khóa.
- Tăng ngân sách kết quả JSON, rút ngắn phần chép chữ không liên quan và tắt retry SDK của OCR để không nhân thời gian chờ nhiều ảnh.
- Giao diện luôn hiển thị bảng chữ/số đã đọc và trạng thái kiểm tra, kể cả khi không ô nào đủ chắc để tự điền. Có nội dung đọc riêng của từng ảnh; lỗi một ảnh không xóa kết quả ảnh khác. Đổi khóa cache để không giữ kết quả của pipeline cũ.

## Xác minh

23 kiểm thử OCR cuối đạt trong `output/remediation-ocr-final-tests.xml`. Nhóm OCR và tích hợp LangGraph trước lượt cuối: 29 PASS trong `output/remediation-ocr-full-tests.xml`. Có kiểm thử giữ nguyên kết quả khi ảnh khác lỗi, không cộng ảnh trùng, không lấy Cash POS thay tiền mặt sổ, mâu thuẫn nguồn, ngày Việt Nam/ISO, ca khác, phản hồi bị cắt và lỗi 429 không lộ secret.

Thử ảnh thật có kết quả `NEEDS_REVIEW`, nội dung đọc thô và ứng viên từng ảnh trong `data/agent_private/ocr-three-photos-final.json`. Chất lượng mô hình hiện tại vẫn chưa đủ tin cậy để khẳng định đã đọc đúng tất cả khoản. Các trường mơ hồ/sai nguồn/mâu thuẫn tiếp tục để trống khi tự điền; người dùng phải kiểm tra ảnh trước khi xác nhận. Không có cơ chế tự chuyển sang mô hình trả phí.

Tham khảo khả năng mô hình (không phải bằng chứng độ chính xác OCR): https://openrouter.ai/dots-studio/dots-3-note-preview:free .
