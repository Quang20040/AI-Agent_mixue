# BÁO CÁO KIỂM TOÁN GIAO DIỆN & TRẢI NGHIỆM NGƯỜI DÙNG (FRONTEND AUDIT)
## HỆ THỐNG: BEVERAGE-OPS AI — CHI NHÁNH MIXUE 39 TÔN QUANG PHIỆT
**Mã tài liệu:** `WB-AUDIT-05-FE`  
**Phiên bản:** 2.0.0-PROD-AUDIT  
**Đối tượng:** Đánh giá vòng đời Streamlit, quản lý trạng thái (`st.session_state`), CSS, JavaScript components và bảng tính `st.data_editor`

---

## 1. PHÂN TÍCH VÒNG ĐỜI VÀ MÔ HÌNH STREAMLIT RUNTIME

Hệ thống sử dụng **Streamlit v1.40+** làm nền tảng giao diện duy nhất. Mặc dù Streamlit giúp xây dựng nhanh giao diện dashboard dữ liệu cho AI/Data Science, nhưng khi áp dụng vào một ứng dụng quản trị vận hành F&B đa bước (Multi-step ERP/POS Operations), các hạn chế về mặt vòng đời (Execution Lifecycle) bộc lộ rất rõ ràng.

### 1.1. Chu Kỳ Re-run Toàn Bộ Trang (Full Script Re-execution)
- **Cơ chế hoạt động:** Mỗi khi người dùng bấm bất kỳ nút nào, gõ phím vào ô nhập liệu hoặc chuyển tab, Streamlit sẽ **thực thi lại toàn bộ mã nguồn của [src/dashboard/app.py](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/dashboard/app.py) từ dòng 1 đến dòng 1,234**.
- **Tác động hiệu năng & UX:**
  - Mọi hàm không được bọc cache (`@st.cache_data`) đều bị tính toán lại.
  - Các kết nối cơ sở dữ liệu và truy vấn ORM bị kích hoạt lại nhiều lần không cần thiết.
  - Màn hình thường xuyên xuất hiện biểu tượng Running quay tròn (Spinner) góc trên bên phải, gây cảm giác giật lag cho nhân viên thao tác quầy bar.

---

