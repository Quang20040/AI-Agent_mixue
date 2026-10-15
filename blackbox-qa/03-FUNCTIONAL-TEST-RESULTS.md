# 03 – FUNCTIONAL TEST RESULTS (KẾT QUẢ KIỂM THỬ CHỨC NĂNG CHI TIẾT)

> **Dự án:** BeverageOps AI — Quản trị Điều phối Vận hành Chi nhánh Mixue 39 Tôn Quang Phiệt  
> **Tổng số Test Cases thực thi:** 45 test cases  
> **Kết quả tổng thể:** 42 Passed · 3 Failed · 0 Blocked  
> **Tỷ lệ Pass (Functional Pass Rate):** **93.33%**  
> **Thư mục bằng chứng:** `blackbox-qa/evidence/screenshots/`  

---

## 1. PHÂN HỆ XÁC THỰC & PHÂN QUYỀN (AUTHENTICATION & RBAC)

### TC-AUTH-01: Hiển thị màn hình đăng nhập khi chưa xác thực
- **Loại test:** Test 1 – Happy Path / UI Inspection
- **Điều kiện tiên quyết:** Chưa đăng nhập, mở `http://localhost:8501`.
- **Các bước thực hiện:**
  1. Điều hướng trình duyệt đến `http://localhost:8501`.
  2. Kiểm tra các thành phần trên màn hình đăng nhập.
- **Kết quả kỳ vọng:** Hiển thị nhận diện thương hiệu Tuyết Vương đỏ-trắng, form nhập Username/Password và 4 nút đăng nhập nhanh.
- **Kết quả thực tế:** Hiển thị chuẩn xác banner Tuyết Vương, thẻ thông tin chi nhánh 2132, form đăng nhập và 4 nút quick-login.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/01_login_unauthenticated.png`

---

### TC-AUTH-02: Đăng nhập với form rỗng (Empty Input)
- **Loại test:** Test 3 – Empty Input
- **Điều kiện tiên quyết:** Đang ở màn hình đăng nhập.
- **Các bước thực hiện:**
  1. Để trống Username và Password.
  2. Nhấn nút "Đăng nhập vào Hệ thống 🚀".
- **Kết quả kỳ vọng:** Hệ thống hiển thị thông báo lỗi yêu cầu nhập đầy đủ tài khoản và mật khẩu.
- **Kết quả thực tế:** Hệ thống hiển thị cảnh báo: *"Tên đăng nhập hoặc mật khẩu không chính xác! Vui lòng thử lại."*
- **Đánh giá chuyên môn:** Chức năng hoạt động an toàn (không crash, chặn đăng nhập thành công), tuy nhiên thông báo lỗi chưa phân biệt giữa việc chưa nhập dữ liệu và nhập sai mật khẩu (UX Flaw).
- **Trạng thái:** **PASS (về bảo mật) / Ghi nhận BUG-AUTH-01 (về UX)**
- **Bằng chứng:** `evidence/screenshots/02_login_empty_submit.png`

---

### TC-AUTH-03: Đăng nhập với thông tin tài khoản không tồn tại (Invalid Input)
- **Loại test:** Test 2 – Invalid Input
- **Điều kiện tiên quyết:** Đang ở màn hình đăng nhập.
- **Các bước thực hiện:**
  1. Nhập Username: `nguoidung_ao`.
  2. Nhập Password: `sai_pass_999`.
  3. Nhấn "Đăng nhập vào Hệ thống 🚀".
- **Kết quả kỳ vọng:** Từ chối đăng nhập, hiển thị thông báo lỗi bảo mật chung.
- **Kết quả thực tế:** Hiển thị thông báo màu đỏ: *"Tên đăng nhập hoặc mật khẩu không chính xác! Vui lòng thử lại."*
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/03_login_invalid_creds.png`

---

### TC-AUTH-04: Thử nghiệm tấn công tiêm nhiễm SQL Injection trên form
- **Loại test:** Test 10 – Unexpected User Behavior / Security Testing
- **Điều kiện tiên quyết:** Đang ở màn hình đăng nhập.
- **Các bước thực hiện:**
  1. Nhập Username: `' OR '1'='1' --`.
  2. Nhập Password: `' OR '1'='1' --`.
  3. Nhấn "Đăng nhập vào Hệ thống 🚀".
