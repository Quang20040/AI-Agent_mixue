# 08 – FORMAL BUG REPORT (BÁO CÁO TOÀN DIỆN CÁC LỖI PHÁT HIỆN)

> **Dự án:** BeverageOps AI — Quản trị Điều phối Vận hành Chi nhánh Mixue 39 Tôn Quang Phiệt  
> **Người lập báo cáo:** Senior Software QA Engineer & Defect Manager  
> **Môi trường:** Local (`http://localhost:8501`)  
> **Tiêu chuẩn lập báo cáo:** IEEE 829 Standard for Software Test Documentation  

---

## BẢNG TỔNG HỢP DANH SÁCH LỖI (DEFECT MATRIX)

| BUG ID | TIÊU ĐỀ LỖI | PHÂN HỆ | PRIORITY | SEVERITY | TRẠNG THÁI |
|---|---|---|:---:|:---:|:---:|
| **BUG-STICKER-01** | Tem dán ly cũ không bị xóa khi giải mã mã tem lỗi | Tem & công thức | **P2** | Medium | Open |
| **BUG-STOCK-01** | Sổ thẻ kho ma trận cho phép âm kho mà không có cảnh báo đỏ | Báo cáo & kho | **P2** | Medium | Open |
| **BUG-STOCK-02** | Sửa ô ma trận kho bị mất dữ liệu nếu chuyển tab mà quên bấm Lưu | Báo cáo & kho | **P2** | Medium | Open |
| **BUG-STOCK-03** | Thiếu cơ chế phát hiện gửi trùng phiếu kho trong thời gian ngắn | Báo cáo & kho | **P2** | Medium | Open |
| **BUG-PERF-01** | Thời gian chạy mô hình dự báo D+1 mất 14s thiếu thanh tiến trình % | Dự báo | **P2** | Medium | Open |
| **BUG-RESP-01** | Thanh điều hướng 8 tabs bị ngắt thành nhiều dòng trên di động | Responsive | **P2** | Medium | Open |
| **BUG-NAV-01** | Nút Đăng xuất bị giấu sâu trong Sidebar thu gọn khó tìm | UI/UX | **P2** | Medium | Open |
| **BUG-AUTH-01** | Thông báo lỗi đăng nhập khi để trống form báo sai mật khẩu | Xác thực | **P3** | Low | Open |
| **BUG-AUTH-02** | Thiếu cấu hình tự động hết hạn phiên (Auto Session Idle Timeout) | Bảo mật | **P2** | Medium | Open |
| **BUG-STOCK-04** | Form xuất kho thiếu cảnh báo khi nhập số lượng lớn bất thường | Báo cáo & kho | **P3** | Low | Open |

---

## CHI TIẾT TỪNG LỖI (FULL BUG SPECIFICATIONS)

---

### BUG ID: BUG-STICKER-01
- **TITLE:** Tem dán ly đồ họa cũ của lần tra cứu trước không bị xóa khi người dùng nhập mã tem không hợp lệ
- **MODULE:** Tem in nhãn & Công thức (BOM)
- **PRIORITY:** P2 (Medium)
- **SEVERITY:** Medium
- **URL:** `http://localhost:8501` (Section: Tem & công thức)
- **VIEWPORT:** All Viewports (Desktop 1920x1080, Mobile 375x667)
- **PRECONDITIONS:** Đã đăng nhập vào hệ thống, đang ở tab "Tem & công thức".
- **STEPS TO REPRODUCE:**
  1. Nhập mã tem hợp lệ: `24101` và bấm "Giải mã Tem dán".
  2. Quan sát: Khung tem dán đồ họa màu vàng-trắng hiển thị món Trà đào, 30% đường, nóng, thêm trân châu.
  3. Nhập mã tem lỗi hoặc không tồn tại: `ABC`.
  4. Bấm nút "Giải mã Tem dán".
  5. Quan sát màn hình.
