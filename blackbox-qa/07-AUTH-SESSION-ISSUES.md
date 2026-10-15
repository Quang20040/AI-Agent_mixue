# 07 – AUTHENTICATION, SESSION & SECURITY REPORT (BÁO CÁO KIỂM THỬ XÁC THỰC & PHIÊN LÀM VIỆC)

> **Dự án:** BeverageOps AI — Quản trị Điều phối Vận hành Chi nhánh Mixue 39 Tôn Quang Phiệt  
> **Chuyên môn đánh giá:** Security & Authentication QA Specialist  
> **Tiêu chuẩn an toàn:** OWASP Application Security Verification Standard (ASVS v4.0)  

---

## 1. TỔNG QUAN HỆ THỐNG XÁC THỰC & BẢO MẬT (AUTH ARCHITECTURE)

Hệ thống triển khai cơ chế xác thực đa lớp:
1. **Lớp lưu trữ mật khẩu:** Mã hóa mật khẩu một chiều bằng thuật toán **SHA-256** (`hash_password()`) kết hợp kiểm tra xác thực đối sánh an toàn.
2. **Lớp phân quyền RBAC 2 cấp độ:**
   - **ADMIN:** Gồm 2 vai trò `OWNER` (Nguyễn Hạnh Chi) và `MANAGER` (Bùi Văn Quang).
   - **STAFF:** Gồm `STAFF_OFFICIAL` (Nhân viên quầy pha chế chính thức) và `STAFF_PROBATION` (Nhân viên mới/thử việc).
3. **Chính sách mật khẩu lần đầu:** Nhân viên mới được cấp mật khẩu mặc định `123456`. Khi đăng nhập lần đầu, cờ `must_change_password=True` chặn toàn bộ giao diện làm việc và buộc nhân viên phải thiết lập mã PIN 6 số cá nhân.

---

## 2. KẾT QUẢ KIỂM THỬ CÁC TÌNH HUỐNG XÁC THỰC

### 2.1. Đăng nhập đúng (Valid Login)
- **Tài khoản thử nghiệm:** `quanly` / `123` và `nhanvien` / `123`.
- **Kết quả:** Đăng nhập thành công 100%, nạp đúng chức danh, huy hiệu phân quyền và danh sách trang được phép xem.
- **Đánh giá:** **PASS**

### 2.2. Đăng nhập sai mật khẩu (Wrong Password)
- **Tài khoản thử nghiệm:** `quanly` / `sai_mat_khau`.
- **Kết quả:** Hệ thống từ chối đăng nhập, hiển thị thông báo lỗi màu đỏ.
- **Đánh giá:** **PASS**

### 2.3. Tên đăng nhập không tồn tại (Non-existent Username)
- **Tài khoản thử nghiệm:** `user_khong_ton_tai` / `123456`.
- **Kết quả:** Hệ thống từ chối đăng nhập với thông báo lỗi chung, không tiết lộ tài khoản có tồn tại hay không trong DB (ngăn chặn kỹ thuật Username Enumeration Attack).
- **Đánh giá:** **PASS**

### 2.4. Mật khẩu hoặc tài khoản rỗng (Empty Inputs)
- **Kết quả:** Bị chặn đăng nhập. Tuy nhiên, thông báo lỗi báo *"Tên đăng nhập hoặc mật khẩu không chính xác!"* thay vì yêu cầu điền thông tin (đã ghi nhận BUG-AUTH-01).
- **Đánh giá:** **PASS về an toàn / Cần sửa UX**

### 2.5. Tấn công tiêm nhiễm SQL Injection (SQLi Attack)
- **Chuỗi thử nghiệm:** `' OR '1'='1' --` và `admin'--`.
- **Kết quả:** SQLAlchemy ORM sử dụng Parameterized Queries nên chuỗi đầu vào bị xử lý như chuỗi ký tự thông thường, hoàn toàn miễn nhiễm với SQL Injection.
- **Đánh giá:** **PASS**

### 2.6. Quy trình Đăng xuất (Logout Flow)
- **Thao tác:** Bấm nút "🚪 Đăng xuất khỏi Hệ thống" trong Sidebar.
- **Kết quả:** Toàn bộ các khóa session state nhạy cảm (`authenticated`, `user`, `username`, `user_role`, `user_name`, `chat_history_vi`) đều bị `pop()` xóa sạch.
- **Đánh giá:** **PASS**

### 2.7. Sử dụng nút Back trình duyệt sau khi Đăng xuất (Browser History Back)
- **Thao tác:** Sau khi đăng xuất về màn hình Login, nhấn phím Back trên trình duyệt.
- **Kết quả:** Nhờ cơ chế kiểm tra bắt buộc `if not st.session_state.get("authenticated", False): render_login_screen(); st.stop()`, trang lập tức nhận diện chưa xác thực và giữ người dùng ở lại màn hình đăng nhập. Không có bất kỳ dữ liệu nhạy cảm nào bị lộ.
- **Đánh giá:** **PASS**

### 2.8. Duy trì phiên làm việc khi Tải lại trang (F5 / Refresh Retention)
- **Thao tác:** Đang làm việc trong phiên Admin, thực hiện F5 tải lại trang.
- **Kết quả:** Phiên làm việc được duy trì qua session của Streamlit, người dùng không bị văng ra đăng nhập lại phiền toái.
- **Đánh giá:** **PASS**

### 2.9. Truy cập trái phép vào trang Quản trị khi chưa được cấp quyền (Direct Access Bypass)
- **Thao tác:** Đăng nhập tài khoản `nhanvien` (Staff), thử can thiệp vào tham số section để gọi các trang `Dự báo`, `Nhập hàng`, `Quản lý nhân viên`.
- **Kết quả:** Hàm `can_access_page(user_role, section)` chặn đứng tại tầng logic điều hướng và xuất cảnh báo: *"🔒 Truy cập bị từ chối: Bạn không có quyền truy cập trang này. Chức năng chỉ dành riêng cho Quản lý và Chủ cửa hàng (Admin)."*
- **Đánh giá:** **PASS**

---

## 3. DANH SÁCH VẤN ĐỀ XÁC THỰC & PHIÊN LÀM VIỆC CẦN LƯU Ý

| Mã lỗi | Phân loại | Mô tả vấn đề | Rủi ro | Mức độ |
|---|---|---|---|---|
| **AUTH-ISSUE-01** | UX Error | Để trống username/password nhưng hệ thống báo lỗi "Mật khẩu không chính xác" | Gây khó hiểu cho người dùng mới | **P3 (Low)** |
| **AUTH-ISSUE-02** | Session Timeout | Streamlit chưa cấu hình thời gian hết hạn phiên làm việc tự động (Auto Idle Timeout) sau một khoảng thời gian nhân viên không thao tác | Nếu nhân viên rời quầy mà không bấm Đăng xuất, ca sau có thể thao tác nhầm trên tài khoản ca trước | **P2 (Medium)** |
| **AUTH-ISSUE-03** | Password Policy | Mật khẩu tài khoản chính thức hiện tại trong database demo khá đơn giản (`123`) | Phù hợp môi trường nội bộ demo nhưng cần bắt buộc đổi mật khẩu mạnh trước khi go-live | **P2 (Medium)** |