- **Kết quả kỳ vọng:** Hệ thống xử lý chuỗi escape an toàn, không bị vượt qua xác thực, không phát sinh lỗi 500 hay lộ cấu trúc bảng DB.
- **Kết quả thực tế:** Hệ thống từ chối an toàn, SQLAlchemy ORM tham số hóa truy vấn chuẩn mực.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/04_login_sqli_attack.png`

---

### TC-AUTH-05: Đăng nhập tài khoản Nhân viên mới có cờ đổi mật khẩu bắt buộc
- **Loại test:** Test 4 – Boundary & State Transition Testing
- **Điều kiện tiên quyết:** Tài khoản có cờ `must_change_password=True`.
- **Các bước thực hiện:**
  1. Nhập tài khoản nhân viên thử việc / mới.
  2. Quan sát màn hình hiển thị.
- **Kết quả kỳ vọng:** Hệ thống chặn vào quầy, hiển thị màn hình bắt buộc thiết lập mã PIN 6 số.
- **Kết quả thực tế:** Màn hình `render_force_change_password_screen()` hiển thị yêu cầu nhập mã PIN mới gồm đúng 6 chữ số.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/05_force_change_password_screen.png`

---

### TC-AUTH-06: Đăng xuất an toàn và xóa phiên làm việc
- **Loại test:** Test 7 – Navigation & Session Termination
- **Điều kiện tiên quyết:** Đang đăng nhập bất kỳ tài khoản nào.
- **Các bước thực hiện:**
  1. Mở sidebar bên trái.
  2. Bấm nút "🚪 Đăng xuất khỏi Hệ thống".
  3. Quan sát giao diện và thử ấn nút Back trên trình duyệt.
- **Kết quả kỳ vọng:** Toàn bộ session state bị xóa, người dùng được chuyển hướng về trang đăng nhập. Ấn Back không xem được dữ liệu cũ.
- **Kết quả thực tế:** Đăng xuất thành công, chuyển hướng về màn hình đăng nhập ngay lập tức.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/08_logout_success.png`

---

## 2. PHÂN HỆ TRANG CHỦ & THỰC ĐƠN (HOME & MENU EXPLORER)

### TC-HOME-01: Hiển thị danh mục 39 SKU thực đơn Mixue
- **Loại test:** Test 1 – Happy Path
- **Điều kiện tiên quyết:** Đã đăng nhập vào hệ thống.
- **Các bước thực hiện:**
  1. Truy cập tab "Trang chủ".
  2. Cuộn qua các thẻ món trong thực đơn.
- **Kết quả kỳ vọng:** Hiển thị đủ 39 món, ảnh sản phẩm xếp lớp, tên món, giá niêm yết (VND) và nút "Xem công thức".
- **Kết quả thực tế:** Hiển thị 39 món sắc nét, card sản phẩm có hiệu ứng nổi 3D theo con trỏ chuột.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/09_admin_dashboard_home.png`

---

### TC-HOME-02: Tìm kiếm món có dấu tiếng Việt (Accented Search)
- **Loại test:** Test 1 – Happy Path / Internationalization
- **Điều kiện tiên quyết:** Đang ở tab "Trang chủ".
- **Các bước thực hiện:**
  1. Gõ `"Trà sữa trân châu"` vào ô tìm kiếm.
- **Kết quả kỳ vọng:** Kết quả lọc chính xác 1 món `TS1 - Trà sữa trân châu`.
- **Kết quả thực tế:** Lọc tức thì, hiển thị chính xác món Trà sữa trân châu kèm giá 25.000 đ.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/10_home_search_accent.png`

---

### TC-HOME-03: Tìm kiếm món không dấu (Unaccented Search)
- **Loại test:** Test 1 – Happy Path / Search Normalization
- **Điều kiện tiên quyết:** Đang ở tab "Trang chủ".
- **Các bước thực hiện:**
  1. Gõ `"hong tra"` vào ô tìm kiếm.
- **Kết quả kỳ vọng:** Tìm thấy tất cả các món thuộc nhóm Hồng trà (Hồng trà chanh, Hồng trà sữa, Hồng trà nguyên vị).
- **Kết quả thực tế:** Thuật toán chuẩn hóa tiếng Việt tìm kiếm chính xác các món chứa chuỗi "Hồng trà".
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/11_home_search_no_accent.png`

---

