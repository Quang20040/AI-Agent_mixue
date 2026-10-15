# 05 – UI/UX AUDIT & USABILITY REPORT (BÁO CÁO ĐÁNH GIÁ GIAO DIỆN & TRẢI NGHIỆM)

> **Dự án:** BeverageOps AI — Quản trị Điều phối Vận hành Chi nhánh Mixue 39 Tôn Quang Phiệt  
> **Chuyên môn đánh giá:** Senior UI/UX Auditor & Ergonomics Specialist  
> **Tiêu chuẩn đối chiếu:** Nielsen Norman Group (NN/g) Usability Heuristics & Material Design 3  

---

## 1. ĐÁNH GIÁ TỔNG QUAN VỀ THƯƠNG HIỆU & THỊ GIÁC (VISUAL & BRANDING)

### 1.1. Điểm xuất sắc (Strengths)
1. **Bản sắc thương hiệu Mixue Tuyết Vương (Snow King / 雪王) rất đậm nét:** Tông màu đỏ Mixue (`#e60012`) kết hợp trắng sữa và vàng nhạt tạo cảm giác ấm áp, tươi vui, đúng với khẩu hiệu *"Thêm ngọt ngào. Thêm niềm vui"*.
2. **Hiệu ứng đồ họa hiện đại:** Thẻ sản phẩm có hiệu ứng nghiêng 3D (GSAP 3D tilt) bám theo con trỏ chuột, linh vật Tuyết Vương sinh động với các trạng thái (đang nghĩ, vẫy tay, chào mừng).
3. **Typography & Bản địa hóa 100% tiếng Việt:** Bộ font sans-serif dễ đọc, thuật ngữ F&B chuẩn xác (khui thùng, mẻ nấu, đệm an toàn, chốt ca, đối soát POS, tem ly).
4. **Nút hỗ trợ người dùng nhạy cảm chuyển động:** Có nút *"Tạm dừng hiệu ứng"* ngay đầu trang chủ, tuân thủ tiêu chuẩn Accessibility (WCAG 2.1 - Animation from interactions).

---

## 2. PHÂN TÍCH CÁC VẤN ĐỀ UI/UX PHÁT HIỆN (DETAILED FINDINGS)

### UIUX-01: Thông báo lỗi đăng nhập khi để trống form gây hiểu nhầm (Misleading Error Message)
- **Vị trí:** Màn hình Đăng nhập (`render_login_screen()`).
- **Hiện trạng:** Khi người dùng chưa nhập bất kỳ ký tự nào vào ô Username và Password mà bấm nút "Đăng nhập vào Hệ thống", hệ thống hiển thị cảnh báo đỏ:
  > *"Tên đăng nhập hoặc mật khẩu không chính xác! Vui lòng thử lại."*
- **Vấn đề trải nghiệm:** Người dùng cảm thấy bối rối vì họ chưa gõ mật khẩu nhưng lại bị báo là "mật khẩu không chính xác". Điều này vi phạm nguyên tắc Heuristic #9: *"Help users recognize, diagnose, and recover from errors"*.
- **Đề xuất cải tiến:**
  - Nếu Username hoặc Password để trống, hiển thị: *"Vui lòng nhập đầy đủ Tên đăng nhập và Mật khẩu!"*.
  - Chỉ hiển thị *"Tên đăng nhập hoặc mật khẩu không chính xác"* khi người dùng đã nhập thông tin nhưng không khớp cơ sở dữ liệu.
- **Mức độ:** **P3 – Low / UX Weakness**

---

### UIUX-02: Bảng Ma trận Sổ kho 31 ngày có quá nhiều cột gây ngợp thị giác (Information Overload)
- **Vị trí:** Tab "Báo cáo & kho" $\rightarrow$ "Sổ Thẻ Kho Ma Trận (31 Ngày Tháng 10/2026)".
- **Hiện trạng:** Mặc định bảng hiển thị toàn bộ 31 ngày (hơn 40 cột ngang). Trên màn hình laptop 1366x768 hoặc màn hình nhỏ, người dùng phải cuộn ngang rất dài để tìm ngày hiện tại.
- **Vấn đề trải nghiệm:** Mặc dù hệ thống đã có bộ lọc theo Tuần (Tuần 1, 2, 3, 4, 5), nhưng mặc định lại chọn xem "Toàn bộ Tháng 10/2026", khiến bảng dữ liệu hiển thị dày đặc, các ô số bị thu nhỏ khó đọc.
- **Đề xuất cải tiến:**
  - Mặc định khi mở tab, tự động chọn tuần chứa ngày hiện tại (ví dụ: ngày 15/10 $\rightarrow$ tự động mở `Tuần 3 (12/10 - 18/10)`).
  - Ghim cố định (Freeze column) cột "STT" và "Tên mặt hàng (Quy cách)" bên trái khi cuộn ngang.
- **Mức độ:** **P2 – Medium / Usability**

---