- **EXPECTED RESULT:** Hệ thống báo lỗi *"Không tìm thấy công thức..."* và **phải xóa bỏ hoặc ẩn khung tem dán cũ** bên dưới để tránh nhầm lẫn.
- **ACTUAL RESULT:** Hệ thống hiển thị thông báo lỗi màu đỏ phía trên, nhưng chiếc tem dán của mã `24101` bên dưới vẫn giữ nguyên trạng thái hiển thị.
- **EVIDENCE:** `evidence/screenshots/31_sticker_invalid_code.png`
- **FREQUENCY:** 100% (Luôn tái hiện)
- **USER IMPACT:** Nhân viên quầy bar trong giờ cao điểm nhìn lướt có thể thấy tem đồ họa cũ và pha nhầm đồ cho khách, gây lãng phí nguyên liệu và khiếu nại chất lượng.
- **SUSPECTED ROOT CAUSE:** Trong `app.py`, khi giải mã thất bại (`status != "SUCCESS"`), biến `st.session_state["sticker_result"]` không được xóa bỏ bằng `pop()`.
- **RECOMMENDED FIX:**
  ```python
  if res["status"] == "SUCCESS":
      st.session_state["sticker_result"] = res
  else:
      st.session_state.pop("sticker_result", None)
      st.error(res["message"])
  ```
- **RETEST CRITERIA:** Nhập mã hợp lệ để hiện tem, sau đó nhập mã lỗi; tem cũ phải biến mất hoàn toàn và chỉ còn thông báo lỗi.

---

### BUG ID: BUG-STOCK-01
- **TITLE:** Sổ thẻ kho ma trận cho phép tồn kho sổ sách hiển thị giá trị âm mà không có cảnh báo đỏ trực quan
- **MODULE:** Báo cáo & Kho $\rightarrow$ Sổ Thẻ Kho Ma Trận 31 Ngày
- **PRIORITY:** P2 (Medium)
- **SEVERITY:** Medium
- **URL:** `http://localhost:8501` (Section: Báo cáo & kho $\rightarrow$ Tab Ma trận)
- **VIEWPORT:** Desktop 1920x1080 / Laptop 1366x768
- **PRECONDITIONS:** Đăng nhập quyền ADMIN (Quản lý hoặc Chủ quán).
- **STEPS TO REPRODUCE:**
  1. Vào tab "Sổ Thẻ Kho Ma Trận".
  2. Tạo một lệnh xuất kho với số lượng lớn hơn tồn kho hiện tại (hoặc dùng chức năng sửa ô ngày).
  3. Quan sát cột "Tồn sổ sách" trên bảng ma trận.
- **EXPECTED RESULT:** Ô tồn kho khi bị âm phải được tô màu đỏ cảnh báo (Warning Badge / Highlight) để Quản lý phát hiện ngay việc âm kho bất thường.
- **ACTUAL RESULT:** Ô hiển thị giá trị âm (ví dụ: `-2.0`) nhưng với màu chữ đen thông thường, dễ bị bỏ sót trong bảng dữ liệu lớn hơn 40 cột.
- **EVIDENCE:** `evidence/screenshots/17_admin_stock_matrix_tab.png`
- **FREQUENCY:** 100%
- **USER IMPACT:** Chủ cửa hàng và kế toán không nhận biết được tình trạng âm kho để kịp thời đối soát hóa đơn nhập chưa ghi sổ.
- **SUSPECTED ROOT CAUSE:** `st.data_editor` chưa áp dụng `column_config` với điều kiện định dạng có điều kiện (Conditional Formatting) cho các số $< 0$.
- **RECOMMENDED FIX:** Sử dụng `st.column_config.NumberColumn` hoặc hiển thị cảnh báo Banner khi có ít nhất 1 mặt hàng âm kho.
- **RETEST CRITERIA:** Khi một mặt hàng có Tồn sổ sách $< 0$, xuất hiện cảnh báo rõ ràng trên đầu bảng ma trận.

---