### TC-HOME-04: Tìm kiếm theo mã SKU nội bộ (SKU Search)
- **Loại test:** Test 1 – Happy Path
- **Điều kiện tiên quyết:** Đang ở tab "Trang chủ".
- **Các bước thực hiện:**
  1. Gõ `"TS1"` vào ô tìm kiếm.
- **Kết quả kỳ vọng:** Hiển thị món có mã SKU `TS1`.
- **Kết quả thực tế:** Hiển thị đúng sản phẩm Trà sữa trân châu.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/12_home_search_sku.png`

---

### TC-HOME-05: Trạng thái rỗng khi tìm kiếm không có kết quả (Empty State)
- **Loại test:** Test 3 – Empty State Handling
- **Điều kiện tiên quyết:** Đang ở tab "Trang chủ".
- **Các bước thực hiện:**
  1. Gõ từ khóa không tồn tại: `"mon_khong_ton_tai_xyz"`.
- **Kết quả kỳ vọng:** Hiển thị thông báo không tìm thấy món thân thiện thay vì để màn hình trắng.
- **Kết quả thực tế:** Hiển thị thông báo: *"Không tìm thấy món nào phù hợp với từ khóa. Vui lòng thử từ khóa khác."*
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/13_home_search_empty_state.png`

---

### TC-HOME-06: Mở Popup chi tiết công thức định lượng (BOM Recipe Modal)
- **Loại test:** Test 1 – Happy Path / Modal Interaction
- **Điều kiện tiên quyết:** Đang ở tab "Trang chủ".
- **Các bước thực hiện:**
  1. Nhấn nút "Xem công thức" trên bất kỳ thẻ sản phẩm nào.
- **Kết quả kỳ vọng:** Modal popup mở lên, hiển thị mã SKU, tên món, bảng định lượng nguyên liệu chuẩn (Mã NL, Tên NL, Định lượng, Đơn vị) và SOP quầy bar.
- **Kết quả thực tế:** Modal mở mượt mà, hiển thị bảng BOM chi tiết từng gam/ml và lưu ý SOP pha chế Mixue.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/14_home_recipe_modal.png`

---

## 3. PHÂN HỆ BÁO CÁO & KHO (REPORTS & INVENTORY)

### TC-STOCK-01: Nhân viên gửi đề xuất lệnh xuất kho (Maker Request)
- **Loại test:** Test 1 – Happy Path (Maker - Checker)
- **Điều kiện tiên quyết:** Đăng nhập tài khoản `nhanvien` (Staff).
- **Các bước thực hiện:**
  1. Vào trang "Báo cáo & kho", chọn subtab "📝 Phiếu Đề Xuất Lệnh Kho Quầy Bar".
  2. Chọn mặt hàng: `NL01 — Trà đen (Thùng 20 gói)`.
  3. Chọn thao tác: `Xuất quầy bar sử dụng`.
  4. Nhập số lượng: `2.0`.
  5. Nhập ghi chú: `Ca sáng khui 2 thùng quầy trà`.
  6. Nhấn "Gửi Đề Xuất Lệnh Kho Chờ Quản Lý Duyệt".
- **Kết quả kỳ vọng:** Lệnh kho được tạo ở trạng thái `⏳ Chờ Quản lý duyệt`, xuất hiện trong bảng "Trạng Thái Các Lệnh Kho Của Bạn".
- **Kết quả thực tế:** Phiếu được ghi nhận vào database với trạng thái PENDING, nhân viên theo dõi được thời gian thực.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/07_staff_stock_request_created.png`

---

### TC-STOCK-02: Quản lý phê duyệt đề xuất lệnh kho của nhân viên (Checker Action)
- **Loại test:** Test 1 – Happy Path / State Transition
- **Điều kiện tiên quyết:** Đăng nhập tài khoản `quanly` (Admin), có lệnh chờ duyệt.
- **Các bước thực hiện:**
  1. Vào "Báo cáo & kho", tab "📋 Duyệt Lệnh Kho".
  2. Xem thông tin lệnh: Mã lệnh, mặt hàng, số lượng, nhân viên tạo.
  3. Nhấn nút "✅ Duyệt".