### UIUX-03: Thiếu thanh tiến trình (Progress Indicator) khi chạy mô hình dự báo
- **Vị trí:** Tab "Dự báo" $\rightarrow$ Nút "🚀 Chạy Mô hình Dự báo".
- **Hiện trạng:** Khi Quản lý bấm nút chạy dự báo, hệ thống hiển thị một spinner nhỏ: *"Đang tính toán dự báo sản lượng cho toàn bộ 39 món thực đơn..."* và kéo dài trong **~14 giây**.
- **Vấn đề trải nghiệm:** 14 giây là khoảng thời gian đủ lâu để người dùng cảm thấy sốt ruột và tự hỏi liệu hệ thống có bị đơ/treo hay không. Spinner đơn điệu không cho biết tiến trình đã hoàn thành bao nhiêu % (ví dụ: đã dự báo được 15/39 món).
- **Đề xuất cải tiến:**
  - Sử dụng `st.progress()` kèm thanh đếm: *"Đang tính toán món 12/39 (Trà sữa trân châu)..."*.
  - Thêm cơ chế lưu bộ nhớ đệm (Cache forecast results) trong ngày để khi bấm lại không phải tính toán lại từ đầu.
- **Mức độ:** **P2 – Medium / Performance UX**

---

### UIUX-04: Tem dán cũ không bị xóa khi nhập mã tem không hợp lệ (State Residual Flaw)
- **Vị trí:** Tab "Tem & công thức" $\rightarrow$ "Giải mã Mã Tem In trên Ly".
- **Hiện trạng:** Khi người dùng vừa giải mã thành công một mã tem (ví dụ: `24101`), khung tem đồ họa hiển thị đẹp mắt. Sau đó, nếu nhập mã lỗi (ví dụ: `ABC`), hệ thống hiện thông báo đỏ *"Không tìm thấy công thức..."* ở trên, **nhưng chiếc tem dán 24101 bên dưới vẫn giữ nguyên**.
- **Vấn đề trải nghiệm:** Giao diện mâu thuẫn: Phía trên báo lỗi không tìm thấy tem, phía dưới lại vẫn có tem dán chi tiết. Barista đang thao tác nhanh có thể nhìn nhầm tem cũ bên dưới và pha nhầm đồ cho khách.
- **Đề xuất cải tiến:**
  - Khi giải mã thất bại (`status != "SUCCESS"`), phải thực hiện `st.session_state.pop("sticker_result", None)` để ẩn hoàn toàn khung tem cũ.
- **Mức độ:** **P2 – Medium / State Bug**

---

### UIUX-05: Chuyển tab từ Popup công thức sang Chatbot Tuyết Vương quá nhanh
- **Vị trí:** Tab "Trang chủ" $\rightarrow$ Modal "Xem công thức" $\rightarrow$ Nút "💬 Hỏi Tuyết Vương ở màn hình Chat".
- **Hiện trạng:** Khi bấm nút, modal đóng lại và màn hình nhảy ngay sang tab "💬 Tuyết Vương AI" với câu hỏi công thức được gửi đi.
- **Vấn đề trải nghiệm:** Hành vi điều hướng rất tiện lợi, tuy nhiên người dùng mới có thể bị giật mình vì chuyển đổi ngữ cảnh đột ngột (Context Switch).
- **Đề xuất cải tiến:**
  - Hiển thị một Toast nhỏ thông báo: *"Đang chuyển câu hỏi về công thức sang Trợ lý Tuyết Vương AI..."* để người dùng kịp định hình màn hình mới.
- **Mức độ:** **P3 – Low / Minor Polish**

---

### UIUX-06: Sidebar thu gọn mặc định (Collapsed Sidebar) khó nhận biết trên một số màn hình
- **Vị trí:** Sidebar bên trái trên toàn hệ thống.
- **Hiện trạng:** `initial_sidebar_state="collapsed"` khiến nút mở sidebar chỉ là một mũi tên nhỏ `>>` ở góc trên cùng bên trái màn hình.
- **Vấn đề trải nghiệm:** Nút "🚪 Đăng xuất khỏi Hệ thống" và thông tin chi nhánh nằm hoàn toàn trong sidebar. Khi sidebar bị thu gọn, người dùng không thấy nút Đăng xuất ở đâu và tưởng rằng hệ thống không có chức năng đăng xuất.
- **Đề xuất cải tiến:**
  - Thêm nút Đăng xuất nhanh hoặc Avatar người dùng ở góc trên bên phải (Top-right Header Bar) bên cạnh thanh điều hướng để người dùng thao tác tiện lợi hơn mà không cần mở sidebar.
- **Mức độ:** **P2 – Medium / Information Architecture**

---

## 3. BẢNG TỔNG HỢP XẾP HẠNG VẤN ĐỀ UI/UX

| Mã lỗi | Hạng mục | Vấn đề phát hiện | Heuristic vi phạm | Ưu tiên |
|---|---|---|---|---|
| **UIUX-01** | Form Login | Thông báo lỗi không chính xác khi để trống | Error Recovery (#9) | **P3** |
| **UIUX-02** | Thẻ kho | Bảng 31 ngày quá tải thông tin, thiếu freeze cột | Aesthetic & Minimalist (#8) | **P2** |
| **UIUX-03** | Dự báo | Chờ 14s không có thanh tiến trình % | Visibility of System Status (#1) | **P2** |
| **UIUX-04** | Tem ly | Tem đồ họa cũ không bị xóa khi gặp mã lỗi | Consistency & Standards (#4) | **P2** |
| **UIUX-05** | Modal | Chuyển ngữ cảnh sang Chat quá nhanh | Flexibility & Efficiency (#7) | **P3** |
| **UIUX-06** | Navigation | Nút Đăng xuất bị giấu sâu trong Collapsed Sidebar | Recognition rather than Recall (#6) | **P2** |
