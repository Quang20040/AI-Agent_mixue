# 09 – PRODUCT READINESS & GAP ANALYSIS (ĐÁNH GIÁ ĐỘ SẴN SÀNG SẢN PHẨM & KHOẢNG TRỐNG TÍNH NĂNG)

> **Góc nhìn đánh giá:** Product Manager (PM) & Senior Business Analyst  
> **Mục tiêu:** Thẩm định mức độ hoàn thiện của hệ thống dưới góc độ một giải pháp SaaS / Quản trị F&B thương mại hóa trước khi bàn giao cho chuỗi cửa hàng.  

---

## 1. PHÂN TÍCH 10 CÂU HỎI PRODUCT READINESS REVIEW

### 1.1. Những tính năng nào thực sự có ích và mang lại giá trị cao nhất?
1. **Quy trình Kiểm soát Kho 2 Bước (Maker - Checker Workflow):** Đây là tính năng có giá trị vận hành thực tế cao nhất. Nhân viên quầy bar chỉ có quyền gửi đề xuất, Quản lý Bùi Văn Quang phải trực tiếp bấm Duyệt thì thẻ kho mới được ghi nhận. Điều này triệt tiêu hoàn toàn rủi ro nhân viên tự ý điều chỉnh số liệu kho hoặc biển thủ nguyên liệu.
2. **Sổ tay Định lượng BOM & Giải mã Tem dán ly 5 chữ số:** Hỗ trợ đào tạo nhân viên mới cực kỳ hiệu quả. Khi khách đặt món qua app hoặc tại quầy, barista chỉ cần nhập mã tem (ví dụ: `24101`) là biết ngay định lượng đường, đá, topping và quy chuẩn SOP mà không cần tra sổ giấy cồng kềnh.
3. **Kế hoạch Sơ chế Làm tròn Mẻ chuẩn Mixue & Thẩm định Độc lập:** Tự động quy đổi nhu cầu tiêu thụ thành số lượng mẻ nguyên (5.000ml trà, 1.000g trân châu) kèm thời gian bảo quản SOP (4 giờ) giúp quán tránh lãng phí và đảm bảo vệ sinh an toàn thực phẩm.
4. **Đối soát Chốt Ca Bằng Ảnh (AI OCR) vs Máy POS:** Tự động đọc doanh thu từ sổ tay chốt ca và so sánh trực tiếp với thực thu POS, phát hiện chênh lệch chỉ trong vài giây.

---

### 1.2. Những tính năng nào khó sử dụng hoặc gây cản trở?
1. **Bảng Sổ Thẻ Kho Ma Trận 31 Ngày:** Mặc dù rất chi tiết nhưng việc hiển thị hơn 40 cột ngang cùng lúc gây quá tải thị giác (cognitive overload). Quản lý phải cuộn ngang liên tục để tìm ngày cần kiểm tra. Cần mặc định hiển thị theo Tuần hiện tại thay vì hiển thị cả tháng.
2. **Chế độ Sửa Ô Trực Tiếp bằng tay (`st.data_editor`):** Việc cho phép bấm đúp sửa số liệu nhưng lại yêu cầu phải nhớ bấm thêm nút *"💾 Lưu Các Ô Đã Sửa Vào Sổ Kho"* ở phía dưới là một điểm gây cản trở lớn. Người dùng quen với Excel hoặc Google Sheets (vốn tự động lưu) sẽ dễ bị mất dữ liệu khi chuyển sang tab khác.

---

### 1.3. Có bước nào gây cản trở (Friction Points) trong quy trình thao tác không?
- **Vị trí nút Đăng xuất:** Nút Đăng xuất bị ẩn trong sidebar thu gọn (collapsed sidebar). Khi bàn giao ca làm việc giữa ca sáng và ca chiều, nhân viên mới thường lúng túng không biết đăng xuất ở đâu để nhân viên ca sau đăng nhập.
- **Thời gian chờ dự báo 14 giây:** Chờ 14 giây mà không có thanh tiến trình % tạo cảm giác ứng dụng bị đơ.

---

### 1.4. Có quy trình nghiệp vụ nào chưa khép kín (Broken or Open-loop Workflows) không?
1. **Quy trình Đơn Đặt Hàng PO chưa có bước "Xác nhận Nhập kho Thực tế" (Goods Receipt):** 
   - Hiện tại: Quản lý bấm "Ký duyệt Đơn Nhập Hàng" $\rightarrow$ Đơn hàng chuyển sang trạng thái APPROVED.
   - Khoảng trống: Khi xe hàng tổng Mixue chở nguyên liệu đến cửa hàng 2 ngày sau đó, hệ thống chưa có nút **"Xác nhận Đã Nhận Hàng PO"** để tự động cộng số lượng thùng/kiện đó vào cột Nhập của Ma trận thẻ kho. Hiện tại Quản lý phải tự vào tạo một lệnh nhập kho riêng biệt bằng tay, gây đứt gãy giữa khâu đặt hàng và khâu nhận hàng.
