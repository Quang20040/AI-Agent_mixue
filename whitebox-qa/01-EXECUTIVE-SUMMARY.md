# BÁO CÁO KIỂM TOÁN NGUỒN VÀ KIỂM THỬ HỘP TRẮNG (WHITE-BOX AUDIT)
## HỆ THỐNG: BEVERAGE-OPS AI — CHI NHÁNH MIXUE 39 TÔN QUANG PHIỆT
**Mã tài liệu:** `WB-AUDIT-01-EXEC`  
**Phiên bản kiểm toán:** 2.0.0-PROD-AUDIT  
**Đối tượng kiểm toán:** Toàn bộ repository `AI-Agent_mixue`  
**Ngày thực hiện:** 15/10/2026  
**Đơn vị thực hiện:** Independent Technical Audit Team (Principal Software Architect, Staff Backend Engineer, Senior Frontend Engineer, QA Automation Lead, Application Security Engineer)  
**Tình trạng môi trường:** Local Staging / Production Simulation (Python 3.12.6, Streamlit 1.40+, SQLite Engine)

---

## 1. TỔNG QUAN DỰ ÁN VÀ PHẠM VI KIỂM TOÁN

Dự án **BeverageOps AI** là giải pháp phần mềm quản trị, tối ưu hóa và trợ lý vận hành AI chuyên biệt cho chuỗi đồ uống F&B, triển khai thử nghiệm tại chi nhánh **Mixue 39 Tôn Quang Phiệt** (Mã cửa hàng: 2132). 

Hệ thống kết hợp giữa tính toán tất định (Deterministic Engines: BOM explosion, dự báo nhu cầu bán hàng, tối ưu mẻ sơ chế topping, lập đơn đặt hàng PO đóng gói thùng/kiện, đối soát sổ kho 31 ngày, đối soát chốt ca máy POS) và AI Orchestration (Tuyết Vương AI Agent hỗ trợ đàm thoại, giải mã tem dán ly, kiểm tra chính sách bảo mật và cổng phê duyệt Human-in-the-Loop).

### Tech Stack Thực Tế Phát Hiện Qua Audit:
- **Ngôn ngữ & Runtime:** Python 3.12.6 64-bit on Windows x64.
- **Frontend / Presentation Layer:** Streamlit (v1.40+), HTML5/CSS3 tùy biến nhận diện thương hiệu Tuyết Vương Mixue (`src/dashboard/brand.css`), tích hợp animation library GSAP & ScrollTrigger thông qua Streamlit Components v2 API (`src/dashboard/brand_ui.py`).
- **Backend & Data Access:** SQLAlchemy 2.0 ORM (`src/models.py`), SQLite local engine (`data/beverageops.db`) với fallback config sang PostgreSQL (`src/database.py`).
- **Core Processing Engines:** 
  - `src/engine/bom_engine.py`: BOM Explosion, đối soát hao hụt và tồn kho lý thuyết.
  - `src/engine/forecasting.py`: Dự báo chuỗi thời gian (Seasonal Naive, Moving Average, Day-of-Week) với kiểm thử lịch sử cuốn chiếu 15 ngày (Rolling-Origin Backtest).
  - `src/engine/optimizer.py`: Tối ưu định lượng mẻ nấu topping (1,000g / 5,000ml) và làm tròn nguyên thùng/kiện PO Mixue.
  - `src/engine/validator.py`: Thẩm định chính sách độc lập (`IndependentPlanValidator`).
  - `src/engine/daily_stock_service.py`: Quản trị ma trận thẻ kho 31 ngày (tháng 10/2026), Maker-Checker lệnh xuất/nhập/kiểm kê.
  - `src/engine/shift_service.py`: Quản trị sổ giao ca 3 ca/ngày và đối soát doanh thu thực thu với máy POS.
- **AI Agent & LLM Layer:** `src/agent/mixue_agent.py` (1,652 dòng) tổ chức 8 operational tools, System Prompt 5 khối, bộ lọc Red Teaming, Guardrail bảo mật tiền lương và bộ nhớ hội thoại đa lượt (Multi-turn Context Memory).
- **Hạ tầng & Container:** `docker-compose.yml` (chỉ khai báo container PostgreSQL 16; chưa có Dockerfile và service cho ứng dụng chính).

---

## 2. THỐNG KÊ MÃ NGUỒN & KẾT QUẢ PHÂN TÍCH TĨNH (STATIC ANALYSIS)