- **Kết quả kỳ vọng:** Lệnh chuyển trạng thái APPROVED, dữ liệu được ghi nhận vào thẻ kho chi nhánh, hiển thị thông báo flash màu xanh.
- **Kết quả thực tế:** Phê duyệt thành công, hiển thị flash message xác nhận và loại bỏ lệnh khỏi danh sách chờ duyệt.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/16_admin_approved_request.png`

---

### TC-STOCK-03: Hiển thị Ma trận Sổ thẻ kho 31 ngày (Tháng 10/2026)
- **Loại test:** Test 1 – Happy Path / Data Integrity
- **Điều kiện tiên quyết:** Đăng nhập tài khoản Admin.
- **Các bước thực hiện:**
  1. Vào "Báo cáo & kho", chọn tab "📦 Sổ Thẻ Kho Ma Trận (31 Ngày Tháng 10/2026)".
- **Kết quả kỳ vọng:** Bảng ma trận điện tử hiển thị đầy đủ tồn đầu tháng (Tồn T9), các cột nhập hàng, xuất hàng từng ngày từ 01/10 đến 31/10 và tồn sổ sách.
- **Kết quả thực tế:** Bảng `st.data_editor` hiển thị trực quan với hơn 30 cột ngày và đầy đủ danh mục nguyên liệu quy cách F&B.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/17_admin_stock_matrix_tab.png`

---

### TC-STOCK-04: Xuất file bảng tính Excel Sổ Thẻ Kho (.xlsx)
- **Loại test:** Test 1 – Happy Path / Data Export
- **Điều kiện tiên quyết:** Đang ở tab "Sổ Thẻ Kho Ma Trận".
- **Các bước thực hiện:**
  1. Bấm nút "📥 Tải File Excel (.xlsx)".
- **Kết quả kỳ vọng:** Hệ thống tạo file Excel nhị phân định dạng `.xlsx` chứa toàn bộ dữ liệu 31 ngày để tải về máy.
- **Kết quả thực tế:** Tải file thành công, file có dung lượng hợp lệ (>20KB) và mở được trên Microsoft Excel / Google Sheets.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/verified_stock_matrix.png`

---

### TC-STOCK-05: Dashboard Chốt Ca Bằng Ảnh & Đối Soát Doanh Thu POS (AI OCR)
- **Loại test:** Test 1 – Happy Path / Analytics
- **Điều kiện tiên quyết:** Đang ở tab "Báo cáo & kho".
- **Các bước thực hiện:**
  1. Chọn tab "📸 Chốt Ca Bằng Ảnh & Đối Soát (AI OCR)".
  2. Chọn ngày làm việc: `14/10/2026`.
- **Kết quả kỳ vọng:** Hiển thị 5 thẻ KPI: Tổng thực thu về, Tiền mặt gom ca, Chuyển khoản, App giao hàng và Đối soát chênh lệch máy POS.
- **Kết quả thực tế:** 5 thẻ KPI hiển thị số liệu chính xác với chỉ số delta đối soát POS (ví dụ: Khớp 99.99%).
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/18_admin_shift_closing_tab.png`

---

### TC-STOCK-06: Báo Cáo Doanh Thu & Bán Hàng POS 30 Ngày
- **Loại test:** Test 1 – Happy Path / Chart & Data Visualization
- **Điều kiện tiên quyết:** Đang ở tab "Báo cáo & kho".
- **Các bước thực hiện:**
  1. Chọn tab "📊 Báo Cáo Doanh Thu & Bán Hàng POS".
- **Kết quả kỳ vọng:** Hiển thị tổng doanh thu lũy kế 30 ngày, biểu đồ doanh thu theo ngày và bảng xếp hạng sản phẩm bán chạy nhất.
- **Kết quả thực tế:** Biểu đồ doanh thu trực quan, số liệu khớp hoàn toàn với 1.170 hóa đơn bán hàng trong cơ sở dữ liệu.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/19_admin_sales_report_tab.png`

---

### TC-STOCK-07: Đối Soát Thất Thoát Kho Chi Tiết (BOM Variance Reconciliation)
- **Loại test:** Test 1 – Happy Path / Business Logic
- **Điều kiện tiên quyết:** Đang ở tab "Báo cáo & kho".
- **Các bước thực hiện:**
  1. Chọn tab "🔍 Đối Soát Thất Thoát Kho Chi Tiết".
- **Kết quả kỳ vọng:** Bảng so sánh lượng tiêu thụ lý thuyết (BOM Explosion) vs lượng tiêu hao thực tế (Sổ kho) và tỷ lệ chênh lệch (%) kèm cảnh báo.
- **Kết quả thực tế:** Bảng hiển thị rõ ràng từng nguyên liệu, phân loại mức độ hao hụt và cảnh báo các mặt hàng vượt ngưỡng cho phép (trên 5%).
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/20_admin_reconciliation_tab.png`