## 2. QUẢN LÝ TRẠNG THÁI (STATE MANAGEMENT AUDIT - `st.session_state`)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SESSION STATE INVENTORY & RISKS                       │
├──────────────────────────┬──────────────────────────┬───────────────────────┤
│ Biến Session State       │ Mục Đích Sử Dụng         │ Rủi Ro Kỹ Thuật       │
├──────────────────────────┼──────────────────────────┼───────────────────────┤
│ authenticated            │ Cờ trạng thái đăng nhập  │ Mất khi F5 trình duyệt│
├──────────────────────────┼──────────────────────────┼───────────────────────┤
│ user_role, user_name     │ Thông tin phân quyền     │ Không có token ký số  │
├──────────────────────────┼──────────────────────────┼───────────────────────┤
│ operations_agent         │ Instance MixueOperations-│ Giữ unclosed DB       │
│                          │ Agent (kèm draft_plans)  │ sessions trong RAM    │
├──────────────────────────┼──────────────────────────┼───────────────────────┤
│ sticker_result           │ Kết quả giải mã tem ly   │ Không giải phóng khi  │
│                          │                          │ lỗi (BUG-STICKER-01)  │
├──────────────────────────┼──────────────────────────┼───────────────────────┤
│ stock_editor_df          │ Dữ liệu bảng kho 31 ngày │ Mất dữ liệu khi đổi   │
│                          │ đang chỉnh sửa           │ tab (BUG-STOCK-02)    │
├──────────────────────────┼──────────────────────────┼───────────────────────┤
│ chat_history             │ Lịch sử hội thoại AI     │ Phình to RAM session  │
│                          │                          │ theo thời gian        │
└──────────────────────────┴──────────────────────────┴───────────────────────┘
```

### 2.1. Phân Tích Lỗi BUG-STICKER-01 (Dính Trạng Thái Cũ Khi Lỗi)
- **Vị trí mã nguồn:** [src/dashboard/app.py:1020-1045](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/dashboard/app.py#L1020-L1045)
- **Cơ chế phát sinh lỗi:**
  ```python
  if st.button("🔍 Giải mã tem ly"):
      res = agent.tool_decode_recipe_or_sticker(code_input)
      if res.get("status") == "SUCCESS":
          st.session_state["sticker_result"] = res
      else:
          st.error(res.get("message"))
          # LỖI: Không xóa st.session_state["sticker_result"] cũ!
  ```
  Nếu lần trước người dùng giải mã thành công một tem ly (ví dụ `24101`), kết quả được lưu vào `st.session_state["sticker_result"]`. Khi người dùng nhập một mã tem sai (ví dụ `99999`) và bấm giải mã, hệ thống hiển thị thông báo lỗi `st.error(...)`, nhưng **bên dưới vẫn tiếp tục vẽ card kết quả của mã tem `24101` trước đó** do biến session cũ không bị `pop()`!

### 2.2. Phân Tích Lỗi BUG-STOCK-02 (Mất Trạng Thái Sửa Ô Bảng Kho)
- **Vị trí mã nguồn:** [src/dashboard/app.py:530-580](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/dashboard/app.py#L530-L580)
- **Cơ chế phát sinh lỗi:**
  - Component `st.data_editor` lưu trữ các thay đổi tạm thời (deltas) trong bộ nhớ widget cục bộ của trình duyệt.
  - Khi nhân viên đang sửa 5 ô trong bảng kho nhưng chuyển sang Tab khác (ví dụ: Tab Sơ chế hoặc Tab Chốt ca) trước khi bấm nút **"💾 Lưu thay đổi"**, Streamlit unmount component `st.data_editor`.
  - Toàn bộ deltas chưa lưu bị hủy bỏ ngay lập tức mà không có bất kỳ hộp thoại xác nhận nào (No "Discard unsaved changes?" prompt). Khi nhân viên quay lại Tab Báo cáo & Kho, bảng trở về trạng thái ban đầu.

---

## 3. THIẾT KẾ THƯƠNG HIỆU & TÙY BIẾN CSS/JS (BRAND UI & STYLING)

### 3.1. Nhận Diện Thương Hiệu Tuyết Vương Mixue (`brand_ui.py`)
- **Điểm sáng xuất sắc:**
  - Tệp [src/dashboard/brand.css](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/dashboard/brand.css) được đầu tư công phu với hơn 700 dòng CSS tùy biến.
  - Sử dụng bảng màu chuẩn thương hiệu Mixue: Đỏ Mixue (`#e60012`, `#d90429`), Trắng tuyết (`#ffffff`), Vàng kem (`#ffb703`).
  - Font chữ hiện đại, bo góc chuẩn mực, hệ thống Badge và Card được thiết kế đậm phong cách ứng dụng My Mixue.
  - Tích hợp linh vật Tuyết Vương (Snow King / 雪王) dạng ảnh base64 tối ưu, có animation mascot suy nghĩ (`mascot-thinking`).