### BUG ID: BUG-STOCK-02
- **TITLE:** Dữ liệu chỉnh sửa trực tiếp trên ma trận thẻ kho bị mất nếu người dùng chuyển tab mà quên bấm nút Lưu
- **MODULE:** Báo cáo & Kho $\rightarrow$ Sổ Thẻ Kho Ma Trận 31 Ngày
- **PRIORITY:** P2 (Medium)
- **SEVERITY:** Medium
- **URL:** `http://localhost:8501` (Section: Báo cáo & kho)
- **VIEWPORT:** Desktop 1920x1080
- **PRECONDITIONS:** Đăng nhập quyền ADMIN.
- **STEPS TO REPRODUCE:**
  1. Vào tab Ma trận thẻ kho.
  2. Bấm đúp vào một ô ngày (ví dụ: Nhập 12/10) và sửa giá trị từ `5.0` thành `8.0`.
  3. Không bấm nút "💾 Lưu Các Ô Đã Sửa Vào Sổ Kho".
  4. Chuyển sang tab khác (ví dụ: "Dự báo" hoặc tab "Chốt Ca Bằng Ảnh").
  5. Quay lại tab Ma trận thẻ kho.
- **EXPECTED RESULT:** Hệ thống cảnh báo "Bạn có dữ liệu chưa lưu!" hoặc tự động lưu tạm vào session state.
- **ACTUAL RESULT:** Streamlit rerun làm mất toàn bộ giá trị vừa gõ, ô số liệu quay về giá trị ban đầu mà không có bất kỳ thông báo cảnh báo nào.
- **EVIDENCE:** `evidence/screenshots/verified_stock_matrix.png`
- **FREQUENCY:** 100%
- **USER IMPACT:** Người quản lý mất công gõ sửa nhiều ô kiểm kê nhưng bị mất trắng dữ liệu chỉ vì lỡ chuyển tab.
- **SUSPECTED ROOT CAUSE:** `st.data_editor` lưu trữ trạng thái chỉnh sửa trong key component nội bộ; khi component bị unmount do chuyển tab, trạng thái chỉnh sửa chưa commit bị hủy bỏ.
- **RECOMMENDED FIX:** Thêm nhắc nhở hoặc tự động lưu giá trị `edited_rows` vào `st.session_state` trước khi điều hướng.
- **RETEST CRITERIA:** Chỉnh sửa ô, chuyển tab rồi quay lại; dữ liệu đã sửa phải được giữ nguyên hoặc có cảnh báo xác nhận trước khi rời trang.

---

### BUG ID: BUG-STOCK-03
- **TITLE:** Thiếu cơ chế kiểm tra gửi trùng phiếu đề xuất kho (Duplicate Request Detection)
- **MODULE:** Báo cáo & Kho $\rightarrow$ Phiếu Đề Xuất Lệnh Kho
- **PRIORITY:** P2 (Medium)
- **SEVERITY:** Medium
- **URL:** `http://localhost:8501` (Section: Báo cáo & kho)
- **VIEWPORT:** Mobile & Desktop
- **PRECONDITIONS:** Đăng nhập tài khoản Nhân viên (`nhanvien`).
- **STEPS TO REPRODUCE:**
  1. Vào form tạo phiếu đề xuất kho quầy bar.
  2. Chọn `Trà đen (Thùng 20 gói)`, xuất `2.0 thùng`.
  3. Bấm "Gửi Đề Xuất Lệnh Kho Chờ Quản Lý Duyệt".
  4. Trong vòng 10 giây tiếp theo, gửi tiếp một phiếu giống hệt.
- **EXPECTED RESULT:** Hệ thống phát hiện phiếu trùng lặp và hỏi xác nhận: *"Bạn vừa tạo một đề xuất xuất 2.0 thùng Trà đen cách đây vài giây. Bạn có chắc muốn tạo thêm một lệnh tương tự?"*.
- **ACTUAL RESULT:** Hệ thống tạo ngay lệnh thứ 2 thành công mà không có bất kỳ cảnh báo nào.
- **EVIDENCE:** `evidence/screenshots/07_staff_stock_request_created.png`
- **FREQUENCY:** 100%
- **USER IMPACT:** Nhân viên thao tác nhầm hoặc click đúp tạo 2 lệnh trùng lặp, gây nguy cơ Quản lý duyệt trùng và trừ kho 2 lần.
- **SUSPECTED ROOT CAUSE:** Hàm `create_stock_request()` trong `daily_stock_service.py` chưa kiểm tra bản ghi gần nhất có cùng mặt hàng, loại thao tác và thời gian phát sinh trong vòng 60 giây.
- **RECOMMENDED FIX:** Thêm kiểm tra thời gian tối thiểu giữa 2 lệnh cùng loại hoặc gắn cờ xác nhận `confirm_duplicate`.
- **RETEST CRITERIA:** Gửi 2 lệnh giống hệt nhau liên tiếp trong vòng 1 phút phải xuất hiện cảnh báo trùng lặp.