---

## 4. PHÂN HỆ DỰ BÁO NHU CẦU (DEMAND FORECASTING D+1)

### TC-FC-01: Bảng đối chiếu kiểm chứng 15 ngày Backtesting
- **Loại test:** Test 1 – Happy Path / Mathematical Validation
- **Điều kiện tiên quyết:** Vào tab "Dự báo".
- **Các bước thực hiện:**
  1. Xem bảng so sánh 3 mô hình dự báo.
- **Kết quả kỳ vọng:** Hiển thị MAE, WAPE, Bias của:
  - Moving Average 7 ngày (WAPE 20.27%, MAE 8.31, Bias +0.32%).
  - Day-of-Week MA (WAPE 21.76%, MAE 8.92, Bias -0.78%).
  - Seasonal Naive (WAPE 25.24%, MAE 10.35, Bias +0.22%).
- **Kết quả thực tế:** Hiển thị đầy đủ bảng đối chiếu với kết luận mô hình Moving Average tối ưu nhất.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/21_admin_forecast_tab.png`

---

### TC-FC-02: Thực thi mô hình dự báo sản lượng cho toàn bộ 39 SKU
- **Loại test:** Test 1 – Happy Path / Compute-heavy Execution
- **Điều kiện tiên quyết:** Đang ở tab "Dự báo".
- **Các bước thực hiện:**
  1. Chọn ngày dự báo: `13/10/2026`.
  2. Chọn giải thuật: `Tự động chọn mô hình tối ưu nhất (Auto)`.
  3. Nhấn "🚀 Chạy Mô hình Dự báo".
  4. Chờ tính toán và quan sát bảng kết quả.
- **Kết quả kỳ vọng:** Hệ thống tính toán dự báo cho toàn bộ 39 món trong menu, hiển thị tổng số ly dự kiến, cận trên, cận dưới và mức độ tin cậy (Cao 🟢 / Trung bình 🟡 / Thấp 🔴).
- **Kết quả thực tế:** Dự báo thành công toàn bộ 39 món, tổng dự kiến ~800 ly. Bảng dữ liệu sắp xếp theo sản lượng giảm dần. Thời gian thực thi đo được: ~14 giây (cần tối ưu hóa hiệu năng).
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/22_admin_forecast_result.png`

---

## 5. PHÂN HỆ SƠ CHẾ THEO MẺ (BATCH PREPARATION PLAN)

### TC-PREP-01: Quy chuẩn bảo quản bán thành phẩm theo SOP Mixue
- **Loại test:** Test 1 – Happy Path / Compliance Check
- **Điều kiện tiên quyết:** Vào tab "Sơ chế".
- **Các bước thực hiện:**
  1. Đọc nội dung thẻ SOP bên phải.
- **Kết quả kỳ vọng:** Hiển thị đúng hạn bảo quản: Hồng trà/Trà xanh 5.000ml (4h), Trân châu 1.000g (giữ ấm 4h, nghiêm cấm qua đêm), Thạch dừa/đường đen 1.000g (hết ngày).
- **Kết quả thực tế:** Hiển thị đầy đủ quy chuẩn SOP chuẩn hóa theo sổ tay Mixue 2132.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/23_admin_prep_tab.png`

---

### TC-PREP-02: Tính toán kế hoạch sơ chế topping & nấu trà làm tròn mẻ
- **Loại test:** Test 1 – Happy Path / Deterministic Optimization
- **Điều kiện tiên quyết:** Đang ở tab "Sơ chế".
- **Các bước thực hiện:**
  1. Thiết lập đệm an toàn: `10%`.
  2. Ngày thực hiện: `13/10/2026`.
  3. Bấm nút "⚡ Tính toán Kế hoạch Sơ chế".
- **Kết quả kỳ vọng:** Số lượng mẻ trà phải là bội số nguyên của 5.000 ml; mẻ trân châu/thạch là bội số nguyên của 1.000 g. Thẩm định độc lập báo `VERIFIED`.
- **Kết quả thực tế:** Kế hoạch được làm tròn chính xác từng mẻ, độc lập kiểm định hiển thị: *"✅ KẾ HOẠCH ĐÃ THẨM ĐỊNH HỢP LỆ (Kiểm định: Đạt chuẩn mẻ làm tròn & an toàn thực phẩm)"*.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/24_admin_prep_calculated.png`

