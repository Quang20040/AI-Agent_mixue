# MA TRẬN THEO DÕI & XỬ LÝ LỖI TOÀN DIỆN (ISSUE RESOLUTION MATRIX)
## BeverageOps AI — Chi Nhánh Mixue 39 Tôn Quang Phiệt

Tài liệu này tổng hợp toàn bộ các phát hiện lỗi từ **Phase 1 (Black-box Testing)** và **Phase 2 (White-box Testing & Code Audit)**, đối chiếu với các hành động sửa lỗi, refactoring và kiểm thử tự động đã hoàn thành trong **Phase 3**.

---

### BẢNG MA TRẬN CHI TIẾT (RESOLUTION MATRIX)

| Mã Lỗi (Issue ID) | Mức độ | Phân loại | Mô tả lỗi | Nguyên nhân gốc rễ (Root Cause) | Giải pháp thực hiện (Fix Implemented) | File ảnh hưởng | Trạng thái | Bài test kiểm chứng |
| :--- | :---: | :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| **BUG-SHIFT-01** | **P0** | Data Integrity | Sửa báo cáo ca làm mất dữ liệu đối soát POS (`pos_collected_vnd`, `variance_pos_vnd`) | `save_or_update_shift_report` gán đè dictionary mới lên bản ghi cũ thay vì merge thuộc tính | Sử dụng `merged_item.update(report_dict)` để bảo lưu vĩnh viễn các trường đối soát POS | `src/engine/shift_service.py` | **RESOLVED** | `tests/test_shift_closing.py`<br>`tests/test_regression_phase3.py` |
| **BUG-SHIFT-02** | **P0** | Testing | Test `test_shift_closing.py` thất bại do thiếu thông tin `signed_by` và trường POS | Bản ghi `SHIFT_20261014_CA_TOI` bị sửa mất `signed_by: "An"` trong quá trình thao tác trước đó | Khôi phục đầy đủ dữ liệu gốc trong JSON và sửa đường dẫn import `sys.path` | `data/shift_reports.json`<br>`tests/test_shift_closing.py` | **RESOLVED** | `tests/test_shift_closing.py` |
| **SEC-AUTH-01** | **P0** | Security | Tồn tại Backdoor so sánh mật khẩu dạng văn bản thuần (Plaintext Fallback) | Hàm `check_password` có nhánh fallback `clean_plain == hashed_or_plain` | Xóa bỏ hoàn toàn nhánh kiểm tra plaintext; bắt buộc xác thực qua hàm băm có muối | `src/auth.py` | **RESOLVED** | `tests/test_employee_rbac.py`<br>`tests/test_regression_phase3.py` |
| **SEC-AUTH-02** | **P0** | Security | Lỗ hổng bypass xác thực tài khoản Quản trị viên bằng mật khẩu `"123"` | Đoạn code cứng trong `verify_user` cho phép bypass nếu là admin role | Loại bỏ toàn bộ logic kiểm tra cứng; bắt buộc kiểm tra hash người dùng từ DB | `src/auth.py` | **RESOLVED** | `tests/test_employee_rbac.py`<br>`tests/test_regression_phase3.py` |
| **SEC-AUTH-03** | **P1** | Security | Sử dụng thuật toán băm SHA-256 không muối (Unsalted SHA-256), dễ bị Rainbow Table | Hàm `hash_password` cũ chỉ gọi `hashlib.sha256(password.encode())` | Nâng cấp lên PBKDF2-HMAC-SHA256 (100,000 rounds, 16-byte random salt, `secrets.compare_digest`) | `src/auth.py` | **RESOLVED** | `tests/test_regression_phase3.py` |
| **SEC-AUTH-04** | **P2** | Security | Phiên làm việc trên máy tính quầy bar không tự hết hạn khi nhân viên rời vị trí | Thiếu cơ chế kiểm tra nhàn rỗi (Session Idle Timeout) trong Streamlit | Thiết lập kiểm tra thời gian nhàn rỗi 15 phút (`SESSION_TIMEOUT_MINUTES = 15`), tự động hủy session | `src/dashboard/app.py`<br>`src/dashboard/brand_ui.py` | **RESOLVED** | `tests/test_dashboard.py` |
| **BUG-BOM-01** | **P1** | Business Logic | Công thức đối soát tồn kho bỏ quên số dư tồn đầu kỳ (`initial_stock`) | Hàm `calculate_inventory_reconciliation` tính `expected_stock = purchases - theoretical_usage` | Lấy số liệu kiểm kê sớm nhất làm `initial_stock`, tính: `expected = initial + purchases - usage` | `src/engine/bom_engine.py` | **RESOLVED** | `tests/test_bom.py`<br>`tests/test_regression_phase3.py` |
| **BUG-BOM-02** | **P1** | Business Logic | Tỷ lệ phần trăm sai lệch kho (`variance_pct`) bị phóng đại 500,000% do chia cho 0 | Mẫu số tính % lấy `total_purchased`, khi kỳ không phát sinh nhập kho mẫu số = 0 | Chuẩn hóa mẫu số: `initial_stock + total_purchased`, fallback qua `theoretical_usage` | `src/engine/bom_engine.py` | **RESOLVED** | `tests/test_bom.py`<br>`tests/test_regression_phase3.py` |
| **PERF-FC-01** | **P1** | Performance | Backtest mô hình dự báo chạy mất 14.2 giây, gây đơ giao diện Streamlit | Quét toàn bộ DataFrame 90 ngày 1,872 lần bên trong vòng lặp backtest | Tiền chỉ mục hóa dữ liệu theo SKU (`_sku_series`), bổ sung bộ nhớ đệm `_backtest_cache` | `src/engine/forecasting.py` | **RESOLVED** | `tests/test_forecasting.py`<br>`tests/test_regression_phase3.py` |
| **BUG-STOCK-01** | **P2** | Data Integrity | Người dùng có thể nhập số âm vào bảng ma trận tồn kho trên giao diện | `st.data_editor` không cấu hình giới hạn giá trị tối thiểu cho các cột số | Bổ sung `st.column_config.NumberColumn(min_value=0.0, step=0.5)` cho các cột xuất nhập | `src/dashboard/app.py` | **RESOLVED** | `tests/test_daily_stock_crud.py` |
| **BUG-STOCK-02** | **P2** | Business Logic | Nhấn chuột liên tiếp tạo ra nhiều lệnh kho trùng lặp trong thời gian ngắn | Thiếu cơ chế kiểm tra tính lũy biến / chống bấm đúp (Idempotency Key) | Bổ sung bộ lọc kiểm tra lệnh kho tương đồng trong vòng 3 giây, trả về trạng thái `DUPLICATE` | `src/engine/daily_stock_service.py` | **RESOLVED** | `tests/test_regression_phase3.py` |
| **BUG-STICKER-01**| **P2** | UI/UX | Tem ly cũ không bị xóa khi người dùng nhập sai mã tem mới | Khi hàm giải mã báo lỗi, session state `sticker_result` không bị xóa bỏ | Thêm `st.session_state.pop("sticker_result", None)` trong khối xử lý lỗi | `src/dashboard/app.py` | **RESOLVED** | `tests/test_dashboard.py` |
| **BUG-AUTH-01** | **P2** | UI/UX | Gửi form đăng nhập rỗng không có thông báo nhắc nhở rõ ràng | Hệ thống gửi chuỗi rỗng vào hàm xác thực người dùng | Bổ sung kiểm tra `username.strip()` và `password.strip()` trước khi xác thực, hiện cảnh báo | `src/dashboard/brand_ui.py` | **RESOLVED** | `tests/test_dashboard.py` |
| **CODE-LINT-01** | **P2** | Code Quality | 396 lỗi linter, bao gồm unused imports, f-string rỗng, cú pháp type hint cũ | Codebase tích lũy nợ kỹ thuật sau các vòng phát triển nhanh | Sử dụng Ruff tự động sửa 312 lỗi, sửa thủ công các biến thừa và gán `ClassVar` | Toàn bộ codebase `src/` & `tests/` | **RESOLVED** | `ruff check src/ tests/` |
| **DEVOPS-01** | **P1** | DevOps | Thiếu `Dockerfile`, `requirements.txt` ghim phiên bản và CI/CD Pipeline | Chưa chuẩn hóa môi trường đóng gói container cho production | Tạo `Dockerfile` đa tầng (non-root), `requirements.txt` chuẩn hóa, workflow GitHub Actions CI | `Dockerfile`<br>`requirements.txt`<br>`.github/workflows/ci.yml` | **RESOLVED** | CI workflow & Docker build check |

---

### THỐNG KÊ TỔNG KẾT THEO MỨC ĐỘ
- **Mức P0 (Blocker / Critical Security & Data Loss):** 4/4 vấn đề đã được khắc phục (100%).
- **Mức P1 (High / Core Business Logic & Performance):** 5/5 vấn đề đã được khắc phục (100%).
- **Mức P2 (Medium / UI, UX & Code Quality):** 6/6 vấn đề đã được khắc phục (100%).
- **Tổng cộng:** 15/15 đầu mục vấn đề đã được giải quyết triệt để và nghiệm thu thành công.
