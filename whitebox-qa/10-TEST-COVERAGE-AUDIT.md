# BÁO CÁO KIỂM TOÁN ĐỘ BAO PHỦ & CHẤT LƯỢNG KIỂM THỬ (TEST COVERAGE AUDIT)
## HỆ THỐNG: BEVERAGE-OPS AI — CHI NHÁNH MIXUE 39 TÔN QUANG PHIỆT
**Mã tài liệu:** `WB-AUDIT-10-TEST`  
**Phiên bản:** 2.0.0-PROD-AUDIT  
**Đối tượng:** Đánh giá cấu trúc bộ kiểm thử `tests/`, độ phủ nhánh (Branch Coverage), 2 ca kiểm thử thất bại và nguyên lý F.I.R.S.T

---

## 1. TỔNG QUAN BỘ KIỂM THỬ TỰ ĐỘNG (AUTOMATED TEST SUITE INVENTORY)

Toàn bộ hệ thống sở hữu **9 tệp kiểm thử chuyên biệt** với tổng cộng **46 ca kiểm thử tự động (Unit & Integration Tests)** chạy trên nền tảng `pytest 8.4.2`:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       AUTOMATED TEST SUITE SUMMARY                          │
├──────────────────────────────┬────────┬────────┬────────┬───────────────────┤
│ Tệp Kiểm Thử                 │ Tests  │ Passed │ Failed │ Thời Gian / Focus │
├──────────────────────────────┼────────┼────────┼────────┼───────────────────┤
│ 1. tests/test_agent.py       │ 14     │ 14     │ 0      │ ~95s (AI Tools,   │
│                              │        │        │        │ RBAC, Guardrails) │
├──────────────────────────────┼────────┼────────┼────────┼───────────────────┤
│ 2. tests/test_bom.py         │ 4      │ 4      │ 0      │ ~0.8s (BOM, Waste)│
├──────────────────────────────┼────────┼────────┼────────┼───────────────────┤
│ 3. tests/test_daily_stock_   │ 3      │ 3      │ 0      │ ~1.2s (Stock CRUD,│
│    crud.py                   │        │        │        │ Matrix Calc)      │
├──────────────────────────────┼────────┼────────┼────────┼───────────────────┤
│ 4. tests/test_dashboard.py   │ 4      │ 4      │ 0      │ ~1.5s (Auth Screen│
│                              │        │        │        │ & Tab Access)     │
├──────────────────────────────┼────────┼────────┼────────┼───────────────────┤
│ 5. tests/test_employee_      │ 7      │ 7      │ 0      │ ~2.1s (Employee   │
│    rbac.py                   │        │        │        │ Management & Auth)│
├──────────────────────────────┼────────┼────────┼────────┼───────────────────┤
│ 6. tests/test_forecasting.py │ 2      │ 2      │ 0      │ ~28s (Forecast 39 │
│                              │        │        │        │ SKUs & Backtest)  │
├──────────────────────────────┼────────┼────────┼────────┼───────────────────┤
│ 7. tests/test_optimizer.py   │ 3      │ 3      │ 0      │ ~15s (Batch & Pack│
│                              │        │        │        │ Rounding, Validator)│
├──────────────────────────────┼────────┼────────┼────────┼───────────────────┤
│ 8. tests/test_retro_15days_  │ 5      │ 5      │ 0      │ ~42s (Red Teaming,│
│    evaluation.py             │        │        │        │ Prompt Injection) │
├──────────────────────────────┼────────┼────────┼────────┼───────────────────┤
│ 9. tests/test_shift_closing  │ 4      │ 2      │ **2**  │ ~18s (OCR, POS    │
│    .py                       │        │        │        │ Audit, Seed Data) │
├──────────────────────────────┼────────┼────────┼────────┼───────────────────┤
│ **TỔNG CỘNG**                │ **46** │ **44** │ **2**  │ **203.59s (~3m23s)│
└──────────────────────────────┴────────┴────────┴────────┴───────────────────┘
```

---

## 2. PHÂN TÍCH NGUYÊN NHÂN GỐC RỄ 2 CA KIỂM THỬ THẤT BẠI (TEST FAILURES)

### 2.1. Ca Thất Bại 1: `test_shift_reports_seed_and_closing_summary`
- **Vị trí lỗi:** [tests/test_shift_closing.py:67](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/tests/test_shift_closing.py#L67)
- **Thông báo lỗi từ Pytest:**
  ```text
  AssertionError: assert 'Anh' == 'An'
  - An
  + Anh
  ?   +
  ```
- **Phân tích cơ chế phát sinh (Root Cause):**
  - Trong logic ban đầu của hàm `_get_seed_shift_reports()` tại `shift_service.py`, ca tối do nhân viên **"An"** ký chốt sổ (`signed_by: "An"`).
  - Tuy nhiên, trong quá trình chạy thử nghiệm hoặc thao tác từ giao diện Streamlit vào ngày 15/10/2026 lúc 05:02:41, người dùng đăng nhập tài khoản nhân viên đã sửa tên người chốt ca thành **"Anh"** và bấm Lưu.
  - Hàm `save_or_update_shift_report()` đã ghi đè chuỗi `"Anh"` vào tệp [data/shift_reports.json:61](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/data/shift_reports.json#L61).
  - Khi bài test chạy, hàm `get_all_shift_reports("2026-10-14")` đọc trực tiếp từ tệp bị ô nhiễm này thay vì đọc từ seed chuẩn, dẫn đến assertion bị sai lệch!

### 2.2. Ca Thất Bại 2: `test_agent_targeted_shift_revenue_qa`
- **Vị trí lỗi:** [tests/test_shift_closing.py:124](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/tests/test_shift_closing.py#L124)
- **Thông báo lỗi từ Pytest:**
  ```text
  AssertionError: assert 'Khớp tuyệt đối' in r_close["text"]
  ... Đối soát máy POS: Doanh thu POS 10,119,000 đ (Thực thu POS: 10,119,000 đ ➔ Lệch -242,000 đ so với máy POS)
  ```
- **Phân tích cơ chế phát sinh (Root Cause):**
  - Bài test kỳ vọng Tuyết Vương AI trả về: *"Đối soát máy POS khớp tuyệt đối (lệch -137 đ)"*.
  - Tại sao lại lệch -137 đ? Bởi vì ngày 14/10/2026, doanh thu danh nghĩa máy POS là 10,119,000 đ, nhưng khách áp dụng voucher giảm giá (-217,000 đ) và có điều chỉnh lẻ, nên thực thu máy POS là **9,877,137 đ**. Sổ thu về của quán là **9,877,000 đ** $\rightarrow$ Độ lệch thực thu chỉ là **-137 đồng** (tỷ lệ khớp 99.999%).
  - Tuy nhiên, khi form giao diện Streamlit lưu lại ca vào `data/shift_reports.json`, **hàm lưu đã bỏ quên không lưu trường `pos_collected_vnd` và `variance_pos_vnd`**.
  - Dẫn đến khi AI Agent truy vấn lại, hàm tính chênh lệch lấy mặc định $9,877,000 - 10,119,000 = \mathbf{-242,000\ đ}$. Vì chênh lệch tới 242k, AI Agent không in chuỗi "Khớp tuyệt đối", khiến bài test bị gãy!

---

## 3. ĐÁNH GIÁ CHẤT LƯỢNG KIỂM THỬ THEO NGUYÊN LÝ F.I.R.S.T

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       F.I.R.S.T TESTING AUDIT MATRIX                        │
├────────────────────┬──────────┬─────────────────────────────────────────────┤
│ Nguyên Lý F.I.R.S.T│ Đánh Giá │ Đánh Giá Chi Tiết                           │
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ Fast (Nhanh)       │ VIOLATED │ Tổng thời gian chạy > 3 phút; các test gọi  │
│                    │ (CHẬM)   │ forecast mất 14-28 giây mỗi test            │
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ Independent (Độc   │ VIOLATED │ Các test dùng chung file mutable            │
│ lập)               │ (DÍNH)   │ data/shift_reports.json gây test pollution  │
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ Repeatable (Lặp lại│ CÓ RỦI RO│ Chạy lại có thể fail nếu dữ liệu file JSON  │
│ nhất quán)         │          │ bị thay đổi ngoài môi trường test           │
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ Self-validating    │ ĐẠT      │ Khẳng định rõ ràng bằng assert True/False   │
│ (Tự kiểm chứng)    │          │                                             │
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ Timely (Kịp thời)  │ TỐT      │ Đã viết test bám sát 15 Ngày AI Thực Chiến  │
└────────────────────┴──────────┴─────────────────────────────────────────────┘
```