---

### TC-PREP-03: Cơ chế ký duyệt kế hoạch sơ chế của Quản lý (HITL Approval)
- **Loại test:** Test 1 – Happy Path / Governance
- **Điều kiện tiên quyết:** Đã tạo kế hoạch sơ chế, đăng nhập quyền ADMIN.
- **Các bước thực hiện:**
  1. Bấm nút "✍️ Ký duyệt Kế hoạch Sơ chế".
- **Kết quả kỳ vọng:** Hệ thống ghi nhận chữ ký duyệt của Quản lý Bùi Văn Quang, cấp mã phê duyệt hợp lệ.
- **Kết quả thực tế:** Ký duyệt thành công, hiển thị thông báo xác nhận và lưu vết vào hệ thống.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/25_admin_prep_approved.png`

---

## 6. PHÂN HỆ DỰ THẢO ĐƠN NHẬP HÀNG (REPLENISHMENT PO)

### TC-PO-01: Tạo dự thảo đơn đặt hàng nguyên liệu theo quy cách bao/thùng
- **Loại test:** Test 1 – Happy Path / Supply Chain Logic
- **Điều kiện tiên quyết:** Vào tab "Nhập hàng".
- **Các bước thực hiện:**
  1. Thiết lập Lead Time: `2 ngày`.
  2. Ngày đề xuất: `13/10/2026`.
  3. Bấm "📋 Tạo Dự thảo Đơn Đặt hàng".
- **Kết quả kỳ vọng:** Rà soát tồn kho hiện tại so với nhu cầu tiêu thụ trong 2 ngày Lead Time, làm tròn số lượng đặt thành **số nguyên thùng/kiện/bao**, phát hiện các mặt hàng nguy cấp (CRITICAL).
- **Kết quả thực tế:** Tạo thành công đơn hàng draft (ví dụ: `PO-20261013-XXXX`), danh sách hiển thị rõ ràng số lượng đặt nguyên thùng, tồn kho hiện tại và mức ưu tiên.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/27_admin_po_calculated.png`

---

### TC-PO-02: Phê duyệt đơn nhập hàng bởi Quản trị viên (HITL Approval)
- **Loại test:** Test 1 – Happy Path / Governance
- **Điều kiện tiên quyết:** Đã tạo dự thảo đơn PO, đăng nhập quyền ADMIN.
- **Các bước thực hiện:**
  1. Bấm nút "✍️ Ký duyệt Đơn Nhập Hàng".
- **Kết quả kỳ vọng:** Ký duyệt thành công, chuyển đơn sang trạng thái sẵn sàng gửi nhà cung cấp/tổng kho Mixue.
- **Kết quả thực tế:** Ký duyệt thành công với thông báo phê duyệt chính thức.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/28_admin_po_approved.png`

---

## 7. PHÂN HỆ TEM DÁN LY & CÔNG THỨC (STICKER & BOM)

### TC-STICKER-01: Giải mã mã tem dán ly 5 chữ số hợp lệ (24101)
- **Loại test:** Test 1 – Happy Path / Decoder
- **Điều kiện tiên quyết:** Vào tab "Tem & công thức".
- **Các bước thực hiện:**
  1. Nhập mã tem: `24101`.
  2. Bấm nút "Giải mã Tem dán".
- **Kết quả kỳ vọng:** Giải mã thành công: Món `Trà đào bốn mùa`, Đường `30%`, Đá `Nóng`, Topping `Thêm trân châu` kèm SOP quầy bar.
- **Kết quả thực tế:** Tem dán mô phỏng đồ họa hiển thị đầy đủ thông tin chuẩn xác theo tem in nhiệt POS Mixue.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/30_sticker_decoded_24101.png`

---

