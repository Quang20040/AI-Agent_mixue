# Giao diện theo ngày hiện tại — 22/10/2026

- Đã bỏ trình giải mã tem và tem mô phỏng trên giao diện. Trang công thức chỉ còn sổ tay định lượng; nhãn điều hướng là “Công thức pha chế”. Giữ khóa điều hướng nội bộ cũ để các phiên đang mở không bị mất trang.
- Thẻ doanh thu/số ly dùng ngày hiện tại theo Asia/Ho_Chi_Minh; không lấy ngày cũ gần nhất làm kết quả hôm nay. Không có bản ghi thì hiện “Chưa có kết quả”; bản ghi số 0 vẫn hiện 0. Chỉ so với đúng hôm qua nếu có dữ liệu cả hai ngày.
- Biểu đồ dùng đúng 7 ngày lịch đến hôm nay. Ngày thiếu hiện “Chưa có”; không tạo cột doanh thu 0 giả. Tổng tuần chỉ hiện khi đủ 7 ngày, nếu thiếu thì báo chưa đủ dữ liệu.
- Trang chủ truy vấn lại dữ liệu mỗi 30 giây khi mở trang và có nút làm mới ngay; đã bỏ cache bán hàng không có thời hạn. Đây là cập nhật từ database: chưa có kết nối tự thu thập giao dịch trực tiếp từ POS. Cần nhập/đồng bộ dữ liệu bán hàng để có số mới.
- Dự báo tóm tắt trang chủ hướng đến ngày mai thực tế; lịch sử chưa cập nhật hôm nay thì không hiển thị dự báo cho một ngày cũ như dự báo hiện tại.
- Chat thành một trang riêng, một cột hội thoại rộng tối đa 900px, chữ lớn hơn, nội dung chạy theo chiều dài trang, một ô nhập tin, có lịch sử, trò chuyện mới, nguồn và xác nhận thao tác. Đã bỏ popover nổi và gợi ý giải mã tem. Không thay mô hình AI hoặc giả lập streaming để tạo cảm giác đang sinh token.

Kiểm tra: 4 ca logic ngày thiếu/0/ngày tương lai/ngày hôm qua đạt; Streamlit AppTest trên bản sao chỉ chứa dữ liệu giả xác minh dữ liệu cũ không thành hôm nay, bản ghi 0 mới được đọc lại, không còn decoder, gửi chat và tạo hội thoại mới hoạt động. Bằng chứng `output/remediation-sales-view-tests.xml` và `output/remediation-ui-0f3159ec/result.txt`. Không dùng thông tin đăng nhập thật để kiểm thử UI; không sửa dữ liệu cửa hàng.
