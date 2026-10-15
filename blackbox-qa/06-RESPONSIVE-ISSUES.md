# 06 – RESPONSIVE & CROSS-DEVICE AUDIT (BÁO CÁO KIỂM THỬ ĐA THIẾT BỊ)

> **Dự án:** BeverageOps AI — Quản trị Điều phối Vận hành Chi nhánh Mixue 39 Tôn Quang Phiệt  
> **Chuyên môn đánh giá:** Responsive Testing Specialist & Mobile Usability Auditor  
> **Phạm vi kiểm thử:** 7 kích thước Viewport chuẩn (320px $\rightarrow$ 1920px)  
> **Thư mục bằng chứng:** `blackbox-qa/evidence/screenshots/`  

---

## 1. MA TRẬN KẾT QUẢ KIỂM THỬ TRÊN 7 VIEWPORT

| Viewport | Thiết bị đại diện | Chiều rộng | Chiều cao | Cuộn ngang body (Overflow) | Bố cục Menu & Thẻ món | Đánh giá tổng thể | Bằng chứng |
|---|---|---:|---:|:---:|:---:|:---:|---|
| **Small Mobile** | iPhone SE (1st gen) | 320px | 568px | **KHÔNG TRÀN (0px)** | Co giãn 1 cột, cân đối | **PASS** | `evidence/screenshots/resp_320_small_mobile_home.png` |
| **Mobile** | iPhone 8 / SE (2nd) | 375px | 667px | **KHÔNG TRÀN (0px)** | 1 cột, nút bấm to rõ | **PASS** | `evidence/screenshots/resp_375_mobile_home.png` |
| **Large Mobile** | iPhone 14/15 Pro Max | 430px | 932px | **KHÔNG TRÀN (0px)** | 1 cột rộng rãi, ảnh đẹp | **PASS** | `evidence/screenshots/resp_430_large_mobile_home.png` |
| **Tablet Portrait** | iPad Mini / Air đứng | 768px | 1024px | **KHÔNG TRÀN (0px)** | Tự động chuyển 2 cột | **PASS** | `evidence/screenshots/resp_768_tablet_home.png` |
| **Tablet Landscape**| iPad xoay ngang | 1024px | 768px | **KHÔNG TRÀN (0px)** | 3 cột, hiển thị tối ưu | **PASS** | `evidence/screenshots/resp_1024_tablet_landscape_home.png` |
| **Laptop HD** | Laptop phổ thông | 1366px | 768px | **KHÔNG TRÀN (0px)** | 4 cột, chuẩn tỷ lệ | **PASS** | `evidence/screenshots/resp_1366_laptop_home.png` |
| **Desktop Full HD** | Màn hình chuẩn | 1920px | 1080px | **KHÔNG TRÀN (0px)** | 4-5 cột, khoảng trắng tốt | **PASS** | `evidence/screenshots/resp_1920_desktop_home.png` |

---

## 2. ĐÁNH GIÁ CHI TIẾT THEO TỪNG KÍCH THƯỚC

### 2.1. Small Mobile (320px) & Mobile (375px - 430px)
- **Điểm tích cực:**
  - Trang chủ co giãn mượt mà thành 1 cột duy nhất (`grid-template-columns: 1fr`).
  - Thanh cuộn ngang body được kiểm soát tốt (`scrollWidth` đo được hoàn toàn bằng `clientWidth`), không làm vỡ viền màn hình điện thoại.
  - Form đăng nhập và form gửi lệnh kho tự động xếp dọc các trường nhập liệu, nút bấm có kích thước chạm ngón tay (Touch Target) đạt chuẩn $\ge 44\text{px}$.
- **Điểm cần khắc phục:**
  - **Thanh điều hướng Radio (8 tabs):** Trên chiều rộng 320px - 430px, hàng radio 8 nút bị tràn theo chiều ngang thành nhiều dòng, chiếm gần nửa chiều cao màn hình đầu tiên (Above the fold).
  - **Bảng Ma trận Thẻ kho 31 ngày:** Trên màn hình điện thoại, bảng `st.data_editor` buộc phải cuộn ngang liên tục, rất khó để nhân viên quầy bar kiểm tra trên điện thoại cá nhân.

---

### 2.2. Tablet (768px - 1024px)
- **Điểm tích cực:**
  - Điểm chuyển đổi (Breakpoints) tại 768px và 1024px hoạt động rất chính xác: lưới thẻ món tự động chia thành 2 cột (768px) và 3 cột (1024px).
  - Không gian xem các biểu đồ doanh thu và bảng kiểm kê rất thoáng, nhãn trục ngày tháng không bị đè chữ lên nhau.
  - Phân hệ Chốt Ca Bằng Ảnh hiển thị 5 thẻ KPI thành 2 hàng rất cân xứng.
- **Điểm cần lưu ý:**
  - Sidebar khi mở trên tablet sẽ che khuất một phần nội dung chính nếu không chạm ra ngoài để đóng.

---

### 2.3. Laptop (1366px) & Desktop (1920px)
- **Điểm tích cực:**
  - Đây là môi trường hiển thị hoàn hảo nhất của ứng dụng: Bảng ma trận thẻ kho xem được gần 20 ngày mà không cần cuộn quá nhiều.
  - Phân hệ Sơ chế và Phân hệ Nhập hàng chia cột 1 : 1.85 rất trực quan: Cột trái là bảng điều khiển và nhập tham số, cột phải là bảng SOP quy chuẩn và kết quả làm tròn mẻ.
  - Hiệu ứng đổ bóng, linh vật Tuyết Vương và font chữ hiển thị sắc nét, không bị răng cưa.

---

## 3. DANH SÁCH CÁC VẤN ĐỀ RESPONSIVE CẦN TINH CHỈNH

| Mã lỗi | Màn hình bị ảnh hưởng | Vấn đề phát hiện | Giải pháp khuyến nghị | Mức độ ưu tiên |
|---|---|---|---|---|
| **RESP-01** | Mobile (320px - 430px) | Thanh điều hướng 8 tabs bị ngắt thành 4-5 hàng chiếm diện tích lớn | Chuyển thành Menu Dropdown hoặc Bottom Navigation Bar khi màn hình $\le 600\text{px}$ | **P2 (Medium)** |
| **RESP-02** | Mobile (320px - 430px) | Modal chi tiết công thức (BOM Popup) bảng nguyên liệu bị chật chội | Ẩn bớt cột "Mã nguyên liệu", chỉ giữ lại "Tên nguyên liệu" và "Định lượng" trên mobile | **P3 (Low)** |
| **RESP-03** | Tablet (768px) | Nút đóng sidebar góc trên bên trái dễ chạm nhầm với nút quay về trang chủ | Tăng padding giữa icon gập sidebar và header ứng dụng | **P3 (Low)** |