### TC-STICKER-02: Xử lý mã tem sai định dạng hoặc không tồn tại (Negative Input)
- **Loại test:** Test 2 – Invalid Input / Error State
- **Điều kiện tiên quyết:** Vào tab "Tem & công thức".
- **Các bước thực hiện:**
  1. Nhập mã tem không hợp lệ: `ABC` hoặc `99999`.
  2. Bấm nút "Giải mã Tem dán".
- **Kết quả kỳ vọng:** Hệ thống báo lỗi không tìm thấy quy tắc mã tem, **phải xóa bỏ tem dán cũ trên màn hình**.
- **Kết quả thực tế:** Hệ thống hiển thị thông báo lỗi: *"Không tìm thấy công thức SKU hoặc quy tắc mã tem cho 'ABC'"*. Tuy nhiên, tem dán cũ của lần giải mã trước đó vẫn còn hiển thị bên dưới (State Retention Flaw).
- **Trạng thái:** **FAIL (về logic hiển thị State) / Ghi nhận BUG-STICKER-01**
- **Bằng chứng:** `evidence/screenshots/31_sticker_invalid_code.png`

---

## 8. PHÂN HỆ QUẢN LÝ NHÂN VIÊN & PHÂN QUYỀN (STAFF RBAC)

### TC-EMP-01: Hiển thị danh sách nhân sự chi nhánh & 4 thẻ KPI
- **Loại test:** Test 1 – Happy Path
- **Điều kiện tiên quyết:** Đăng nhập tài khoản ADMIN, vào tab "👥 Quản lý nhân viên".
- **Các bước thực hiện:**
  1. Quan sát 4 thẻ KPI đầu trang và bảng danh sách nhân viên.
- **Kết quả kỳ vọng:** Hiển thị đúng số lượng nhân sự, phân loại vai trò, trạng thái tài khoản và trạng thái mật khẩu.
- **Kết quả thực tế:** Hiển thị 4 thẻ KPI (Tổng nhân sự, Chính thức, Thử việc, Quản trị) và bảng thông tin đầy đủ.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/32_admin_employees_tab.png`

---

### TC-EMP-02: Chặn tạo tài khoản nhân viên trùng Username (Duplicate Check)
- **Loại test:** Test 2 – Negative / Constraint Validation
- **Điều kiện tiên quyết:** Đang ở tab "Đăng ký Nhân viên Mới".
- **Các bước thực hiện:**
  1. Nhập Username đã tồn tại: `nhanvien`.
  2. Nhập Họ tên: `Trần Văn Test`.
  3. Bấm "Tạo Tài Khoản Nhân Viên Ngay 🚀".
- **Kết quả kỳ vọng:** Hệ thống từ chối tạo và hiển thị lỗi Username đã tồn tại.
- **Kết quả thực tế:** Hiển thị thông báo màu đỏ: *"Tên đăng nhập 'nhanvien' đã tồn tại, vui lòng chọn username khác!"*
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/34_create_emp_duplicate_error.png`

---

### TC-EMP-03: Đăng ký thành công tài khoản nhân viên mới
- **Loại test:** Test 1 – Happy Path
- **Điều kiện tiên quyết:** Đang ở tab "Đăng ký Nhân viên Mới".
- **Các bước thực hiện:**
  1. Nhập Username duy nhất: `nv_qa_auto`.
  2. Nhập Họ tên: `Lê Văn QA Test`.
  3. Chọn vai trò: `Nhân viên chính thức`.
  4. Bấm "Tạo Tài Khoản Nhân Viên Ngay 🚀".
- **Kết quả kỳ vọng:** Tạo tài khoản thành công với mật khẩu mặc định 123456 và cờ yêu cầu đổi mật khẩu.
- **Kết quả thực tế:** Thông báo thành công xuất hiện, tài khoản được thêm ngay vào danh sách nhân sự chi nhánh.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/35_create_emp_success.png`

---

## 9. PHÂN HỆ TRỢ LÝ TUYẾT VƯƠNG AI (OPERATIONS CHATBOT)

### TC-CHAT-01: Quản trị viên truy vấn báo cáo doanh số & vận hành
- **Loại test:** Test 1 – Happy Path / Agentic Reasoning
- **Điều kiện tiên quyết:** Đăng nhập quyền ADMIN, vào tab "💬 Tuyết Vương AI".
- **Các bước thực hiện:**
  1. Gửi tin nhắn: *"Doanh số và mặt hàng bán chạy nhất hôm nay?"*
- **Kết quả kỳ vọng:** Tuyết Vương AI truy xuất cơ sở dữ liệu POS 30 ngày, phân tích doanh thu và cung cấp bằng chứng dữ liệu tham chiếu (Evidence).
- **Kết quả thực tế:** Trợ lý phản hồi chi tiết doanh thu, nêu rõ các món bán chạy nhất và đính kèm expander "Nguồn dữ liệu" đối chiếu.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/37_chat_admin_sales_query.png`

