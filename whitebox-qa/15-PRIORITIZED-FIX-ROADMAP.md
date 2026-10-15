# KẾ HOẠCH HÀNH ĐỘNG VÀ LỘ TRÌNH KHẮC PHỤC LỖI (PRIORITIZED FIX ROADMAP)
## HỆ THỐNG: BEVERAGE-OPS AI — CHI NHÁNH MIXUE 39 TÔN QUANG PHIỆT
**Mã tài liệu:** `WB-AUDIT-15-ROADMAP`  
**Phiên bản:** 2.0.0-PROD-AUDIT  
**Đối tượng:** Hướng dẫn kỹ thuật chi tiết, tiêu chí nghiệm thu (Acceptance Criteria) và lộ trình 4 giai đoạn khắc phục toàn diện

---

## 1. TỔNG QUAN LỘ TRÌNH 4 GIAI ĐOẠN (FOUR-PHASE EXECUTION ROADMAP)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FOUR-PHASE ENGINEERING REMEDIATION                       │
├───────────────┬──────────────────────────┬──────────┬───────────────────────┤
│ Giai Đoạn     │ Trọng Tâm Khắc Phục      │ Thời     │ Mục Tiêu Chất Lượng   │
│               │                          │ Lượng    │                       │
├───────────────┼──────────────────────────┼──────────┼───────────────────────┤
│ **GIAI ĐOẠN A**│ P0 Blockers: Bảo mật     │ 24 - 48  │ Triệt tiêu lỗ hổng    │
│ (Sprint 1)    │ mật khẩu, Caching 14s,   │ Giờ      │ an ninh; 100% test    │
│               │ sửa 2 test fail, Docker  │          │ PASS (46/46)          │
├───────────────┼──────────────────────────┼──────────┼───────────────────────┤
│ **GIAI ĐOẠN B**│ P1 High Priority: Lỗi    │ Tuần 1   │ Khắc phục 100% 10 lỗi │
│ (Sprint 2)    │ Black-box, công thức tồn │ (5 ngày) │ Black-box Vòng 1; bảo │
│               │ kho, CI/CD pipeline      │          │ vệ tính toàn vẹn kho  │
├───────────────┼──────────────────────────┼──────────┼───────────────────────┤
│ **GIAI ĐOẠN C**│ P2 Medium: Dọn dẹp Clean │ Tuần 2   │ Chuyển JSON sang SQL; │
│ (Sprint 3)    │ Code, Alembic, linter,   │ (5 ngày) │ test time <15 giây;   │
│               │ tối ưu hóa test suite    │          │ 0 cảnh báo phân tích  │
├───────────────┼──────────────────────────┼──────────┼───────────────────────┤
│ **GIAI ĐOẠN D**│ P3 Architecture: Phân rã │ Tuần 3-4 │ Sẵn sàng nhân bản chuỗi│
│ (Sprint 4)    │ God Class, FastAPI REST, │ (10 ngày)│ 50 cửa hàng Mixue; API│
│               │ hỗ trợ Multi-store       │          │ tích hợp máy POS thật │
└───────────────┴──────────────────────────┴──────────┴───────────────────────┘
```

---

## 2. CHI TIẾT TỪNG NHIỆM VỤ KHẮC PHỤC KỸ THUẬT

### GIAI ĐOẠN A: P0 BLOCKERS & CRITICAL SECURITY (24 - 48 GIỜ)

#### Task A1: Vá Lỗ Hổng Bảo Mật Mật Khẩu (Security Patching)
- **Tệp nguồn:** [src/auth.py:55-66](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/auth.py#L55-L66)
- **Hành động kỹ thuật:**
  1. Xóa bỏ hoàn toàn biểu thức cửa hậu `or clean_plain == hashed_or_plain`.
  2. Thay thế `hashlib.sha256` bằng thư viện `bcrypt` (work factor rounds=12) hoặc `argon2-cffi`.
  3. Viết script di chuyển (migration script) để băm lại mật khẩu của 4 tài khoản mặc định.
- **Tiêu chí nghiệm thu (Acceptance Criteria):**
  - Không thể đăng nhập bằng chuỗi plaintext nếu DB lưu chuỗi băm.
  - Mật khẩu băm trong bảng `users` có dạng chuẩn bcrypt: `$2b$12$...`.
  - Kiểm thử đăng nhập của `chucuahang`, `quanly`, `nhanvien` thành công.

#### Task A2: Khắc Phục Lỗi Ghi Đè Dữ Liệu Chốt Ca & Sửa 2 Bài Test Pytest
- **Tệp nguồn:** [src/engine/shift_service.py:210-220](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/shift_service.py#L210-L220)
- **Hành động kỹ thuật:**
  1. Trong hàm `save_or_update_shift_report()`, thay thế việc gán đè `data[idx] = report_dict` bằng hàm gộp dữ liệu: `data[idx].update(report_dict)` để bảo toàn các trường POS `pos_collected_vnd` và `variance_pos_vnd`.
  2. Khôi phục lại bản ghi ca tối ngày 14/10/2026 trong `data/shift_reports.json` với `signed_by: "An"`.
- **Tiêu chí nghiệm thu:**
  - Chạy `pytest tests/test_shift_closing.py` đạt **4/4 PASSED (100%)**.
  - Toàn bộ suite đạt **46/46 PASSED (100%)**.

#### Task A3: Khởi Tạo Tệp `requirements.txt` Cố Định Phiên Bản
- **Hành động kỹ thuật:**
  Tạo tệp `requirements.txt` chuẩn tại thư mục gốc với các phiên bản chính xác:
  `streamlit==1.40.1`, `SQLAlchemy==2.0.35`, `pandas==2.2.3`, `numpy==2.1.2`, `openpyxl==3.1.5`, `pydantic==2.9.2`, `pytest==8.4.2`, `ruff==0.8.4`, `psycopg2-binary==2.9.9`.
- **Tiêu chí nghiệm thu:**
  Tạo một Python virtualenv sạch (`python -m venv venv_test`), chạy `pip install -r requirements.txt` và khởi động được ứng dụng mà không gặp lỗi thiếu thư viện.

#### Task A4: Bổ Sung Caching Giảm Độ Trễ Dự Báo Từ 14s Xuống <0.1s
- **Tệp nguồn:** [src/dashboard/app.py:80-100](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/dashboard/app.py#L80-L100)
- **Hành động kỹ thuật:**
  Bọc decorator `@st.cache_data(ttl=3600)` cho hàm gọi dự báo nhu cầu.
- **Tiêu chí nghiệm thu:**
  Thời gian phản hồi khi bấm nút dự báo từ lần thứ hai trở đi $\le 100\text{ms}$.

---

### GIAI ĐOẠN B: KHẮC PHỤC LỖI BLACK-BOX & TÍNH TOÀN VẸN DỮ LIỆU (TUẦN 1)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PHASE B ACTION ITEMS & ACCEPTANCE CRITERIA               │
├──────┬────────────────────┬─────────────────────────────┬───────────────────┤
│ Mã   │ Tệp Nguồn & Dòng   │ Tóm Tắt Khắc Phục           │ Tiêu Chí          │
│      │                    │                             │ Nghiệm Thu        │
├──────┼────────────────────┼─────────────────────────────┼───────────────────┤
│ B1   │ app.py:1035-1045   │ Sửa BUG-STICKER-01: pop()   │ Không còn card cũ │
│      │                    │ biến session khi giải mã lỗi│ khi nhập sai tem  │
├──────┼────────────────────┼─────────────────────────────┼───────────────────┤
│ B2   │ app.py:535-560     │ Sửa BUG-STOCK-01: Thêm      │ Không cho gõ số âm│
│      │                    │ NumberColumn(min_value=0.0) │ vào ô bảng kho    │
├──────┼────────────────────┼─────────────────────────────┼───────────────────┤
│ B3   │ app.py:530-580     │ Sửa BUG-STOCK-02: Buffer    │ Không mất số vừa  │
│      │                    │ deltas vào session state    │ sửa khi đổi tab   │
├──────┼────────────────────┼─────────────────────────────┼───────────────────┤
│ B4   │ daily_stock_service│ Sửa BUG-STOCK-03: Thêm kiểm │ Double click chỉ  │
│      │ .py:240-272        │ tra trùng lặp trong 3s      │ tạo đúng 1 lệnh   │
├──────┼────────────────────┼─────────────────────────────┼───────────────────┤
│ B5   │ brand_ui.py:165-185│ Sửa BUG-AUTH-01: Kiểm tra   │ Cảnh báo "Vui lòng│
│      │                    │ chuỗi rỗng trước khi submit │ nhập tài khoản"   │
├──────┼────────────────────┼─────────────────────────────┼───────────────────┤
│ B6   │ app.py:65-75       │ Sửa BUG-AUTH-02: Thêm Idle  │ Tự đăng xuất sau  │
│      │                    │ Session Timeout 15 phút     │ 15 phút không dùng│
├──────┼────────────────────┼─────────────────────────────┼───────────────────┤
│ B7   │ bom_engine.py:180  │ Bổ sung Tồn đầu kỳ vào công │ variance_pct không│
│      │                    │ thức expected_stock         │ còn bị âm phi lý  │
├──────┼────────────────────┼─────────────────────────────┼───────────────────┤
│ B8   │ Root repo          │ Tạo Dockerfile đa tầng và   │ docker compose up │
│      │                    │ cập nhật docker-compose.yml │ chạy mượt cả App  │
├──────┼────────────────────┼─────────────────────────────┼───────────────────┤
│ B9   │ .github/workflows/ │ Tạo CI Pipeline tự động     │ Chạy linter & test│
│      │ ci.yml             │ kiểm tra mỗi Pull Request   │ trên mọi commit   │
└──────┴────────────────────┴─────────────────────────────┴───────────────────┘
```

