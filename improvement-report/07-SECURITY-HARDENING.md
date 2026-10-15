# BÁO CÁO GIA CỐ BẢO MẬT & KIỂM SOÁT PHÂN QUYỀN (SECURITY HARDENING)
## BeverageOps AI — Quản Trị Vận Hành Chi Nhánh Mixue 39 Tôn Quang Phiệt

---

### 1. NÂNG CẤP CHUẨN MÃ HÓA MẬT KHẨU (PBKDF2-HMAC-SHA256)

#### 1.1. Thực trạng trước cải tiến
- File `src/auth.py` trước đây sử dụng hàm `hashlib.sha256(password.encode("utf-8")).hexdigest()` đơn thuần.
- **Rủi ro an ninh mạng:** SHA-256 trơn không có muối (Unsalted SHA-256) là thuật toán tính toán cực nhanh trên GPU/ASIC. Kẻ tấn công nếu có được file database có thể bẻ khóa hàng triệu mật khẩu mỗi giây bằng kỹ thuật bảng Rainbow Table hoặc từ điển Brute-force.

#### 1.2. Giải pháp thực hiện
Triển khai thuật toán băm chuẩn **PBKDF2-HMAC-SHA256** (tuân thủ khuyến nghị bảo mật OWASP Password Storage Cheat Sheet & NIST SP 800-63B):
- Sử dụng muối ngẫu nhiên an toàn mật mã (`secrets.token_hex(16)` = 128-bit entropy).
- Số vòng lặp băm tăng lên **100,000 rounds** (`hashlib.pbkdf2_hmac`).
- Định dạng chuỗi lưu trữ: `pbkdf2_sha256$100000$<salt_hex>$<hash_hex>`.
- So sánh mật khẩu bằng hàm `secrets.compare_digest` chống lại hình thức tấn công đo thời gian thực thi (Timing Attack).

```python
def hash_password(password: str) -> str:
    clean = str(password).strip()
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", clean.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"pbkdf2_sha256$100000${salt}${key.hex()}"
```

---

### 2. TRIỆT TIÊU TOÀN BỘ CỬA HẬU & BYPASS XÁC THỰC (BACKDOOR ELIMINATION)

#### 2.1. Lỗ hổng Plaintext Fallback (SEC-AUTH-01)
- **Mã lỗi trước đây:**
  ```python
  if clean_plain == hashed_or_plain:  # CỬA HẬU NGUY HIỂM!
      return True
  ```
  Nếu kẻ tấn công gửi chuỗi khớp với chuỗi hash trong database, hệ thống lập tức cho phép đăng nhập mà không qua giải mã!
- **Khắc phục:** Loại bỏ 100% nhánh so sánh văn bản thuần. Nếu chuỗi mật khẩu không đúng cấu trúc băm, hệ thống từ chối xác thực ngay lập tức.

#### 2.2. Lỗ hổng Admin Hardcoded Bypass (SEC-AUTH-02)
- **Mã lỗi trước đây:**
  ```python
  # Trong verify_user:
  if clean_pass in ("123", "123456", "admin123") and is_admin_role(user.role):
      return user_dict  # Bỏ qua kiểm tra mật khẩu thật của Admin!
  ```
  Bất kỳ ai biết username quản lý đều có thể đăng nhập bằng `"123"` dù quản lý đã đổi sang mật khẩu an toàn khác.
- **Khắc phục:** Loại bỏ hoàn toàn khối mã bypass. Mọi người dùng ở mọi phân quyền (kể cả Chủ quán và Quản lý) đều bắt buộc phải vượt qua bước đối chiếu hash trong database.

---

### 3. CƠ CHẾ NÂNG CẤP MÃ HÓA TỰ ĐỘNG (OPPORTUNISTIC HASH MIGRATION)

Để đảm bảo tính liên tục của hệ thống mà không bắt buộc tất cả nhân viên phải tạo lại tài khoản:
- Khi người dùng đăng nhập với tài khoản có hash cũ (SHA-256 legacy):
  1. Hệ thống vẫn xác thực thành công.
  2. Ngay sau đó, hệ thống tự động băm lại mật khẩu đó sang chuẩn mới **PBKDF2-HMAC-SHA256 (100,000 rounds)** và cập nhật ngầm vào database.
  3. Lần đăng nhập tiếp theo, tài khoản hoàn toàn vận hành trên chuẩn mã hóa cao cấp nhất.

---

### 4. BẢO VỆ PHIÊN LÀM VIỆC & DỮ LIỆU NHẠY CẢM TRONG AI AGENT

#### 4.1. Hết hạn phiên nhàn rỗi (Session Idle Timeout)
- Tích hợp kiểm tra thời gian nhàn rỗi 15 phút tại giao diện Streamlit. Khi hết hạn, toàn bộ dữ liệu phiên và quyền truy cập bị xóa bỏ, đưa về màn hình đăng nhập.

#### 4.2. Rào chắn bảo vệ lương & nhân sự trong AI Agent (Guardrails)
- AI Agent Tuyết Vương được thiết lập rào chắn dữ liệu nghiêm ngặt (`Salary Guardrail`):
  - Nhân viên hoặc người dùng thông thường khi hỏi Agent các câu hỏi về: Lương nhân viên, doanh thu ròng, chi phí mua hàng hoặc thông tin mật của chủ quán đều bị từ chối bằng phản hồi chuẩn mực:
    > *"Thông tin về bảng lương và chi phí nhân sự thuộc danh mục bảo mật nội bộ của Quản lý cửa hàng."*
  - Đã được kiểm chứng độc lập bởi test case `test_agent_salary_guardrail` và `test_agent_staff_cannot_query_sales_or_inventory_or_po`.
