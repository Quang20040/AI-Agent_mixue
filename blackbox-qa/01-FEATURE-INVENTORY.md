# 01 – FEATURE INVENTORY (DANH MỤC TÍNH NĂNG THỰC TẾ)

> **Hệ thống kiểm thử:** BeverageOps AI — Hệ thống Điều phối Vận hành Chi nhánh Mixue 39 Tôn Quang Phiệt  
> **Mã cửa hàng:** 2132 (`MX-2132`) · **Môi trường:** LOCAL (`http://localhost:8501`)  
> **Phiên bản Streamlit:** 1.40+ / Python 3.12 · **Ngày kiểm thử:** 15/10/2026  
> **Người thực hiện:** QA Lead & Exploratory Testing Specialist  

---

## 1. TỔNG QUAN HỆ THỐNG & ĐIỀU HƯỚNG

Qua quá trình rà soát trực tiếp bằng trình duyệt tự động (Playwright) và tương tác thực tế, hệ thống gồm **2 cổng truy cập phân quyền rõ rệt (RBAC)**:

1. **Cổng Khách / Chưa xác thực (Unauthenticated Portal):** Màn hình đăng nhập phong cách Tuyết Vương đỏ-trắng, hỗ trợ nhập Username/Password thủ công hoặc chọn nhanh 4 vai trò giả lập (Chủ quán, Quản lý, Nhân viên chính thức, Nhân viên thử việc).
2. **Cổng Xác thực Đăng nhập (Authenticated Portal):**
   - **Giao diện Quản trị (Admin - Chủ quán & Quản lý):** Truy cập toàn diện **8 module/tab** điều hướng.
   - **Giao diện Nhân viên (Staff - Quầy Bar & Thử việc):** Bị giới hạn truy cập, chỉ hiển thị **4 module** (Trang chủ, Báo cáo & kho [Maker Request & Shift Closing], Tem & công thức, Tuyết Vương AI).

---

## 2. BẢNG DANH MỤC TÍNH NĂNG CHI TIẾT (FEATURE INVENTORY)