### 2.1. Thống kê Quy mô Mã nguồn (LOC & File Count)
- **Tổng số tệp mã nguồn ứng dụng (`src/`):** 11 tệp chính.
- **Tổng số dòng mã nguồn (LOC in `src/`):** 6,192 dòng code Python.
- **Tệp lớn nhất (God Class/File Smell):**
  - `src/agent/mixue_agent.py`: 1,652 dòng.
  - `src/dashboard/app.py`: 1,234 dòng.
  - `src/engine/daily_stock_service.py`: 982 dòng.
  - `src/dashboard/brand_ui.py`: 534 dòng.
- **Tổng số tệp kiểm thử (`tests/`):** 9 tệp kiểm thử chuyên biệt.
- **Tổng số ca kiểm thử thực thi:** 46 unit & integration tests.

### 2.2. Kết quả Phân tích Tĩnh (Static Analysis with Ruff v0.8+)
Phân tích tĩnh toàn diện trên thư mục `src/` và `tests/` ghi nhận tổng cộng **375 lỗi & cảnh báo mã nguồn**:
- **307 vi phạm S101 (`assert` used outside of tests):** Sử dụng câu lệnh `assert` trong luồng xử lý chính thay vì kiểm tra ngoại lệ `ValueError`/`RuntimeError`.
- **47 vi phạm F401 (Unused Imports):** Nhập các thư viện nhưng không sử dụng, gây lãng phí bộ nhớ và chậm thời gian nạp module.
- **46 vi phạm F541 (f-string missing placeholders):** Khai báo tiền tố `f"..."` nhưng không có biến nội suy, tiềm ẩn sai sót khi chỉnh sửa log.
- **22 vi phạm BLE001 (Blind Except):** Bắt ngoại lệ chung `except Exception:` mà không phân loại cụ thể lỗi DB, lỗi I/O hay lỗi validation.
- **21 vi phạm DTZ005 (Datetime without timezone):** Gọi `datetime.now()` không có thông tin múi giờ (`Asia/Ho_Chi_Minh`), tiềm ẩn lệch dữ liệu khi triển khai cloud server.
- **5 vi phạm S110 (Try-Except-Pass):** Nuốt ngoại lệ hoàn toàn mà không log (`pass`), gây khó khăn cho việc truy vết lỗi runtime.
- **2 vi phạm F841 (Unused variables):** Khởi tạo biến nhưng không sử dụng.

---

## 3. KẾT QUẢ KIỂM THỬ TỰ ĐỘNG (AUTOMATED TEST SUITE EXECUTION)

Thực thi bộ kiểm thử tự động toàn diện qua lệnh `pytest tests/ -v --tb=short`:
- **Tổng số bài kiểm thử:** 46 bài test.
- **Kết quả:** **44 PASSED (95.7%) | 2 FAILED (4.3%)**.
- **Thời gian chạy toàn bộ suite:** 203.59 giây (~3 phút 23 giây) — thời gian kiểm thử kéo dài do các hàm dự báo chạy backtest 1,872 lượt lặp không cache.

### Chi tiết 2 ca kiểm thử bị Thất Bại (FAILED):
1. **`tests/test_shift_closing.py::test_shift_reports_seed_and_closing_summary`**:
   - **Vấn đề:** `assert toi["signed_by"] == "An"` thất bại vì giá trị thực tế trong `data/shift_reports.json` là `"Anh"`.
   - **Nguyên nhân gốc rễ (Root Cause):** Tệp `data/shift_reports.json` là một tệp JSON dùng chung có tính biến đổi (mutable file), bị ghi đè dữ liệu khi người dùng thao tác chỉnh sửa ca trên giao diện Streamlit hoặc do script test trước đó gây ô nhiễm trạng thái (Data State Drift).
2. **`tests/test_shift_closing.py::test_agent_targeted_shift_revenue_qa`**:
   - **Vấn đề:** `assert "Khớp tuyệt đối" in r_close["text"]` thất bại. Agent trả về: `Lệch -242,000 đ so với máy POS`.
   - **Nguyên nhân gốc rễ (Root Cause):** Tệp `data/shift_reports.json` bị mất các trường đối soát POS (`pos_collected_vnd`, `variance_pos_vnd`) khi hàm `save_or_update_shift_report()` thực hiện lưu bản ghi từ UI, khiến doanh thu đối soát POS bị tính mặc định bằng tổng doanh thu danh nghĩa (10,119,000 đ) thay vì thực thu POS đã trừ khuyến mãi voucher (9,877,137 đ).