### 3.1. Vi Phạm Tính Độc Lập (Test Independence Violation)
Bộ test hiện tại vi phạm nguyên tắc quan trọng nhất của Unit Testing: **Các bài test không được phụ thuộc vào trạng thái dữ liệu chia sẻ có thể biến đổi (Shared Mutable State)**.
Khi kiểm thử module `shift_service.py`, bài test cần sử dụng Pytest Fixture với thư mục tạm thời `tmp_path` hoặc mock dữ liệu bằng `unittest.mock.patch`, tuyệt đối không đọc/ghi trực tiếp vào thư mục `data/` của môi trường chạy thật.

---

## 4. ƯỚC TÍNH ĐỘ BAO PHỦ MÃ NGUỒN (COVERAGE ESTIMATION)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CODEBASE TEST COVERAGE BREAKDOWN                         │
├──────────────────────────────┬────────────┬─────────────────────────────────┤
│ Module / Thư Mục             │ Độ Bao Phủ │ Đánh Giá & Vùng Chưa Test       │
├──────────────────────────────┼────────────┼─────────────────────────────────┤
│ src/engine/validator.py      │ **~95%**   │ Rất cao (Full rule matrix)      │
│ src/engine/optimizer.py      │ **~90%**   │ Cao (Batch & Carton specs test) │
│ src/engine/forecasting.py    │ **~85%**   │ Cao (Model & Backtest verified) │
│ src/auth.py                  │ **~82%**   │ Khá (RBAC & Pass change tested) │
│ src/engine/bom_engine.py     │ **~75%**   │ Trung bình (Recon chưa test âm) │
│ src/engine/daily_stock_      │ **~70%**   │ Trung bình (Chưa test trùng lặp)│
│ service.py                   │            │                                 │
│ src/agent/mixue_agent.py     │ **~65%**   │ Trung bình (Mới test 5 prompt   │
│                              │            │ trong số hàng chục regex)       │
│ src/engine/shift_service.py  │ **~60%**   │ Yếu (2 tests failed do JSON)    │
│ src/dashboard/app.py         │ **~20%**   │ Rất yếu (Chỉ test sơ bộ login;  │
│                              │            │ UI tables chưa test tự động)    │
│ src/dashboard/brand_ui.py    │ **~15%**   │ Rất yếu (GSAP, SVG không test)  │
├──────────────────────────────┼────────────┼─────────────────────────────────┤
│ **TOÀN BỘ CODEBASE**         │ **~62%**   │ **CHƯA ĐẠT CHUẨN PROD (>80%)**  │
└──────────────────────────────┴────────────┴─────────────────────────────────┘
```

---

## 5. LỘ TRÌNH NÂNG CAO ĐỘ BAO PHỦ VÀ SỬA CHỮA TEST (TEST HARDENING ROADMAP)

1. **Khắc Phục 2 Bài Test Thất Bại Ngay Lập Tức:**
   - Trong `tests/test_shift_closing.py`, cập nhật fixture tạo file JSON mẫu độc lập trong thư mục tạm `tmp_path`, đảm bảo trường `signed_by: "An"` và bảo toàn trường `pos_collected_vnd`.
2. **Mocking Tầng Dự Báo Để Tăng Tốc Độ Test (Từ 3 phút xuống 15 giây):**
   - Trong `test_agent.py` và `test_retro_15days_evaluation.py`, khi kiểm thử các tác vụ của Agent mà không liên quan đến giải thuật dự báo, thực hiện mock hàm `forecast_demand()` trả về DataFrame giả lập cố định. Điều này sẽ loại bỏ hoàn toàn 1,872 lượt lặp tính toán, giảm thời gian chạy test suite từ **203 giây xuống dưới 15 giây**.
3. **Bổ Sung Bộ Test Trường Hợp Dị Thường (Negative & Edge Case Testing):**
   - Bổ sung test kiểm tra: Đăng nhập sai 5 lần liên tiếp; nhập số lượng hàng kiểm kê bằng 0; gửi 2 lệnh kho trùng lặp trong cùng 1 giây (Idempotency Test).