---

### BUG ID: BUG-PERF-01
- **TITLE:** Thời gian chạy mô hình dự báo D+1 kéo dài 14 giây nhưng chỉ có spinner đơn điệu, thiếu thanh tiến trình phần trăm
- **MODULE:** Dự báo Nhu cầu (Forecasting D+1)
- **PRIORITY:** P2 (Medium)
- **SEVERITY:** Medium
- **URL:** `http://localhost:8501` (Section: Dự báo)
- **VIEWPORT:** All Viewports
- **PRECONDITIONS:** Đăng nhập quyền ADMIN, vào tab "Dự báo".
- **STEPS TO REPRODUCE:**
  1. Chọn giải thuật "Auto" hoặc "Moving Average".
  2. Bấm "🚀 Chạy Mô hình Dự báo".
  3. Bấm đồng hồ đo thời gian chờ kết quả.
- **EXPECTED RESULT:** Có thanh tiến trình `st.progress()` hiển thị tiến độ % (ví dụ: đã dự báo được 15/39 món), thời gian phản hồi lý tưởng dưới 5 giây.
- **ACTUAL RESULT:** Chỉ có một biểu tượng spinner xoay và thông báo tĩnh kéo dài suốt 14 giây, tạo cảm giác ứng dụng bị treo.
- **EVIDENCE:** `evidence/screenshots/22_admin_forecast_result.png` và log `task-179.log`
- **FREQUENCY:** 100%
- **USER IMPACT:** Trải nghiệm người dùng giảm sút; người dùng dễ bấm refresh hoặc tắt trang giữa chừng vì nghĩ hệ thống bị treo.
- **SUSPECTED ROOT CAUSE:** Thuật toán dự báo tính toán lặp tuần tự cho từng SKU trong cơ sở dữ liệu SQLite mà chưa sử dụng xử lý vector hóa (Vectorized Pandas) hoặc chưa hiển thị progress callback.
- **RECOMMENDED FIX:**
  1. Thêm `st.progress(i / total_skus)` trong vòng lặp dự báo.
  2. Lưu cache kết quả dự báo trong ngày (`@st.cache_data(ttl=3600)`).
- **RETEST CRITERIA:** Bấm chạy dự báo có thanh tiến trình cập nhật từng món và thời gian chờ có phản hồi trực quan liên tục.

---

### BUG ID: BUG-RESP-01
- **TITLE:** Thanh điều hướng 8 tabs bị ngắt thành nhiều hàng trên màn hình di động nhỏ (320px - 430px) chiếm nhiều diện tích
- **MODULE:** Responsive & Layout Navigation
- **PRIORITY:** P2 (Medium)
- **SEVERITY:** Medium
- **URL:** `http://localhost:8501`
- **VIEWPORT:** Small Mobile 320px, Mobile 375px, Large Mobile 430px
- **PRECONDITIONS:** Mở ứng dụng trên viewport di động.
- **STEPS TO REPRODUCE:**
  1. Mở công cụ Developer Tools, chọn kích thước 375x667.
  2. Đăng nhập tài khoản Quản lý (Admin).
  3. Quan sát thanh điều hướng radio phía trên trang.
- **EXPECTED RESULT:** Thanh điều hướng co gọn thành Menu Dropdown hoặc Drawer trượt ngang.
- **ACTUAL RESULT:** 8 nút radio bị bẻ dòng thành 4-5 hàng, chiếm gần 40% chiều cao màn hình di động, đẩy nội dung làm việc xuống rất sâu.
- **EVIDENCE:** `evidence/screenshots/resp_375_mobile_home.png`
- **FREQUENCY:** 100%
- **USER IMPACT:** Nhân viên thao tác trên điện thoại bị hạn chế tầm nhìn, phải cuộn trang nhiều lần.
- **SUSPECTED ROOT CAUSE:** `st.radio(horizontal=True)` trên Streamlit mobile tự động ngắt dòng nếu vượt quá chiều rộng container mà không có CSS scrollbar ngang.
- **RECOMMENDED FIX:** Áp dụng CSS media query cho thiết bị di động: `flex-wrap: nowrap; overflow-x: auto;` hoặc chuyển sang `st.selectbox` trên màn hình nhỏ.
- **RETEST CRITERIA:** Trên màn hình 375px, thanh điều hướng chỉ chiếm 1 hàng duy nhất và cho phép vuốt ngang hoặc chọn dạng dropdown.