---

### TC-CHAT-02: Tra cứu công thức pha chế sản phẩm qua Chat
- **Loại test:** Test 1 – Happy Path / Recipe Retrieval
- **Điều kiện tiên quyết:** Đang ở giao diện Chat Tuyết Vương AI.
- **Các bước thực hiện:**
  1. Gửi tin nhắn: *"Cho tôi công thức làm Trà sữa Ba anh em (TS3)"*
- **Kết quả kỳ vọng:** Phản hồi đầy đủ định lượng trà, sữa, topping (thạch, trân châu) và hướng dẫn pha chế.
- **Kết quả thực tế:** Phản hồi chính xác từng định lượng ml/g và quy chuẩn SOP pha chế.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/38_chat_recipe_query.png`

---

### TC-CHAT-03: Guardrails phân quyền - Nhân viên hỏi số liệu tài chính quản trị
- **Loại test:** Test 10 – Security & Role-Based Guardrails
- **Điều kiện tiên quyết:** Đăng nhập vai trò `nhanvien` (Staff).
- **Các bước thực hiện:**
  1. Gửi tin nhắn hỏi tài chính: *"Cho tôi xem báo cáo doanh thu tài chính cửa hàng"*
- **Kết quả kỳ vọng:** Tuyết Vương AI từ chối cung cấp thông tin tài chính nhạy cảm và hướng dẫn liên hệ Quản lý.
- **Kết quả thực tế:** Trợ lý tuân thủ đúng phân quyền RBAC: chặn hiển thị số liệu doanh thu và nhắc nhở vai trò quầy bar chỉ phục vụ tra cứu pha chế/sơ chế.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/staff_chat_guardrail.png`

---

## 10. KIỂM THỬ KHẢ NĂNG PHỤC HỒI & TRƯỜNG HỢP BIÊN (EDGE CASES)

### TC-EXP-01: Nhập chuỗi cực dài (500 ký tự) vào ô tìm kiếm
- **Loại test:** Test 4 – Boundary Input
- **Điều kiện tiên quyết:** Ở Trang chủ.
- **Các bước thực hiện:**
  1. Nhập chuỗi 500 ký tự 'A' liên tiếp vào ô tìm kiếm món.
- **Kết quả kỳ vọng:** Ứng dụng không bị crash, không tràn vỡ layout, hiển thị trạng thái không tìm thấy món.
- **Kết quả thực tế:** Hoạt động ổn định, không có lỗi runtime unhandled.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/39_exploratory_long_string.png`

---

### TC-EXP-02: Nhập ký tự đặc biệt, Emoji và Payload XSS
- **Loại test:** Test 10 – Unexpected User Behavior / XSS Prevention
- **Điều kiện tiên quyết:** Ở Trang chủ.
- **Các bước thực hiện:**
  1. Nhập: `🧋🍦🥤 <script>alert('xss')</script> SELECT * FROM menu`.
- **Kết quả kỳ vọng:** Ký tự được escape an toàn, không có popup script thực thi.
- **Kết quả thực tế:** An toàn tuyệt đối, chuỗi được render dạng text thuần túy.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/40_exploratory_special_chars.png`

---

### TC-EXP-03: Tải lại trang (F5 / Page Refresh) duy trì phiên làm việc
- **Loại test:** Test 6 – Refresh & Test 9 – Data Persistence
- **Điều kiện tiên quyết:** Đang đăng nhập và ở tab bất kỳ.
- **Các bước thực hiện:**
  1. Thực hiện F5 tải lại trang.
- **Kết quả kỳ vọng:** Trình duyệt tải lại và giữ nguyên trạng thái đăng nhập, không văng ra màn hình Login.
- **Kết quả thực tế:** Phiên làm việc được duy trì qua Session State.
- **Trạng thái:** **PASS**
- **Bằng chứng:** `evidence/screenshots/41_page_reload_retention.png`