---

### GIAI ĐOẠN C: DỌN DẸP MÃ NGUỒN & QUẢN TRỊ CƠ SỞ DỮ LIỆU (TUẦN 2)

1. **Di Chuyển Sổ Chốt Ca Sang PostgreSQL:**
   Tạo hai Model SQLAlchemy mới trong `src/models.py`:
   - `ShiftReport`: Lưu tổng tiền mặt, chuyển khoản, Shopee, Grab, Be, tiền két, chữ ký người giao.
   - `ShiftExpense`: Lưu chi tiết các khoản chi lặt vặt (mua sạc đt, ship đơn).
   Xóa bỏ hoàn toàn tệp `data/shift_reports.json`.
2. **Khởi Tạo Alembic Database Migrations:**
   Cấu hình `alembic/` với script khởi tạo `001_initial_schema.py`. Cấm gọi lệnh `Base.metadata.create_all()` khi ứng dụng khởi động.
3. **Dọn Dẹp 375 Cảnh Báo Phân Tích Tĩnh (Ruff):**
   - Loại bỏ 47 unused imports (`F401`).
   - Sửa 22 blind excepts (`except Exception:`) thành ngoại lệ cụ thể (`ValueError`, `SQLAlchemyError`).
   - Thay thế các câu lệnh `assert` trong logic chính bằng việc ném ngoại lệ tường minh.