---

### BUG ID: BUG-NAV-01
- **TITLE:** Nút Đăng xuất bị giấu sâu trong Sidebar thu gọn khiến người dùng khó tìm
- **MODULE:** UI/UX & Navigation Architecture
- **PRIORITY:** P2 (Medium)
- **SEVERITY:** Medium
- **URL:** `http://localhost:8501`
- **VIEWPORT:** All Viewports
- **PRECONDITIONS:** Đã đăng nhập vào hệ thống.
- **STEPS TO REPRODUCE:**
  1. Đăng nhập vào hệ thống.
  2. Quan sát màn hình chính: `initial_sidebar_state="collapsed"` khiến sidebar bị đóng.
  3. Tìm kiếm nút Đăng xuất trên màn hình.
- **EXPECTED RESULT:** Nút Đăng xuất hiển thị ở vị trí dễ thấy (ví dụ: góc trên cùng bên phải màn hình làm việc).
- **ACTUAL RESULT:** Không có nút Đăng xuất nào trên màn hình chính; người dùng buộc phải biết bấm vào icon mũi tên nhỏ `>>` ở góc trên cùng bên trái để mở sidebar mới thấy nút Đăng xuất.
- **EVIDENCE:** `evidence/screenshots/09_admin_dashboard_home.png`
- **FREQUENCY:** 100%
- **USER IMPACT:** Người dùng mới lúng túng không biết làm cách nào để đăng xuất tài khoản để chuyển ca cho người khác.
- **SUSPECTED ROOT CAUSE:** Nút đăng xuất chỉ được đặt duy nhất trong khối `with st.sidebar:`.
- **RECOMMENDED FIX:** Bổ sung nút Đăng xuất nhanh hoặc Menu hồ sơ tài khoản ở góc trên bên phải thanh Header.
- **RETEST CRITERIA:** Người dùng có thể đăng xuất ngay tại màn hình chính với tối đa 1 cú nhấp chuột mà không cần mở sidebar.

---

### BUG ID: BUG-AUTH-01
- **TITLE:** Thông báo lỗi đăng nhập khi để trống form báo sai mật khẩu thay vì yêu cầu nhập đầy đủ thông tin
- **MODULE:** Xác thực & Màn hình Đăng nhập
- **PRIORITY:** P3 (Low)
- **SEVERITY:** Low
- **URL:** `http://localhost:8501`
- **VIEWPORT:** All Viewports
- **PRECONDITIONS:** Đang ở màn hình đăng nhập.
- **STEPS TO REPRODUCE:**
  1. Không nhập bất kỳ ký tự nào vào ô Username và Password.
  2. Nhấn nút "Đăng nhập vào Hệ thống 🚀".
- **EXPECTED RESULT:** Thông báo: *"Vui lòng nhập Tên đăng nhập và Mật khẩu!"*.
- **ACTUAL RESULT:** Thông báo: *"Tên đăng nhập hoặc mật khẩu không chính xác! Vui lòng thử lại."*.
- **EVIDENCE:** `evidence/screenshots/02_login_empty_submit.png`
- **FREQUENCY:** 100%
- **USER IMPACT:** Gây hiểu nhầm về mặt trải nghiệm người dùng (UX confusion).
- **SUSPECTED ROOT CAUSE:** `render_login_screen()` gọi `verify_user("", "")` và trả về `None`, sau đó hiển thị thông báo lỗi mặc định.
- **RECOMMENDED FIX:** Kiểm tra `if not username or not password:` trước khi gọi `verify_user()`.
- **RETEST CRITERIA:** Bấm đăng nhập khi form rỗng hiển thị thông báo yêu cầu điền thông tin.

---