---

## 4. BẢNG TỔNG HỢP LỖI & RỦI RO KỸ THUẬT (DEFECT SEVERITY MATRIX)

| Mã Lỗi | Phân Loại | Mức Độ | Module / Tệp Nguồn | Tóm Tắt Lỗi & Rủi Ro | Trạng Thái |
|---|---|---|---|---|---|
| **WB-SEC-01** | Security / Auth | **CRITICAL (P0)** | `src/auth.py:55-66` | Mật khẩu băm SHA-256 không salt; tồn tại cửa hậu plaintext fallback (`clean_plain == hashed_or_plain`). | Phát hiện mới |
| **WB-DATA-01** | Data Integrity | **CRITICAL (P0)** | `src/engine/shift_service.py:20-74` | Dữ liệu tài chính chốt ca lưu trữ dạng JSON file trần, không lock, nguy cơ race condition mất dữ liệu khi ghi đồng thời. | Phát hiện mới |
| **WB-PERF-01** | Performance | **HIGH (P1)** | `src/engine/forecasting.py:222-255` | `forecast_demand(model='auto')` tính lặp lại 1,872 chu kỳ backtest tuần tự không cache, gây lag 14s mỗi lần load trang hoặc hỏi AI. | Khớp BUG-PERF-01 |
| **WB-SEC-02** | Security / RBAC | **HIGH (P1)** | `src/dashboard/app.py:65-72` | Phân quyền Client-Side hoàn toàn trong Streamlit session, thiếu REST API Gateway và middleware token (JWT/Session Cookie). | Phát hiện mới |
| **WB-BUS-01** | Business Logic | **HIGH (P1)** | `src/engine/bom_engine.py:181-183` | Công thức tính tồn kho kỳ vọng (`expected_stock`) bỏ qua tồn kho đầu kỳ (`initial_stock`), làm sai lệch tỷ lệ chênh lệch kiểm kê (`variance_pct`). | Phát hiện mới |
| **WB-DATA-02** | Data / Idempotency | **MEDIUM (P2)** | `src/engine/daily_stock_service.py:240-272` | Thiếu khóa trùng lặp (Idempotency Key); double click gây nhân bản nhiều lệnh giao dịch kho trùng giờ. | Khớp BUG-STOCK-03 |
| **WB-UI-01** | Frontend / State | **MEDIUM (P2)** | `src/dashboard/app.py:984-1045` | `st.session_state` lưu tem không được giải phóng khi giải mã lỗi; Streamlit re-run làm mất dữ liệu chỉnh sửa dở dang trên `st.data_editor`. | Khớp BUG-STICKER-01 & BUG-STOCK-02 |
| **WB-AI-01** | AI Pipeline | **MEDIUM (P2)** | `src/engine/shift_service.py:320-460` | Hàm AI OCR trích xuất ảnh sổ chốt ca thực chất là regex/mock hardcode theo tên file, chưa tích hợp mô hình thị giác thật. | Phát hiện mới |
| **WB-TEST-01** | QA Automation | **MEDIUM (P2)** | `tests/test_shift_closing.py:44-125` | 2 unit tests FAILED do lệ thuộc vào file mutable `data/shift_reports.json` thay vì mock fixture cách ly. | Phát hiện mới |
| **WB-DEVOPS-01**| DevOps / CI-CD | **MEDIUM (P2)** | Root repository | Không có `requirements.txt`, không có lockfile, không có Dockerfile cho Streamlit app, không có CI pipeline. | Phát hiện mới |

---

## 5. TOP 5 RỦI RO KỸ THUẬT LỚN NHẤT ĐỐI VỚI VẬN HÀNH

