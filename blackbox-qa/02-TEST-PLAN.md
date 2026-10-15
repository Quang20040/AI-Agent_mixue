# 02 – TEST PLAN (KẾ HOẠCH KIỂM THỬ TOÀN DIỆN)

> **Dự án:** BeverageOps AI — Quản trị Điều phối Vận hành Chi nhánh Mixue 39 Tôn Quang Phiệt  
> **Giai đoạn:** Phase 1 — Comprehensive Black-Box & Exploratory Testing  
> **Tiêu chuẩn áp dụng:** ISO/IEC/IEEE 29119 Software Testing Standards  
> **Môi trường thực thi:** Local Environment (`http://localhost:8501`)  

---

## 1. MỤC TIÊU & PHẠM VI (SCOPE)

### 1.1. Mục tiêu kiểm thử
1. Thẩm định độc lập 100% tính năng thực tế đang có trên hệ thống mà không dựa vào giả định.
2. Kiểm tra tính toàn vẹn của logic nghiệp vụ F&B (quy chuẩn mẻ 5.000ml trà, 1.000g trân châu, đệm Lead Time 2 ngày, chốt ca POS).
3. Đánh giá tính an toàn của cơ chế phân quyền RBAC 2 cấp độ (Admin vs Staff) và luồng Maker-Checker trong quản lý kho.
4. Phát hiện lỗi giao diện (UI), trải nghiệm (UX), tràn layout trên 7 kích thước màn hình phổ biến.
5. Kiểm tra khả năng phục hồi khi gặp dữ liệu bất thường, tấn công tiêm nhiễm (SQLi/XSS) và mất kết nối.

### 1.2. Phạm vi kiểm thử (In-Scope)
- **Module 0 – Xác thực & Phiên (Authentication & Session):** Đăng nhập, đổi mật khẩu bắt buộc 6 số, đăng xuất, duy trì phiên khi F5/refresh.
- **Module 1 – Trang chủ (Home & Menu Explorer):** 39 SKU, tìm kiếm có dấu/không dấu, lọc nhóm, popup BOM công thức, link sang Chat.
- **Module 2 – Báo cáo & Kho (Reports & Inventory):** 
  - Maker-Checker: Nhân viên gửi lệnh xuất/nhập, Quản lý duyệt/từ chối/xóa.
  - Sổ thẻ kho ma trận 31 ngày (tháng 10/2026), chỉnh sửa ô trực tiếp qua `st.data_editor`, xuất file Excel.
  - Chốt ca bằng ảnh (Shift closing) AI OCR, đối soát doanh thu thực thu vs máy POS.
  - Báo cáo doanh số POS 30 ngày, đối soát hao hụt BOM.
- **Module 3 – Dự báo (Demand Forecasting D+1):** So sánh 3 mô hình Backtest (Moving Average, Seasonal Naive, DoW), chạy dự báo 39 SKU.
- **Module 4 – Sơ chế (Batch Preparation Plan):** Thuật toán làm tròn mẻ, đệm an toàn, thẩm định độc lập VERIFIED, ký duyệt HITL.
- **Module 5 – Nhập hàng (Replenishment PO):** Tồn kho an toàn, Lead time 2 ngày, làm tròn nguyên thùng, ký duyệt HITL.
- **Module 6 – Tem & Công thức (Sticker & Recipe BOM):** Giải mã tem ly 5 chữ số, kiểm tra định dạng, tra cứu định lượng BOM.
- **Module 7 – Quản lý nhân viên (Staff RBAC):** KPI nhân sự, danh sách nhân viên, đăng ký tài khoản mới, kiểm tra trùng username, reset mật khẩu về 123456.
- **Module 8 – Trợ lý Tuyết Vương AI (Operations Chatbot):** Hỏi doanh số POS, hỏi công thức pha chế, guardrail chặn quyền nhân viên.

### 1.3. Ngoài phạm vi (Out-of-Scope)
- Sửa trực tiếp mã nguồn hoặc sửa database bên ngoài giao diện (tuân thủ nghiêm ngặt quy tắc Black-box).
- Tải trọng cực đại (Stress/Load Testing > 1.000 concurrent users).
- Kiểm thử thanh toán tiền thật qua cổng ngân hàng ngoài đời thực.

---

## 2. CHIẾN LƯỢC & PHƯƠNG PHÁP KIỂM THỬ (TEST STRATEGY)

Áp dụng mô hình kiểm thử đa tầng:

```
┌────────────────────────────────────────────────────────┐
│               1. Black-box Functional Testing          │
│   Happy Path · Boundary Value · Equivalence Classes    │
└──────────────────────────┬─────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────┐
│            2. Business Logic & RBAC Verification       │
│   Maker-Checker · State Transitions · HITL Approval    │
└──────────────────────────┬─────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────┐
│         3. Responsive & Cross-device Viewport Testing  │
│   320px · 375px · 430px · 768px · 1024px · 1366px · 1920px
└──────────────────────────┬─────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────┐
│          4. Exploratory & Negative Testing             │
│   Rapid Clicks · Long Strings · SQLi/XSS Payloads      │
└──────────────────────────┬─────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────┐
│          5. Session, Recovery & Reliability            │
│   F5 Retention · Back Button · Token Timeout           │
└────────────────────────────────────────────────────────┘
```

---

## 3. MÔI TRƯỜNG & TÀI KHOẢN KIỂM THỬ

### 3.1. Cấu hình môi trường
- **URL Ứng dụng:** `http://localhost:8501`
- **Framework nền tảng:** Streamlit 1.40+ (Python 3.12 64-bit trên Windows 11)
- **Công cụ điều khiển trình duyệt:** Microsoft Playwright (Chromium Headless & Headed)
- **Cơ sở dữ liệu:** SQLite / SQLAlchemy ORM kết nối dữ liệu 30 ngày chi nhánh 2132

### 3.2. Ma trận tài khoản kiểm thử
| Tên tài khoản | Mật khẩu | Vai trò phân quyền | Thẩm quyền thực tế |
|---|---|---|---|
| `quanly` | `123` | **ADMIN (Quản lý cửa hàng)** | Toàn quyền 8 tab: Xem tài chính, duyệt lệnh kho, ký PO, ký sơ chế, quản lý nhân sự |
| `chucuahang` | `123` | **ADMIN (Chủ cửa hàng)** | Toàn quyền cao nhất: Kiểm soát dòng tiền, đối soát thất thoát, phân quyền nhân sự |
| `nhanvien` | `123` | **STAFF (Nhân viên chính thức)** | Quầy bar: Tra cứu 39 món, xem BOM, gửi đề xuất lệnh kho, chốt ca, hỏi AI công thức |
| `nhanvien_moi` | `123456` | **STAFF_PROBATION (Thử việc)** | Mật khẩu mặc định 123456; có cờ kích hoạt bắt buộc đổi mã PIN 6 số |

---

## 4. MA TRẬN VIEWPORT KIỂM THỬ RESPONSIVE

| Tên thiết bị mô phỏng | Độ rộng (Width) | Chiều cao (Height) | Tiêu chí đánh giá |
|---|---|---|---|
| **Small Mobile** (iPhone SE 1st) | 320px | 568px | Không vỡ layout, không tràn thanh cuộn ngang body |
| **Mobile** (iPhone 8 / SE 2nd) | 375px | 667px | Menu co giãn 1 cột, nút bấm chạm chuẩn tối thiểu 44px |
| **Large Mobile** (iPhone 14/15 Pro Max) | 430px | 932px | Thẻ món hiển thị cân đối, text không bị cắt ngắn |
| **Tablet Portrait** (iPad Mini/Air) | 768px | 1024px | Bố cục chuyển đổi 2 cột mượt mà, sidebar mở/gập tốt |
| **Tablet Landscape** (iPad ngang) | 1024px | 768px | Tận dụng tốt không gian ngang, biểu đồ hiển thị đủ nhãn |
| **Laptop** (Màn hình phổ thông) | 1366px | 768px | Bố cục chuẩn desktop, ma trận thẻ kho xem rõ 10 cột |
| **Desktop Full HD** (Màn hình tiêu chuẩn) | 1920px | 1080px | Cân đối khoảng trắng, không bị dãn component quá mức |

---

## 5. TIÊU CHÍ NGHIỆM THU (ENTRY & EXIT CRITERIA)

### 5.1. Entry Criteria
- Ứng dụng Streamlit đang lắng nghe trên cổng `localhost:8501`.
- Cơ sở dữ liệu SQLite đã nạp đủ dữ liệu chuẩn hóa 30 ngày (bán hàng POS, định lượng BOM, thẻ kho).
- Trình duyệt Chromium của Playwright khởi tạo thành công không lỗi driver.

### 5.2. Exit Criteria
- 100% tính năng trong Feature Inventory được thực thi kiểm thử.
- Thu thập đầy đủ bằng chứng kiểm thử (Screenshot, Console Log, Network Traffic Log).
- Đánh giá phân loại toàn bộ lỗi theo thang P0 (Critical) $\rightarrow$ P3 (Low).
- Xuất bản đầy đủ bộ 11 báo cáo đánh giá và kết luận GO / CONDITIONAL GO / NO-GO.