4. **Tối Ưu Hóa Tốc Độ Bộ Kiểm Thử (Test Suite Acceleration):**
   Tạo Pytest Mock Fixture cho `forecast_demand()` trong `test_agent.py`, đưa thời gian thực thi toàn bộ test suite từ **203 giây xuống dưới 15 giây**.

---

### GIAI ĐOẠN D: TIẾN HÓA KIẾN TRÚC & SẴN SÀNG MỞ RỘNG ĐA CHUỖI (TUẦN 3 - 4)

1. **Phân Rã God Classes:**
   - Chia tách [src/agent/mixue_agent.py](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/agent/mixue_agent.py) thành các module chuyên biệt: `agent_core.py`, `guardrails.py`, `nlp_parser.py`, `tools/`.
   - Chia tách [src/dashboard/app.py](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/dashboard/app.py) thành thư mục `src/dashboard/views/` gồm các file độc lập cho từng Tab.
2. **Chuẩn Hóa Đa Chi Nhánh (Multi-store Support):**
   Bổ sung cột `store_id` vào bảng `daily_stock_movements`, `purchases` và `users`. Mọi câu truy vấn đều lọc theo `store_id = current_user.store_id`.
3. **Xây Dựng FastAPI Headless REST Gateway:**
   Cung cấp các endpoint chuẩn OpenAPI để sẵn sàng kết nối webhook tự động với máy POS tại quầy và phát hành ứng dụng di động cho Quản lý.