| Mã ID | Module / Trang | Chức năng cụ thể | Mô tả nghiệp vụ | Quyền hạn (RBAC) | Trạng thái kiểm thử |
|---|---|---|---|---|---|
| **F001** | Xác thực | Đăng nhập tài khoản | Form nhập Username và Password có kiểm tra xác thực DB | Public | **ĐÃ KIỂM THỬ (PASS)** |
| **F002** | Xác thực | Đăng nhập nhanh 1 chạm | 4 nút chọn nhanh vai trò (Chủ quán, Quản lý, NV chính thức, NV thử việc) | Public | **ĐÃ KIỂM THỬ (PASS)** |
| **F003** | Xác thực | Bắt buộc đổi PIN 6 số | Nhân viên mới đăng nhập mật khẩu mặc định (123456) bị chặn bắt đổi PIN | STAFF_PROBATION | **ĐÃ KIỂM THỬ (PASS)** |
| **F004** | Xác thực | Đăng xuất an toàn | Xóa toàn bộ Session State và chuyển hướng về màn hình đăng nhập | Mọi vai trò | **ĐÃ KIỂM THỬ (PASS)** |
| **F005** | Trang chủ | Thực đơn 39 SKU Mixue | Hiển thị danh mục 39 đồ uống phân loại theo nhóm, giá tiền, ảnh sản phẩm | Mọi vai trò | **ĐÃ KIỂM THỬ (PASS)** |
| **F006** | Trang chủ | Tìm kiếm món đa năng | Tìm kiếm thời gian thực theo tên món có dấu tiếng Việt, không dấu, hoặc mã SKU | Mọi vai trò | **ĐÃ KIỂM THỬ (PASS)** |
| **F007** | Trang chủ | Lọc danh mục đồ uống | Lọc theo nhóm: Trà hoa quả, Trà sữa, Kem & cà phê | Mọi vai trò | **ĐÃ KIỂM THỬ (PASS)** |
| **F008** | Trang chủ | Modal Xem công thức (BOM) | Popup hiển thị định lượng chi tiết (ml/g), mã nguyên liệu và quy chuẩn SOP Bar | Mọi vai trò | **ĐÃ KIỂM THỬ (PASS)** |
| **F009** | Trang chủ | Nút Hỏi Tuyết Vương từ Modal | Chuyển thẳng sang tab Chat Tuyết Vương AI kèm câu hỏi công thức điền sẵn | Mọi vai trò | **ĐÃ KIỂM THỬ (PASS)** |
| **F010** | Trang chủ | Tạm dừng hiệu ứng chuyển động | Nút toggle dừng chuyển động GSAP/CSS hỗ trợ người nhạy cảm chuyển động | Mọi vai trò | **ĐÃ KIỂM THỬ (PASS)** |
| **F011** | Báo cáo & kho | Maker Request (Đề xuất kho) | Nhân viên quầy tạo phiếu xuất dùng / nhận hàng xe tổng chờ duyệt | STAFF | **ĐÃ KIỂM THỬ (PASS)** |
| **F012** | Báo cáo & kho | Lịch sử lệnh của nhân viên | Bảng theo dõi tiến độ duyệt các phiếu kho do cá nhân gửi | STAFF | **ĐÃ KIỂM THỬ (PASS)** |
| **F013** | Báo cáo & kho | Hòm thư Duyệt lệnh (Checker) | Quản lý kiểm duyệt: Duyệt (Approve), Từ chối (Reject), Xóa (Delete) | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F014** | Báo cáo & kho | Sổ Thẻ Kho Ma Trận 31 Ngày | Ma trận thẻ kho điện tử theo quy cách thùng/kiện/dây của tháng 10/2026 | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F015** | Báo cáo & kho | Chỉnh sửa trực tiếp ô ma trận | Bảng `st.data_editor` cho phép bấm đúp sửa số liệu và lưu vào database | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F016** | Báo cáo & kho | Thao tác lệnh kho thủ công | Form thêm lệnh trực tiếp, sửa/xóa 1 ô cụ thể hoặc xóa lệnh vĩnh viễn | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F017** | Báo cáo & kho | Xuất file Excel Thẻ kho | Tải file `.xlsx` ma trận kho tương thích Google Sheets | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F018** | Báo cáo & kho | Chốt Ca Bằng Ảnh (AI OCR) | Tải ảnh chụp sổ chốt ca bàn giao thực tế, AI trích xuất doanh thu từng ca | Mọi vai trò | **ĐÃ KIỂM THỬ (PASS)** |
| **F019** | Báo cáo & kho | 5 Thẻ KPI Đối soát Chốt Ca | Tổng thực thu, Tiền mặt gom ca, Chuyển khoản, App, Đối soát chênh lệch POS | Mọi vai trò | **ĐÃ KIỂM THỬ (PASS)** |
| **F020** | Báo cáo & kho | Báo Cáo Doanh Thu POS 30 Ngày | Biểu đồ doanh thu theo ngày, tổng doanh thu, doanh số phân theo nhóm hàng | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F021** | Báo cáo & kho | Đối Soát Hao Hụt BOM | So sánh tiêu thụ lý thuyết theo công thức và tiêu hao thực tế sổ kho | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F022** | Dự báo | So sánh Benchmark Backtest | Bảng đối chiếu 15 ngày 3 mô hình (Moving Average 7d, Seasonal Naive, DoW) | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F023** | Dự báo | Chạy dự báo nhu cầu D+1 | Thuật toán dự báo sản lượng bán ngày mai cho 39 SKU kèm cận trên/dưới | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F024** | Sơ chế | Kế hoạch nấu trà & Topping | Tính mẻ sơ chế với slider đệm an toàn (0% - 30%), tuân thủ hạn SOP | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F025** | Sơ chế | Thẩm định kế hoạch độc lập | Kiểm định độc lập mẻ làm tròn (5.000ml trà, 1.000g trân châu) đạt VERIFIED | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F026** | Sơ chế | Ký duyệt kế hoạch sơ chế (HITL) | Cơ chế phê duyệt của Quản lý Bùi Văn Quang trước khi quầy thực hiện | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F027** | Sơ chế | Báo cáo lịch sử hao hụt topping | Bảng tỷ lệ hủy topping 30 ngày qua (trân châu, thạch, trà) | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F028** | Nhập hàng | Dự thảo Đơn Đặt Hàng PO | Rà soát tồn kho hiện tại, an toàn Lead Time 2 ngày, làm tròn nguyên thùng | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F029** | Nhập hàng | Cảnh báo mặt hàng nguy cấp | Tự động phân loại mức ưu tiên CRITICAL, REORDER, OK | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F030** | Nhập hàng | Ký duyệt Đơn Nhập Hàng (HITL) | Ký duyệt phát hành đơn PO chính thức có mã định danh | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F031** | Tem & công thức | Giải mã mã tem in ly 5 số | Giải mã mã tem POS (vd: 24101 -> Trà đào, 30% đường, nóng, thêm trân châu) | Mọi vai trò | **ĐÃ KIỂM THỬ (PASS)** |
| **F032** | Tem & công thức | Hiển thị mô phỏng tem dán | Giao diện tem in nhiệt quầy bar chuẩn chi nhánh 39 Tôn Quang Phiệt | Mọi vai trò | **ĐÃ KIỂM THỬ (PASS)** |
| **F033** | Tem & công thức | Sổ tay Định lượng BOM | Dropdown chọn 39 món xem định lượng thành phần và SOP quầy bar | Mọi vai trò | **ĐÃ KIỂM THỬ (PASS)** |
| **F034** | Quản lý NV | Thống kê KPI nhân sự | 4 thẻ: Tổng nhân sự, Nhân viên chính thức, Thử việc, Quản trị | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F035** | Quản lý NV | Danh sách nhân viên chi nhánh | Bảng hiển thị thông tin tài khoản, phân quyền, trạng thái mật khẩu, trạng thái làm việc | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F036** | Quản lý NV | Đăng ký tài khoản nhân viên mới | Form tạo tài khoản mới với mật khẩu mặc định 123456 và cờ bắt buộc đổi PIN | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F037** | Quản lý NV | Reset mật khẩu nhân viên | Khôi phục mật khẩu nhân viên về 123456 khi quên mật khẩu | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F038** | Tuyết Vương AI | Chatbot Quản trị Vận hành | Truy vấn doanh số, tồn kho, mặt hàng bán chạy, nguồn tham chiếu POS | ADMIN | **ĐÃ KIỂM THỬ (PASS)** |
| **F039** | Tuyết Vương AI | Chatbot Hỗ trợ Quầy Bar | Tra cứu công thức, định lượng nguyên liệu, hướng dẫn sơ chế SOP | Mọi vai trò | **ĐÃ KIỂM THỬ (PASS)** |
| **F040** | Tuyết Vương AI | Guardrails Phân quyền Chat | Nhân viên hỏi tài chính/báo cáo bị từ chối hoặc điều hướng sang Quản lý | STAFF | **ĐÃ KIỂM THỬ (PASS)** |

---

## 3. CHECKPOINT & ĐÁNH GIÁ ĐỘ BAO PHỦ

- **Tổng số module phát hiện:** 8 module chức năng + 1 module xác thực.
- **Tổng số tính năng phát hiện:** 40 tính năng nghiệp vụ.
- **Số tính năng đã kiểm thử thực tế:** 40 / 40 tính năng (**100% Feature Coverage**).
- **Phạm vi không thể truy cập / Chưa có:** Không có khu vực nào bị thiếu hoặc không thể truy cập sau khi cấp quyền tương ứng.