```
   ┌────────────────────────────────────────────────────────────────────────┐
   │                       TOP 5 TECHNICAL RISKS                            │
   ├──────┬────────────────────────┬──────────┬─────────────────────────────┤
   │ TOP  │ Lĩnh Vực Rủi Ro         │ Mức Độ   │ Hậu Quả Vận Hành            │
   ├──────┼────────────────────────┼──────────┼─────────────────────────────┤
   │  1   │ Mật khẩu & Xác thực    │ CRITICAL │ Nguy cơ dò mật khẩu qua     │
   │      │ (SHA-256 không salt)   │          │ rainbow table, bypass auth. │
   ├──────┼────────────────────────┼──────────┼─────────────────────────────┤
   │  2   │ Lưu trữ sổ chốt ca JSON│ CRITICAL │ Mất mát doanh thu chốt ca   │
   │      │ (File không transaction│          │ khi 2 ca lưu đồng thời.     │
   ├──────┼────────────────────────┼──────────┼─────────────────────────────┤
   │  3   │ Độ trễ dự báo 14s      │ HIGH     │ Giao diện đóng băng,        │
   │      │ (Backtest không cache) │          │ nghẽn thread máy chủ.       │
   ├──────┼────────────────────────┼──────────┼─────────────────────────────┤
   │  4   │ Logic tồn kho thiếu Tồn│ HIGH     │ Báo cáo đối soát kiểm kê bị │
   │      │ đầu kỳ (bom_engine.py) │          │ âm hoặc sai lệch nghiêm trọng│
   ├──────┼────────────────────────┼──────────┼─────────────────────────────┤
   │  5   │ Thiếu Dependency Lock  │ HIGH     │ Không thể dựng lại hệ thống │
   │      │ & Dockerfile hoàn chỉnh│          │ đồng nhất trên Staging/Cloud│
   └──────┴────────────────────────┴──────────┴─────────────────────────────┘
```

