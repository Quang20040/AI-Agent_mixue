# BẢNG ĐIỂM ĐÁNH GIÁ CHẤT LƯỢNG KỸ THUẬT (QUALITY SCORECARD)
## HỆ THỐNG: BEVERAGE-OPS AI — CHI NHÁNH MIXUE 39 TÔN QUANG PHIỆT
**Mã tài liệu:** `WB-AUDIT-14-SCORE`  
**Phiên bản:** 2.0.0-PROD-AUDIT  
**Đối tượng:** Đánh giá định lượng toàn diện hệ thống phần mềm theo khung thang điểm 100 chuẩn ISO/IEC 25010

---

## 1. TỔNG HỢP ĐIỂM SỐ KỸ THUẬT TOÀN DIỆN (EXECUTIVE SCORECARD)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BEVERAGE-OPS AI QUALITY SCORECARD                        │
├──────────────────────────────────────┬──────────┬──────────┬────────────────┤
│ Trục Đánh Giá Kỹ Thuật (Pillars)     │ Thang    │ Điểm Đạt │ Tỷ Lệ Đạt      │
│                                      │ Điểm     │ Được     │ (%)            │
├──────────────────────────────────────┼──────────┼──────────┼────────────────┤
│ 1. Kiến Trúc & Thiết Kế Hệ Thống     │ 15 Điểm  │ **10.5** │ 70.0%          │
├──────────────────────────────────────┼──────────┼──────────┼────────────────┤
│ 2. Chất Lượng Mã Nguồn & Clean Code  │ 15 Điểm  │ **10.0** │ 66.7%          │
├──────────────────────────────────────┼──────────┼──────────┼────────────────┤
│ 3. Tính Chính Xác Của Logic Nghiệp Vụ│ 15 Điểm  │ **12.5** │ 83.3%          │
├──────────────────────────────────────┼──────────┼──────────┼────────────────┤
│ 4. An Toàn Thông Tin & Bảo Mật (RBAC)│ 15 Điểm  │ **8.5**  │ 56.7%          │
├──────────────────────────────────────┼──────────┼──────────┼────────────────┤
│ 5. Hiệu Năng & Tối Ưu Hóa Độ Trễ     │ 10 Điểm  │ **5.5**  │ 55.0%          │
├──────────────────────────────────────┼──────────┼──────────┼────────────────┤
│ 6. Kiểm Thử & Tự Động Hóa (QA Auto)  │ 15 Điểm  │ **10.5** │ 70.0%          │
├──────────────────────────────────────┼──────────┼──────────┼────────────────┤
│ 7. Hạ Tầng, DevOps & CI/CD           │ 15 Điểm  │ **5.0**  │ 33.3%          │
├──────────────────────────────────────┼──────────┼──────────┼────────────────┤
│ **TỔNG ĐIỂM KỸ THUẬT TOÀN DIỆN**     │ **100**  │ **62.5** │ **62.5%**      │
├──────────────────────────────────────┴──────────┴──────────┴────────────────┤
│ **XẾP LOẠI CHẤT LƯỢNG (GRADE):**                       │ **HẠNG C+**        │
│ **QUYẾT NGHỊ SẴN SÀNG SẢN XUẤT (VERDICT):**            │ **CHƯA ĐẠT (NO-GO)│
└─────────────────────────────────────────────────────────┴────────────────────┘
```

---

## 2. BẢNG TIÊU CHÍ ĐÁNH GIÁ CHI TIẾT TỪNG TRỤ CỘT

### Trụ Cột 1: Kiến Trúc & Thiết Kế Hệ Thống (Đạt 10.5 / 15 Điểm)
- **Tính Module Hóa & Đóng Gói (3.5 / 5.0):**
  Các engine tính toán (`bom_engine`, `forecasting`, `optimizer`, `validator`) được đóng gói tốt thành các class độc lập. Tuy nhiên, `mixue_agent.py` và `app.py` là các God file khổng lồ phá vỡ tính module hóa.
- **Tách Biệt Ranh Giới (Separation of Concerns) (3.0 / 5.0):**
  UI Streamlit dính chặt với các hàm query CSDL và logic nghiệp vụ. Tồn tại hai hệ thống lưu trữ phân mảnh (SQLite vs JSON file).
- **Khả Năng Mở Rộng & Đa Cửa Hàng (4.0 / 5.0):**
  Đã có `store_id` trong bán hàng, nhưng bảng thẻ kho 31 ngày `daily_stock_movements` hoàn toàn thiếu `store_id`.

### Trụ Cột 2: Chất Lượng Mã Nguồn & Clean Code (Đạt 10.0 / 15 Điểm)
- **Tính Đọc Hiểu & Naming Conventions (4.0 / 5.0):**
  Tên biến, hàm và lớp bằng tiếng Anh và tiếng Việt rất sát nghĩa với thực tế nghiệp vụ quán trà sữa Mixue.
- **Độ Phức Tạp & Vòng Lặp Lồng Ghép (2.5 / 5.0):**
  Hàm `process_query()` có Cyclomatic Complexity lên tới 48, lồng ghép 5 cấp `if/else`, rất khó bảo trì.
- **Phân Tích Tĩnh & Code Smells (3.5 / 5.0):**
  Ruff phát hiện 375 lỗi: 22 blind excepts (`except Exception:`), 5 nuốt lỗi (`pass`), 47 unused imports.

### Trụ Cột 3: Tính Chính Xác Của Logic Nghiệp Vụ (Đạt 12.5 / 15 Điểm)
- **Thuật Toán Cốt Lõi (4.5 / 5.0):**
  BOM explosion, tối ưu mẻ topping (1000g/5000ml), hạn dùng 4h, và quy cách đóng gói thùng/kiện Master Mixue được cài đặt rất xuất sắc.
- **Xử Lý Biên & Ngoại Lệ (3.5 / 5.0):**
  Đã xử lý chia cho 0, chặn số lượng âm qua validator. Tuy nhiên, công thức tồn kho trong `bom_engine.py` bị thiếu Tồn đầu kỳ.
- **Đối Soát & Tính Nhất Quán Dữ Liệu (4.5 / 5.0):**
  Quy trình Maker-Checker 2 cấp độ duyệt lệnh kho hoạt động chuẩn mực.

### Trụ Cột 4: An Toàn Thông Tin & Bảo Mật Ứng Dụng (Đạt 8.5 / 15 Điểm)
- **Xác Thực & Quản Lý Mật Khẩu (1.5 / 5.0 - ĐIỂM LIỆT):**
  Băm SHA-256 không có Salt; tồn tại cửa hậu plaintext fallback (`clean_plain == hashed_or_plain`); mật khẩu admin mặc định "123".
- **Phân Quyền Truy Cập (RBAC) (3.5 / 5.0):**
  Phân quyền 2 cấp độ rõ ràng trên UI và trong AI Agent. Nhưng thiếu middleware kiểm soát ở tầng API.
- **AI Safety & Red Teaming (3.5 / 5.0):**
  Chặn thành công 5 vector tấn công: Prompt Injection, Credential Leak, HR Privacy, Out of Scope, Privilege Escalation.

### Trụ Cột 5: Hiệu Năng & Tối Ưu Hóa (Đạt 5.5 / 10 Điểm)
- **Độ Trễ & Thời Gian Phản Hồi (2.0 / 5.0):**
  Dự báo nhu cầu mất 14 giây do chạy 1,872 lượt lặp backtest tuần tự không cache.
- **Tối Ưu Hóa Tài Nguyên & Caching (3.5 / 5.0):**
  Đã có `@lru_cache` cho assets ảnh, nhưng thiếu cache dữ liệu nghiệp vụ quan trọng.

### Trụ Cột 6: Kiểm Thử & Đảm Bảo Chất Lượng (Đạt 10.5 / 15 Điểm)
- **Quy Mô & Tỷ Lệ Vượt Qua (3.5 / 5.0):**
  Có 46 bài test tự động, nhưng tỷ lệ đạt chỉ là 44/46 (95.7%) do 2 bài test chốt ca bị FAILED.
- **Tính Độc Lập Của Bộ Test (F.I.R.S.T) (3.0 / 5.0):**
  Bộ test bị ô nhiễm trạng thái (Test Pollution) do phụ thuộc vào file JSON dùng chung có thể biến đổi.
- **Tốc Độ Kiểm Thử (4.0 / 5.0):**
  Test suite chạy mất 3 phút 23 giây (chậm do tính backtest nhiều lần).

### Trụ Cột 7: Hạ Tầng, DevOps & CI/CD (Đạt 5.0 / 15 Điểm - YẾU NHẤT)
- **Quản Lý Thư Viện Phụ Thuộc (1.0 / 5.0 - ĐIỂM LIỆT):**
  Hoàn toàn không có `requirements.txt`, `Pipfile` hay `poetry.lock`.
- **Container Hóa Docker (2.0 / 5.0):**
  Không có `Dockerfile` cho ứng dụng Streamlit; docker-compose chỉ chạy CSDL.
- **Tự Động Hóa CI/CD (2.0 / 5.0):**
  Không có GitHub Actions workflow để tự động lint và test khi tạo Pull Request.

---

## 3. SO SÁNH VỚI CHUẨN DOANH NGHIỆP (INDUSTRY BENCHMARK COMPARISON)

```
                   SO SÁNH VỚI CHUẨN SẴN SÀNG PRODUCTION (80/100)
