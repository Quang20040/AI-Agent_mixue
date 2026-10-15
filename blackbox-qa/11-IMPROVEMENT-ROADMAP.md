# 11 – IMPROVEMENT ROADMAP & ARCHITECTURAL RECOMMENDATIONS (LỘ TRÌNH CẢI TIẾN & ĐỀ XUẤT KỸ THUẬT)

> **Dự án:** BeverageOps AI — Quản trị Điều phối Vận hành Chi nhánh Mixue 39 Tôn Quang Phiệt  
> **Người lập:** Senior QA Lead, Business Analyst & Solutions Architect  
> **Mục tiêu:** Cung cấp hướng dẫn kỹ thuật chi tiết để nhóm phát triển (Development Team) tiến hành sửa lỗi và nâng cấp trong Vòng 2 (Phase 2).  

---

## 1. LỘ TRÌNH TRIỂN KHAI 3 GIAI ĐOẠN (3-PHASE ROADMAP)

```
┌────────────────────────────────────────────────────────┐
│  GIAI ĐOẠN 1: HOTFIXES & TRẢI NGHIỆM VẬN HÀNH (Tuần 1)  │
│  Sửa 8 lỗi P2 & P3 · Tối ưu nút Đăng xuất · Xóa tem cũ │
└──────────────────────────┬─────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────┐
│  GIAI ĐOẠN 2: KHÉP KÍN QUY TRÌNH & HIỆU NĂNG (Tuần 2-3) │
│  Khâu Nhận hàng PO · Cache Dự báo · Cảnh báo Âm kho    │
└──────────────────────────┬─────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────┐
│  GIAI ĐOẠN 3: TÍNH NĂNG DOANH NGHIỆP SAAS (Tháng tới) │
│  Audit Trail Log · Webhook Zalo/Telegram · Báo cáo P&L │
└────────────────────────────────────────────────────────┘
```

---

## 2. HƯỚNG DẪN KỸ THUẬT CHI TIẾT CHO NHÓM PHÁT TRIỂN (SPRINT 1 HOTFIXES)

### 2.1. Sửa lỗi không xóa tem dán ly cũ khi gặp mã lỗi (`BUG-STICKER-01`)
- **Tập tin cần sửa:** `src/dashboard/app.py`
- **Vị trí:** Khối `elif section == "Tem & công thức":` (dòng ~1035)
- **Đoạn mã đề xuất:**
  ```python
  if st.button("Giải mã Tem dán", key="dec_btn_vi", type="primary", use_container_width=True):
      res = agent.tool_decode_recipe_or_sticker(code_input)
      if res["status"] == "SUCCESS":
          st.session_state["sticker_result"] = res
      else:
          # Xóa bỏ kết quả tem cũ để không gây nhầm lẫn cho Barista
          st.session_state.pop("sticker_result", None)
          st.error(res["message"])
  ```

---

### 2.2. Sửa thông báo lỗi khi để trống form đăng nhập (`BUG-AUTH-01`)
- **Tập tin cần sửa:** `src/dashboard/brand_ui.py`
- **Vị trí:** Trong `render_login_screen()` (dòng ~330)
- **Đoạn mã đề xuất:**
  ```python
  if submitted:
      clean_u = (username or "").strip()
      clean_p = (password or "").strip()
      if not clean_u or not clean_p:
          st.error("⚠️ Vui lòng điền đầy đủ Tên đăng nhập và Mật khẩu!")
      else:
          user = verify_user(clean_u, clean_p)
          if user:
              _apply_login_session(user)
              st.success(f"Đăng nhập thành công! Xin chào {user['name']}.")
              st.rerun()
          else:
              st.error("Tên đăng nhập hoặc mật khẩu không chính xác! Vui lòng thử lại.")
  ```

---

### 2.3. Bổ sung nút Đăng xuất nhanh ở Header (`BUG-NAV-01`)
- **Tập tin cần sửa:** `src/dashboard/app.py`
- **Đoạn mã đề xuất:** Thêm một container góc trên bên phải thanh điều hướng chính:
  ```python
  c_nav, c_user = st.columns([5, 1.2])
  with c_nav:
      section = st.radio(...)
  with c_user:
      st.markdown(f"**{user_name}** ({user_badge})")
      if st.button("🚪 Đăng xuất", key="btn_quick_logout", use_container_width=True):
          for k in ["authenticated", "user", "username", "user_role", ...]:
              st.session_state.pop(k, None)
          st.rerun()
  ```