1. **Rủi ro Mật khẩu & Xác thực (WB-SEC-01):**
   Hàm `check_password()` tại [src/auth.py](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/auth.py#L60-L66) chấp nhận so sánh bằng trực tiếp `clean_plain == hashed_or_plain`. Nếu trong database có bản ghi mật khẩu là chuỗi thường hoặc kẻ tấn công chèn được hash giả định, hệ thống sẽ cho phép đăng nhập trái phép. Ngoài ra, việc dùng SHA-256 trần không có Salt và Cost Factor (như bcrypt hay Argon2id) khiến mật khẩu 6 số của nhân viên có thể bị bẻ khóa bằng rainbow table trong vòng vài mili-giây.

2. **Rủi ro Toàn vẹn Dữ liệu Chốt ca (WB-DATA-01):**
   Dịch vụ doanh thu chốt ca tại [src/engine/shift_service.py](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/shift_service.py#L20-L74) lưu toàn bộ lịch sử chốt ca vào tệp cục bộ `data/shift_reports.json` bằng cách đọc toàn bộ và ghi đè toàn bộ (`json.dump(data, f)`). Cơ chế này không hỗ trợ khóa tệp (file locking), không có atomic transaction. Khi hai nhân viên giao ca cùng lúc hoặc quản lý đang duyệt báo cáo trong khi nhân viên nộp ảnh, dữ liệu sẽ bị ghi đè và làm biến mất các trường đối soát POS.

3. **Rủi ro Hiệu năng Tính toán Nhu cầu (WB-PERF-01):**
   Tại [src/engine/forecasting.py](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/forecasting.py#L222-L255), mỗi khi gọi hàm `forecast_demand(model='auto')`, hệ thống tự động chạy lại toàn bộ thuật toán `run_backtest(start_eval_day=15)`. Vòng lặp này duyệt qua 16 ngày đánh giá, 39 mã sản phẩm và 3 mô hình dự báo (1,872 lượt lặp tính toán tuần tự trên Python single thread). Điều này khiến thời gian phản hồi kéo dài từ 12 đến 14 giây, làm nghẽn toàn bộ luồng giao diện người dùng Streamlit.

4. **Rủi ro Sai lệch Đối soát Tồn kho (WB-BUS-01):**
   Tại [src/engine/bom_engine.py](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/bom_engine.py#L181-L185), công thức tính tồn kho kỳ vọng là:
   $$\text{expected\_stock} = \text{total\_purchased} - \text{theoretical\_usage}$$
   Công thức này thiếu hoàn toàn thành phần tồn kho đầu kỳ ($\text{opening\_stock}$). Đối với các nguyên liệu đã tồn tại trong kho từ tháng trước mà không có đợt nhập mới trong kỳ đối soát, giá trị này sẽ rơi vào số âm hoặc làm sai lệch tỷ lệ chênh lệch kiểm kê thực tế.

5. **Rủi ro Triển khai & Tái lập Môi trường (WB-DEVOPS-01):**
   Repository hoàn toàn thiếu tệp kê khai gói thư viện (`requirements.txt`, `poetry.lock`, hoặc `pyproject.toml`). Docker compose hiện có chỉ chạy cơ sở dữ liệu PostgreSQL nhưng không có Dockerfile để đóng gói mã nguồn BeverageOps AI. Một kỹ sư mới hoặc máy chủ Production không thể dựng lại ứng dụng với phiên bản thư viện chính xác, dẫn đến nguy cơ lỗi không tương thích phiên bản (dependency break).

---

## 6. ĐÁNH GIÁ CHẤT LƯỢNG & ĐIỂM SỐ KỸ THUẬT (SCORECARD PREVIEW)

Dựa trên tiêu chuẩn đánh giá hệ thống phần mềm cấp doanh nghiệp ISO/IEC 25010 và phương pháp luận 15 Ngày AI Thực Chiến:

| Trục Đánh Giá | Thang Điểm | Điểm Đạt Được | Tỷ Lệ | Nhận Xét Của Audit Team |
|---|---|---|---|---|
| **1. Kiến trúc Hệ thống (Architecture)** | 15 điểm | **10.5 / 15** | 70.0% | Tách biệt engine tốt, nhưng dính coupling giữa UI và DB, thiếu API Gateway. |
| **2. Chất lượng Mã nguồn (Clean Code)** | 15 điểm | **10.0 / 15** | 66.7% | Tồn tại God Class (`mixue_agent.py` 1,652 dòng), 22 blind excepts, 307 asserts. |
| **3. Logic Nghiệp vụ & Độ chính xác** | 15 điểm | **12.5 / 15** | 83.3% | Logic quy cách đóng gói thùng/kiện và làm tròn mẻ rất chuẩn, trừ công thức tồn kho. |
| **4. An toàn & Bảo mật Ứng dụng** | 15 điểm | **8.5 / 15** | 56.7% | Red Teaming AI tốt nhưng Auth backend yếu (SHA-256 không salt, plaintext fallback). |
| **5. Hiệu năng & Tối ưu hóa** | 10 điểm | **5.5 / 10** | 55.0% | Thiếu caching layer nghiêm trọng; backtest 1,872 lượt lặp gây nghẽn 14 giây. |
| **6. Kiểm thử & Độ bao phủ (Testing)** | 15 điểm | **10.5 / 15** | 70.0% | 46 tests phong phú nhưng 2 tests bị fail do data drift; thiếu edge-case tests. |
| **7. Hạ tầng, DevOps & CI/CD** | 15 điểm | **5.0 / 15** | 33.3% | Thiếu hoàn toàn requirements.txt, Dockerfile ứng dụng và pipeline CI/CD. |
| **TỔNG CỘNG** | **100 điểm** | **62.5 / 100** | **Grade: C+** | **CHƯA ĐỦ ĐIỀU KIỆN SẴN SÀNG PRODUCTION (CONDITIONAL NO-GO)** |

---

## 7. KHUYẾN NGHỊ HÀNH ĐỘNG TỨC THÌ CHO TECH LEAD (IMMEDIATE ACTION PLAN)

1. **Khắc phục Bảo mật Ngay lập tức (Trong vòng 24h):**
   - Loại bỏ đoạn mã `clean_plain == hashed_or_plain` tại [src/auth.py](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/auth.py#L65).
   - Chuyển đổi thuật toán băm mật khẩu sang `bcrypt` (work factor 12) hoặc `argon2id` có bổ sung muối ngẫu nhiên (salt).
2. **Di chuyển Dữ liệu Chốt ca sang CSDL Chuẩn (Trong vòng 48h):**
   - Tạo model ORM `ShiftReport` và `ShiftExpense` trong [src/models.py](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/models.py) để thay thế việc ghi tệp `shift_reports.json`.
   - Chạy script di chuyển (migration) dữ liệu lịch sử và sửa 2 unit tests đang bị FAILED.
3. **Cải thiện Hiệu năng Dự báo (Trong vòng 48h):**
   - Thêm decorator `@st.cache_data(ttl=3600)` hoặc `@functools.lru_cache` cho hàm `run_backtest()` trong [src/engine/forecasting.py](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/forecasting.py#L136), đưa độ trễ từ 14 giây xuống dưới 0.1 giây đối với các lần truy vấn tiếp theo.
4. **Chuẩn hóa Quản lý Dependencies & Docker (Trong vòng 72h):**
   - Khởi tạo tệp `requirements.txt` có cố định chính xác phiên bản các gói (`pip freeze`).
   - Xây dựng `Dockerfile` đa tầng (multi-stage build) cho Streamlit app và tích hợp vào `docker-compose.yml`.

*(Chi tiết phân tích kỹ thuật từng hạng mục được trình bày trong 15 báo cáo chuyên đề tiếp theo).*