### BUG ID: BUG-AUTH-02
- **TITLE:** Thiếu cơ chế tự động khóa phiên làm việc khi nhân viên không thao tác (Session Idle Timeout)
- **MODULE:** Bảo mật & Quản lý Phiên (Session Security)
- **PRIORITY:** P2 (Medium)
- **SEVERITY:** Medium
- **URL:** `http://localhost:8501`
- **VIEWPORT:** All Viewports
- **PRECONDITIONS:** Đăng nhập tài khoản Quản lý hoặc Chủ quán.
- **STEPS TO REPRODUCE:**
  1. Đăng nhập tài khoản Admin.
  2. Để trình duyệt mở và không thao tác trong hơn 30 phút.
  3. Thử thực hiện lại thao tác (ví dụ: Duyệt lệnh kho, Xóa tài khoản).
- **EXPECTED RESULT:** Hệ thống tự động khóa phiên làm việc (Session Expired) và yêu cầu đăng nhập lại để đảm bảo an toàn quầy thu ngân.
- **ACTUAL RESULT:** Phiên làm việc vẫn duy trì vĩnh viễn cho đến khi đóng hẳn trình duyệt hoặc tắt server.
- **EVIDENCE:** `evidence/screenshots/41_page_reload_retention.png`
- **FREQUENCY:** 100%
- **USER IMPACT:** Nguy cơ nhân viên ca sau hoặc người ngoài quầy thao tác trên tài khoản Quản trị khi người quản lý rời khỏi vị trí mà quên đăng xuất.
- **SUSPECTED ROOT CAUSE:** Streamlit chưa tích hợp middleware kiểm tra thời gian `last_active_timestamp` trong Session State.
- **RECOMMENDED FIX:** Lưu `st.session_state["last_active"] = time.time()` và kiểm tra nếu vượt quá 1.800 giây (30 phút) thì tự động `pop()` session và yêu cầu đăng nhập lại.
- **RETEST CRITERIA:** Sau 30 phút không có thao tác, bấm bất kỳ nút nào hệ thống sẽ thông báo phiên đã hết hạn và yêu cầu đăng nhập lại.

---

### BUG ID: BUG-STOCK-04
- **TITLE:** Form xuất kho tại quầy bar cho phép nhập số lượng lớn bất thường (lên đến 50 thùng) mà không có cảnh báo xác nhận
- **MODULE:** Báo cáo & Kho $\rightarrow$ Phiếu Đề Xuất Lệnh Kho
- **PRIORITY:** P3 (Low)
- **SEVERITY:** Low
- **URL:** `http://localhost:8501`
- **VIEWPORT:** All Viewports
- **PRECONDITIONS:** Đăng nhập tài khoản Nhân viên (`nhanvien`).
- **STEPS TO REPRODUCE:**
  1. Vào form tạo phiếu đề xuất kho quầy bar.
  2. Nhập số lượng: `50.0` thùng (ví dụ: nhân viên gõ nhầm 5.0 thành 50.0).
  3. Bấm "Gửi Đề Xuất Lệnh Kho Chờ Quản Lý Duyệt".
- **EXPECTED RESULT:** Với số lượng vượt quá mức tiêu thụ thông thường của 1 ca (ví dụ: $> 10$ thùng), hệ thống hiển thị cảnh báo vàng: *"Số lượng xuất kho lớn bất thường (50 thùng). Bạn có chắc chắn con số này là chính xác?"*.
- **ACTUAL RESULT:** Hệ thống chấp nhận số lượng 50.0 thùng ngay lập tức mà không có ngưỡng cảnh báo trần.
- **EVIDENCE:** `evidence/screenshots/06_staff_baocao_kho.png`
- **FREQUENCY:** 100%
- **USER IMPACT:** Nhân viên gõ nhầm số liệu vô tình gửi lệnh bất hợp lý lên Quản lý.
- **SUSPECTED ROOT CAUSE:** Form quy định `max_value=50.0` nhưng không có ngưỡng cảnh báo động dựa trên mức tiêu thụ trung bình ca.
- **RECOMMENDED FIX:** Bổ sung logic cảnh báo khi số lượng vượt ngưỡng 10 thùng/kiện.
- **RETEST CRITERIA:** Nhập $> 10$ thùng xuất hiện hộp thoại xác nhận số lượng lớn.