---

### 2.4. Bổ sung thanh tiến trình % khi chạy dự báo D+1 (`BUG-PERF-01`)
- **Tập tin cần sửa:** `src/engine/forecasting.py` và `src/dashboard/app.py`
- **Đoạn mã đề xuất:**
  ```python
  if st.button("🚀 Chạy Mô hình Dự báo", key="run_fc_btn_vi", type="primary", use_container_width=True):
      progress_bar = st.progress(0, text="Đang khởi tạo thuật toán dự báo menu 39 SKU...")
      
      def on_progress_callback(current, total, sku_name):
          pct = int((current / total) * 100)
          progress_bar.progress(pct, text=f"Đang tính toán món {current}/{total}: {sku_name} ({pct}%)")

      fc_res = agent.forecast_engine.forecast_demand(
          target_date_input, horizon_days=1, model=selected_model_val, 
          progress_callback=on_progress_callback
      )
      progress_bar.empty()
      st.session_state["latest_forecast_vi"] = fc_res
      st.success(f"Đã lập dự báo thành công cho toàn bộ {len(fc_res)} món!")
  ```

---

### 2.5. Cảnh báo trực quan khi Tồn kho Sổ sách bị âm (`BUG-STOCK-01`)
- **Tập tin cần sửa:** `src/dashboard/app.py`
- **Đoạn mã đề xuất:**
  ```python
  # Kiểm tra các mặt hàng âm kho
  negative_items = matrix_df[pd.to_numeric(matrix_df["Tồn sổ sách"], errors="coerce") < 0]
  if not negative_items.empty:
      neg_names = ", ".join(negative_items["Tên mặt hàng (Quy cách)"].tolist()[:3])
      st.warning(f"🚨 **CẢNH BÁO ÂM KHO:** Đang có **{len(negative_items)}** mặt hàng có tồn sổ sách bị âm ({neg_names}...). Vui lòng kiểm tra lại hóa đơn nhập hàng xe tổng hoặc sai sót kiểm kê quầy!")
  ```

---

## 3. KHÉP KÍN QUY TRÌNH NGHIỆP VỤ TRONG GIAI ĐOẠN 2 (SPRINT 2)

### 3.1. Chức năng "Xác nhận Đã Nhận Hàng PO" (Goods Receipt Confirmation)
- **Bài toán:** Hiện tại Đơn PO được ký duyệt nhưng chưa có cơ chế tự động ghi sổ khi xe hàng về.
- **Giải pháp:**
  1. Thêm bảng `purchase_orders` có trạng thái: `DRAFT` $\rightarrow$ `APPROVED` $\rightarrow$ `RECEIVED` $\rightarrow$ `CANCELLED`.
  2. Tại tab "Nhập hàng", hiển thị danh sách các đơn PO đang chờ nhận hàng.
  3. Khi xe hàng Mixue đến giao, Quản lý bấm nút **"📦 Xác nhận Nhận Hàng PO #XXXX"**.
  4. Hệ thống tự động tạo các dòng biến động kho loại `IN` trong bảng `daily_stock_movements`, lập tức cập nhật vào cột Nhập của Ma trận thẻ kho mà Quản lý không cần gõ lại bằng tay.

### 3.2. Cảnh báo dữ liệu chưa lưu khi rời bảng Ma trận kho (`BUG-STOCK-02`)
- Tích hợp cờ `st.session_state["stock_matrix_has_unsaved_changes"]` khi phát hiện `edited_rows` khác rỗng.
- Hiển thị banner nổi bật màu cam ở đầu trang: *"⚠️ Bạn có thay đổi trên bảng ma trận kho chưa được lưu xuống hệ thống. Hãy bấm 'Lưu Các Ô Đã Sửa' trước khi rời trang!"*.

---

## 4. TIÊU CHÍ NGHIỆM THU CHO VÒNG KIỂM THỬ HỒI QUY (PHASE 2 ACCEPTANCE)

1. Tái chạy bộ kiểm thử tự động `blackbox_master_suite.py`:
   - Toàn bộ 45 test case phải đạt kết quả **PASS 100%**.
   - Không còn lỗi P2 nào tồn đọng.
2. Kiểm tra lại toàn diện trên 7 viewport di động và desktop.
3. Đánh giá lại Bảng điểm chất lượng Quality Scorecard: Đạt tối thiểu **95 / 100 điểm** để chính thức cấp chứng nhận **FULL GO**.