### 3.2. Cầu Nối JavaScript GSAP (`_motion_component`)
- **Vị trí mã nguồn:** [src/dashboard/brand_ui.py:52-63](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/dashboard/brand_ui.py#L52-L63)
- **Đánh giá kiến trúc:**
  - Nhóm phát triển đã sử dụng API hiện đại `streamlit.components.v2` để nạp trực tiếp GSAP (GreenSock Animation Platform) và ScrollTrigger từ thư mục local assets mà không phụ thuộc CDN bên ngoài.
  - Mã JavaScript giải quyết xung đột UMD trên ES modules (`isolate_styles=False`) rất thông minh.
- **Rủi ro tương thích:**
  - `streamlit.components.v2` là một API thử nghiệm (experimental). Trong các phiên bản Streamlit tương lai, API này có thể thay đổi hợp đồng gọi hàm, gây vỡ giao diện nếu nâng cấp thư viện mà không kiểm tra hồi quy.

---

## 4. ĐÁNH GIÁ TRẢI NGHIỆM NGƯỜI DÙNG & KIỂM SOÁT LỖI GIAO DIỆN (UI/UX AUDIT)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          UI/UX STATE EVALUATION                             │
├────────────────────┬──────────┬─────────────────────────────────────────────┤
│ Trạng Thái UI      │ Đánh Giá │ Chi Tiết Đánh Giá                           │
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ 1. Loading State   │ KÉM      │ Khi chạy dự báo 14s chỉ có spinner nhỏ góc  │
│                    │          │ trên; không có progress bar hay skeleton    │
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ 2. Empty State     │ TỐT      │ Có thông báo thân thiện khi không có dữ liệu│
│                    │          │ bán hàng hoặc danh sách chờ duyệt rỗng      │
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ 3. Error Feedback  │ TRUNG BÌNH│ Lỗi đăng nhập để trống ô trả về None thay   │
│                    │          │ vì thông báo "Vui lòng nhập tài khoản"      │
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ 4. Visual Validate │ KÉM      │ st.data_editor không tô đỏ khi nhập số âm   │
│                    │          │ (BUG-STOCK-01)                              │
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ 5. Toast / Notice  │ TỐT      │ Sử dụng st.toast và st.success rõ ràng      │
│                    │          │ sau khi duyệt thành công lệnh kho           │
└────────────────────┴──────────┴─────────────────────────────────────────────┘
```

### 4.1. Lỗi Hiển Thị Đăng Nhập Để Trống (BUG-AUTH-01)
- Tại [src/dashboard/brand_ui.py:160-190](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/dashboard/brand_ui.py#L160-L190):
  Khi người dùng chưa gõ ký tự nào vào ô Tài khoản hoặc Mật khẩu nhưng bấm nút "Đăng Nhập Ngay", hệ thống gọi thẳng `verify_user("", "")` và trả về thông báo lỗi chung chung: *"Tên đăng nhập hoặc mật khẩu không chính xác!"*.
  Trải nghiệm người dùng chuẩn cần kiểm tra form validation phía client trước: *"Vui lòng nhập đầy đủ Tên đăng nhập và Mật khẩu!"*.

### 4.2. Thiếu Định Dạng Điều Kiện Trực Quan Trên Bảng Kho (BUG-STOCK-01)
- Bảng `st.data_editor` trong tab Sổ Kho 31 Ngày cho phép người dùng gõ số âm (ví dụ `-10`). Mặc dù khi bấm Lưu, backend `validator.py` sẽ từ chối ghi nhận, nhưng trên bảng tính, ô đó không được tô đỏ viền hoặc hiển thị biểu tượng cảnh báo lỗi tức thì (Inline Validation Error), gây hoang mang cho nhân viên thu ngân.

---

## 5. KHUYẾN NGHỊ TỐI ƯU HÓA FRONTEND (FRONTEND HARDENING RECOMMENDATIONS)

1. **Khắc phục Triệt để BUG-STICKER-01:**
   Thêm lệnh xóa trạng thái `st.session_state.pop("sticker_result", None)` tại nhánh `else` khi giải mã tem thất bại.
2. **Bảo vệ Trạng Thái Soạn Thảo Bảng Kho (BUG-STOCK-02):**
   Lưu tạm bản thảo chỉnh sửa vào `st.session_state["stock_unsaved_draft"]` mỗi khi có thay đổi trên `st.data_editor` để không bị mất khi chuyển tab.
3. **Bổ sung Thanh Tiến Trình (Progress Bar) Cho Dự Báo:**
   Khi gọi `forecast_demand()`, bổ sung `st.progress()` lặp qua 39 mã sản phẩm để người dùng theo dõi được tiến độ, loại bỏ cảm giác ứng dụng bị treo.
4. **Client-side Form Validation Trước Khi Đăng Nhập (BUG-AUTH-01):**
   Kiểm tra `if not username.strip() or not password.strip(): st.warning(...)` trước khi gửi truy vấn xác thực xuống database.