2. **Quy trình Chốt Ca AI OCR chưa tự động sinh phiếu điều chỉnh kho:**
   - Khi phát hiện hao hụt nguyên liệu trong ca, hệ thống chưa cho phép tạo nhanh một phiếu "Xuất hủy do hỏng/đổ" ngay từ màn hình chốt ca.

---

### 1.5. Có tính năng nào chỉ mang tính trình diễn (Demo/Mock)?
- **Nút "Ký duyệt Đơn Nhập Hàng":** Hệ thống hiển thị thông báo đã ký duyệt và cấp mã đơn, tuy nhiên chưa có chức năng xuất file PDF phiếu đặt hàng chính thức để gửi qua Zalo/Email cho Tổng kho phân phối Mixue.

---

### 1.6. Những chức năng cốt lõi nào còn thiếu để thành sản phẩm thương mại hoàn chỉnh?
1. **Module Nhà Cung Cấp & Giao Nhận (Supplier & Delivery Tracking):** Theo dõi trạng thái xe hàng từ tổng kho Mixue về 39 Tôn Quang Phiệt (Đang vận chuyển / Đã giao quầy).
2. **Hệ thống Thông báo Thời gian thực (Real-time Notifications / Webhook):** Khi nhân viên quầy bar tạo đề xuất lệnh kho, Quản lý phải nhận được thông báo chuông hoặc tin nhắn Zalo/Telegram để duyệt ngay, thay vì phải chủ động F5 vào hòm thư.
3. **Báo cáo Lợi Nhuận Gộp & Chi Phí Giá Vốn (P&L / COGS Analytics):** Hệ thống đã có doanh thu bán hàng và lượng tiêu thụ nguyên liệu, nhưng chưa tổng hợp thành biểu đồ chi phí giá vốn (COGS %) theo ngày để Chủ quán biết được tỷ suất sinh lời ròng.
4. **Nhật ký Kiểm toán Toàn diện (Audit Trail Log):** Ghi nhận chi tiết ai đã sửa ô nào, vào lúc mấy giờ, từ giá trị cũ bao nhiêu thành giá trị mới bao nhiêu để phục vụ kiểm toán nội bộ khi xảy ra thất thoát tiền/hàng.

---

### 1.7. Người dùng có thể tự sử dụng mà không cần hướng dẫn không?
- **Với Nhân viên:** **Rất dễ sử dụng (8.5/10)**. Màn hình của nhân viên rất gọn gàng (chỉ có 4 tab), giao diện tra cứu món và tem dán trực quan, có Tuyết Vương AI hỗ trợ giải đáp công thức ngay lập tức.
- **Với Quản lý / Chủ quán:** **Khá dễ sử dụng (7.5/10)**. Các bảng số liệu ma trận kho và đối soát BOM cần được hướng dẫn khoảng 15-20 phút trong buổi onboarding đầu tiên để nắm rõ ý nghĩa các cột màu xanh dương (nhập), xanh lá (chốt tồn).

---

### 1.8. Có lý do nào khiến người dùng mất niềm tin không?
- Khi nhập sai mã tem dán ly mà chiếc tem cũ vẫn hiển thị bên dưới, barista có thể nghi ngờ tính chính xác của công cụ tra cứu.
- Khi sửa ô ma trận kho mà chuyển tab bị mất số liệu, người quản lý sẽ lo ngại về tính toàn vẹn dữ liệu của hệ thống.

---

### 1.9. Sản phẩm đã đủ điều kiện để phát hành chính thức (Go-Live) chưa?
- **Kết luận:** **CONDITIONAL GO (ĐỦ ĐIỀU KIỆN PHÁT HÀNH CÓ ĐIỀU KIỆN)**.
- Sản phẩm có độ ổn định kỹ thuật rất cao (không phát sinh lỗi crash P0/P1, phân quyền RBAC kiên cố, cơ sở dữ liệu đồng bộ chính xác). Tuy nhiên, cần khắc phục 6 lỗi P2 (xóa tem dán cũ khi lỗi, cảnh báo âm kho, cảnh báo chưa lưu dữ liệu, nút đăng xuất tiện lợi) trước khi bàn giao rộng rãi cho toàn bộ nhân sự tại quầy.
