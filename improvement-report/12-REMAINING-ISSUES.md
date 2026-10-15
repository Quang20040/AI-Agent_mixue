# BÁO CÁO CÁC VẤN ĐỀ TỒN ĐỌNG & LỘ TRÌNH TƯƠNG LAI (REMAINING ISSUES & ROADMAP)
## BeverageOps AI — Quản Trị Vận Hành Chi Nhánh Mixue 39 Tôn Quang Phiệt

---

### 1. CÁC NỢ KỸ THUẬT ĐƯỢC CHẤP NHẬN TRONG PHA THỬ NGHIỆM ĐƠN CỬA HÀNG

Toàn bộ các lỗi nghiêm trọng (P0) và lỗi ảnh hưởng nghiệp vụ cốt lõi (P1/P2) đã được xử lý 100%. Các mục kỹ thuật dưới đây là những tối ưu hóa nâng cao được ghi nhận và đưa vào kế hoạch phát triển (Backlog) cho các phiên bản tiếp theo khi mở rộng chuỗi:

| ID | Hạng mục | Mức độ | Mô tả kỹ thuật | Lý do trì hoãn trong Phase 3 | Kế hoạch xử lý dự kiến |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **DEBT-01** | Timezone-aware Datetime | P3 | Chuyển đổi toàn bộ `datetime.now()` sang `datetime.now(timezone.utc)` hoặc `zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")` | Quán 39 Tôn Quang Phiệt hoạt động tại Hà Nội (GMT+7 cố định), SQLite và dữ liệu hiện tại lưu trữ ISO-8601 string đồng nhất | Chuyển đổi khi mở rộng hệ thống sang chuỗi nhiều chi nhánh liên tỉnh |
| **DEBT-02** | Kết nối trực tiếp máy POS phần cứng | P3 | Tích hợp Webhook/API trực tiếp từ máy in bill quầy bar và cổng thanh toán ngân hàng | Hiện tại tính năng nạp dữ liệu ca trực và OCR hóa đơn đã đáp ứng 100% nghiệp vụ đóng ca | Triển khai khi Mixue Việt Nam cung cấp cổng Open API chính thức |
| **DEBT-03** | Streaming Token LLM | P3 | Hỗ trợ phản hồi chữ chạy từng dòng (Streaming UI) khi trò chuyện với Tuyết Vương AI | Cơ chế hiện tại trả về toàn bộ câu trả lời kèm thẻ ReAct Grounding rõ ràng, tốc độ phản hồi cục bộ < 1s | Cập nhật cùng bản nâng cấp UI tiếp theo |
| **DEBT-04** | Bộ đệm Redis phân tán | P3 | Thay thế bộ đệm in-memory bằng cụm Redis tập trung | Hiện tại hệ thống chạy đơn phiên bản (Single Instance) cho 1 cửa hàng, in-memory cache cho tốc độ nhanh nhất | Triển khai khi triển khai Kubernetes Multi-replica |

---

### 2. KẾ HOẠCH BẢO TRÌ & GIÁM SÁT HỆ THỐNG (OPERATIONAL RUNBOOK)

1. **Sao lưu dữ liệu định kỳ (Database Backup):**
   - Thiết lập cron job hàng ngày sao lưu file SQLite `data/beverageops.db` hoặc backup database PostgreSQL vào lúc 23:30 (sau ca tối).
2. **Kiểm tra nhật ký lỗi (Log Monitoring):**
   - Định kỳ kiểm tra file log tại `logs/` để phát hiện sớm các yêu cầu kho bị từ chối hoặc lỗi nhập sai định lượng từ nhân viên mới.
3. **Đào tạo nhân sự:**
   - Hướng dẫn nhân viên mới quy trình Maker-Checker: Nhân viên gửi đề xuất -> Quản lý duyệt trước khi bốc dỡ nguyên liệu khỏi kho.