Điểm Số
 100 ▲                                                       Chuẩn Production (80đ)
     │                                                     ┌──────────────────────┐
  80 ┼ - - - - - - - - - - - - - - - - - - - - - - - - - - │ - - - - - - - - - - -│
     │                                                     │                      │
  60 ┼ ─── [ BeverageOps AI Hiện Tại: 62.5 Điểm ] ────────│──────────────────────┘
     │     (Kiến trúc tốt, Logic F&B xuất sắc,             │
  40 ┼      nhưng bị kéo tụt bởi Bảo mật & DevOps)         │
     │                                                     │
  20 ┼                                                     │
     │                                                     │
   0 ┴─────────────────────────────────────────────────────┴──────────────────────►
```

**Nhận định của Technical Audit Team:**
- **BeverageOps AI** có phần lõi nghiệp vụ F&B (BOM explosion, dự báo rolling-origin, quy cách đóng gói thùng/kiện chuẩn Mixue) được xây dựng **rất bài bản và có độ chính xác toán học cao** (đạt 83.3%).
- Tuy nhiên, hệ thống bị trừ điểm nặng nề ở 3 trục phi chức năng (Non-functional Requirements):
  1. **Bảo mật mật khẩu (Cryptographic failure):** Băm SHA-256 không salt và cửa hậu plaintext.
  2. **Hiệu năng (Performance bottleneck):** Độ trễ 14 giây không cache.
  3. **DevOps (Missing dependencies & CI/CD):** Không thể dựng lại môi trường một cách tự động.

Chỉ cần hoàn thành đợt sửa chữa kỹ thuật P0/P1 trong vòng **5 ngày làm việc**, điểm số chất lượng của hệ thống sẽ tăng từ **62.5 lên 84.5 điểm**, đủ điều kiện cấp chứng chỉ sẵn sàng Production.
