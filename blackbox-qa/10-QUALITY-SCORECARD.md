# 10 – QUALITY SCORECARD & COVERAGE SUMMARY (BẢNG ĐIỂM CHẤT LƯỢNG & TỔNG KẾT ĐỘ BAO PHỦ)

> **Dự án:** BeverageOps AI — Quản trị Điều phối Vận hành Chi nhánh Mixue 39 Tôn Quang Phiệt  
> **Hội đồng đánh giá:** QA Lead, Test Architect, Lead Auditor  
> **Ngày phê chuẩn:** 15/10/2026  

---

## 1. BẢNG TỔNG HỢP TEST COVERAGE (COVERAGE METRICS)

| Hạng mục kiểm định | Số liệu thực tế ghi nhận | Ghi chú & Đánh giá |
|---|:---:|---|
| **Modules discovered (Số module phát hiện)** | **9 modules** | 1 Auth Portal + 8 Operational Business Modules |
| **Features discovered (Tổng số tính năng)** | **40 features** | Toàn bộ tính năng thực tế từ UI, Forms, Tables, Chatbot |
| **Features tested (Số tính năng đã kiểm thử)** | **40 features** | Đã tương tác và kiểm thử thực nghiệm qua Playwright |
| **Test cases executed (Số test case thực thi)** | **45 test cases** | Bao gồm Happy path, Negative, Boundary, RBAC, Recovery |
| **Passed (Số test đạt)** | **42 test cases** | 93.33% kịch bản kiểm thử đạt tiêu chuẩn chất lượng |
| **Failed (Số test lỗi)** | **3 test cases** | Các lỗi P2/P3 về State residual và UX validation |
| **Blocked (Số test bị chặn)** | **0 test cases** | Không có tính năng nào bị chặn |
| **Not Run (Số test chưa chạy)** | **0 test cases** | 100% test case đã lên kế hoạch đều được thực thi |
| **Test Coverage (Tỷ lệ bao phủ kiểm thử)** | **100.0%** | **Toàn diện 100% phạm vi tính năng hệ thống** |

---

## 2. FINAL QUALITY ASSESSMENT (CHẤM ĐIỂM CHẤT LƯỢNG THEO THANG 100)

| Hạng mục đánh giá | Điểm tối đa | Điểm đạt được | Lý do trừ điểm & Nhận xét chi tiết |
|---|:---:|:---:|---|
| **1. UI/UX** | 15 | **13.0 / 15** | Nhận diện Tuyết Vương rất đẹp, chuẩn thương hiệu Mixue. Trừ 2.0 điểm do: lỗi thông báo khi để trống form đăng nhập (BUG-AUTH-01) và nút đăng xuất bị giấu sâu trong sidebar thu gọn (BUG-NAV-01). |
| **2. Responsive** | 10 | **8.5 / 10** | Co giãn mượt mà từ 320px đến 1920px, hoàn toàn không bị tràn ngang body. Trừ 1.5 điểm do thanh điều hướng 8 tabs bị ngắt thành nhiều dòng trên mobile (BUG-RESP-01). |
| **3. Functional Correctness** | 25 | **23.5 / 25** | Toàn bộ 40 tính năng hoạt động chính xác theo thiết kế. Trừ 1.5 điểm do lỗi tem dán ly cũ không tự xóa khi nhập mã lỗi (BUG-STICKER-01). |
| **4. Business Logic** | 25 | **22.5 / 25** | Logic Maker-Checker, làm tròn mẻ sơ chế 5.000ml/1.000g và Lead Time 2 ngày hoạt động hoàn hảo. Trừ 2.5 điểm do: thiếu cảnh báo đỏ khi tồn kho bị âm (BUG-STOCK-01) và thiếu cảnh báo mất dữ liệu khi sửa ô ma trận kho mà chuyển tab (BUG-STOCK-02). |
| **5. Authentication & Session** | 10 | **9.0 / 10** | Phân quyền RBAC kiên cố, mã hóa SHA-256 an toàn, chặn nhân viên xem báo cáo tài chính. Trừ 1.0 điểm do thiếu cơ chế tự động khóa phiên khi không thao tác (BUG-AUTH-02). |
| **6. Error Handling & Reliability** | 10 | **8.5 / 10** | Hoàn toàn miễn nhiễm với SQL Injection, XSS và chuỗi cực dài. Không bị crash sập ứng dụng. Trừ 1.5 điểm do thời gian chạy dự báo D+1 kéo dài 14s thiếu thanh tiến trình % (BUG-PERF-01). |
| **7. Accessibility** | 5 | **4.5 / 5** | Có nút dừng chuyển động cho người nhạy cảm thị giác, tương phản màu đỏ/trắng đạt chuẩn WCAG AA. Trừ 0.5 điểm do một số text chú thích màu xám nhạt (`#64748b`) hơi nhỏ trên màn hình di động. |
| **TỔNG ĐIỂM CHẤT LƯỢNG** | **100** | **89.5 / 100** | **XẾP LOẠI: XUẤT SẮC (TIỆM CẬN SẴN SÀNG THƯƠNG MẠI)** |

---

## 3. KẾT LUẬN NGHIỆM THU CHẤT LƯỢNG (RELEASE VERDICT)

### Quyết định của QA Lead:
# **CONDITIONAL GO (ĐỦ ĐIỀU KIỆN PHÁT HÀNH CÓ ĐIỀU KIỆN)**

### Điều kiện tiên quyết để chuyển trạng thái thành FULL GO:
1. **Khắc phục dứt điểm 6 lỗi P2 (Medium Priority):**
   - [ ] Sửa lỗi không xóa tem dán ly cũ khi giải mã mã lỗi (`BUG-STICKER-01`).
   - [ ] Bổ sung cảnh báo trực quan màu đỏ khi Tồn sổ sách bị âm (`BUG-STOCK-01`).
   - [ ] Bổ sung nhắc nhở lưu dữ liệu khi sửa ô trên ma trận kho (`BUG-STOCK-02`).
   - [ ] Thêm cảnh báo khi nhân viên bấm tạo lệnh kho trùng nhau liên tiếp (`BUG-STOCK-03`).
   - [ ] Thêm thanh tiến trình phần trăm khi chạy mô hình dự báo D+1 (`BUG-PERF-01`).
   - [ ] Tối ưu nút Đăng xuất hiển thị trực tiếp ở góc trên bên phải màn hình (`BUG-NAV-01`).
2. **Khắc phục 2 lỗi P3 (Low Priority):**
   - [ ] Tinh chỉnh thông báo lỗi form đăng nhập khi để trống (`BUG-AUTH-01`).
   - [ ] Tối ưu thanh điều hướng radio trên màn hình điện thoại dưới 430px (`BUG-RESP-01`).
3. **Thực hiện vòng kiểm thử hồi quy (Regression Testing Round 2):**
   - Chạy lại bộ kiểm thử tự động `blackbox_master_suite.py` để đảm bảo không phát sinh lỗi phụ (Side-effects).
