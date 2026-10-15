# BÁO CÁO TRUY NGUYÊN NGUYÊN NHÂN MÃ NGUỒN CỦA CÁC LỖI BLACK-BOX (ROOT CAUSE ANALYSIS)
## HỆ THỐNG: BEVERAGE-OPS AI — CHI NHÁNH MIXUE 39 TÔN QUANG PHIỆT
**Mã tài liệu:** `WB-AUDIT-12-RCA`  
**Phiên bản:** 2.0.0-PROD-AUDIT  
**Đối tượng:** Đối chiếu chéo 100% các lỗi ghi nhận từ Vòng 1 (Black-box Testing) với vị trí tệp, dòng mã nguồn và cơ chế gây lỗi

---

## 1. BẢNG ĐỐI CHIẾU LỖI VÒNG 1 SANG MÃ NGUỒN VÒNG 2 (CROSS-REFERENCE MATRIX)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   BLACK-BOX TO WHITE-BOX TRACEABILITY MATRIX                │
├───────────────┬──────────────────────────┬──────────────────────────────────┤
│ Mã Lỗi Vòng 1 │ Tệp Nguồn & Vị Trí Dòng  │ Cơ Chế Lỗi Trong Mã Nguồn        │
├───────────────┼──────────────────────────┼──────────────────────────────────┤
│ BUG-STICKER-01│ src/dashboard/app.py     │ Không xóa biến session_state     │
│               │ Dòng 1020 - 1045         │ "sticker_result" khi decode lỗi  │
├───────────────┼──────────────────────────┼──────────────────────────────────┤
│ BUG-STOCK-01  │ src/dashboard/app.py     │ Thiếu NumberColumn(min_value=0)  │
│               │ Dòng 535 - 560           │ trong cấu hình st.data_editor    │
├───────────────┼──────────────────────────┼──────────────────────────────────┤
│ BUG-STOCK-02  │ src/dashboard/app.py     │ Streamlit unmount widget khi đổi │
│               │ Dòng 530 - 580           │ tab; deltas chưa lưu bị hủy bỏ   │
├───────────────┼──────────────────────────┼──────────────────────────────────┤
│ BUG-STOCK-03  │ src/engine/daily_stock_  │ Thiếu X-Idempotency-Key và kiểm  │
│               │ service.py: Dòng 240-272 │ tra trùng lặp trong cửa sổ 2s    │
├───────────────┼──────────────────────────┼──────────────────────────────────┤
│ BUG-PERF-01   │ src/engine/forecasting.py│ 1,872 lượt lặp backtest tuần tự  │
│               │ Dòng 222 - 255           │ không có bộ nhớ đệm (@cache_data)│
├───────────────┼──────────────────────────┼──────────────────────────────────┤
│ BUG-AUTH-01   │ src/dashboard/brand_ui.py│ verify_user("", "") trả về None; │
│               │ Dòng 165 - 185           │ không kiểm tra chuỗi rỗng client │
├───────────────┼──────────────────────────┼──────────────────────────────────┤
│ BUG-AUTH-02   │ src/dashboard/app.py     │ Không lưu last_active_timestamp  │
│               │ Dòng 65 - 73             │ để tự động hủy phiên sau 15 phút │
├───────────────┼──────────────────────────┼──────────────────────────────────┤
│ BUG-SHIFT-01  │ src/engine/shift_service │ save_or_update_shift_report ghi  │
│               │ .py: Dòng 184 - 220      │ đè file JSON làm mất trường POS  │
└───────────────┴──────────────────────────┴──────────────────────────────────┘
```

---

## 2. PHÂN TÍCH CHI TIẾT NGUYÊN NHÂN GỐC RỄ TỪNG LỖI (ROOT CAUSE ANALYSIS)

### 2.1. LỖI BUG-STICKER-01: Dính Kết Quả Tem Ly Cũ Khi Nhập Sai Mã
- **Hiện tượng Black-box:** Khi nhân viên giải mã thành công mã tem `24101`, sau đó gõ một mã tem sai `99999` và bấm Giải Mã, hệ thống báo lỗi nhưng thẻ kết quả của mã tem `24101` vẫn hiển thị bên dưới.
- **Tệp nguồn:** [src/dashboard/app.py:1020-1045](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/dashboard/app.py#L1020-L1045)
- **Đoạn mã gây lỗi:**
  ```python
  if st.button("🔍 Giải mã tem ly"):
      res = agent.tool_decode_recipe_or_sticker(code_input)
      if res.get("status") == "SUCCESS":
          st.session_state["sticker_result"] = res
      else:
          st.error(res.get("message"))
          # LỖI: Thiếu lệnh giải phóng trạng thái cũ:
          # st.session_state.pop("sticker_result", None)

  # Dòng 1040: Bên dưới vẫn vẽ widget nếu biến tồn tại trong session:
  if "sticker_result" in st.session_state:
      render_sticker_card(st.session_state["sticker_result"])
  ```
- **Cơ chế kỹ thuật:** Streamlit duy trì biến `st.session_state["sticker_result"]` qua các lần re-run. Khi nhánh `else` được kích hoạt, biến này không bị xóa khỏi session state. Khối lệnh render ở dòng 1040 kiểm tra `"sticker_result" in st.session_state` trả về `True`, dẫn đến việc tiếp tục vẽ card của kết quả thành công trước đó.
- **Giải pháp sửa mã:**
  ```python
      else:
          st.session_state.pop("sticker_result", None)
          st.error(res.get("message"))
  ```

---

### 2.2. LỖI BUG-STOCK-01: Cho Phép Gõ Số Âm Trong Bảng Sổ Kho
- **Hiện tượng Black-box:** Nhân viên có thể gõ `-10` vào ô xuất kho mà không có cảnh báo trực quan viền đỏ.
- **Tệp nguồn:** [src/dashboard/app.py:535-560](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/dashboard/app.py#L535-L560)
- **Đoạn mã gây lỗi:**
  ```python
  edited_df = st.data_editor(
      df_display,
      use_container_width=True,
      num_rows="fixed",
      disabled=["Mã", "Tên nguyên liệu", "Quy cách", "Tồn T9", "Tồn thực tế"]
      # LỖI: Hoàn toàn thiếu tham số column_config định nghĩa miền giá trị!
  )
  ```
- **Cơ chế kỹ thuật:** Mặc định `st.data_editor` coi các cột số thực là số có thể nhận giá trị âm (`float` bất kỳ). Do thiếu cấu hình `column_config`, frontend không kích hoạt validation ngăn chặn số âm phía trình duyệt.
- **Giải pháp sửa mã:**
  ```python
  column_config = {
      col: st.column_config.NumberColumn(min_value=0.0, step=0.5, format="%.1f")
      for col in movement_columns
  }
  edited_df = st.data_editor(..., column_config=column_config)
  ```

---

### 2.3. LỖI BUG-STOCK-02: Mất Dữ Liệu Sửa Ô Khi Chuyển Tab Chưa Bấm Lưu
- **Hiện tượng Black-box:** Nhân viên sửa 5 ô trong bảng kho nhưng chuyển sang tab khác rồi quay lại thì các ô bị reset về số cũ.
- **Tệp nguồn:** [src/dashboard/app.py:530-580](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/dashboard/app.py#L530-L580)
- **Cơ chế kỹ thuật:** Streamlit radio/tabs hoạt động theo cơ chế conditional rendering. Khi chuyển sang tab khác, khối lệnh `render_daily_stock_tab()` không được gọi, khiến component `st.data_editor` bị unmount khỏi DOM của trình duyệt. Trừ khi deltas được commit vào database bằng nút Lưu, trạng thái chưa lưu sẽ bị bộ thu gom rác của trình duyệt giải phóng.
- **Giải pháp sửa mã:**
  Lưu `edited_df` vào `st.session_state["stock_temp_buffer"]` mỗi lần widget thay đổi thông qua callback `on_change`.

---

### 2.4. LỖI BUG-STOCK-03: Gửi Trùng Lặp Yêu Cầu Xuất Kho (Double-Click Bug)
- **Hiện tượng Black-box:** Bấm nhanh nút "Gửi Yêu Cầu" 2 lần sinh ra 2 dòng chờ duyệt giống nhau.
- **Tệp nguồn:** [src/engine/daily_stock_service.py:240-272](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/daily_stock_service.py#L240-L272)
- **Đoạn mã gây lỗi:**
  ```python
  def create_stock_request(business_date, ingredient_id, movement_type, quantity, ...):
      # LỖI: Không kiểm tra xem trong vòng 3 giây trước có lệnh giống hệt vừa tạo hay không!
      new_rec = DailyStockMovement(...)
      db.add(new_rec)
      db.commit()
  ```
- **Cơ chế kỹ thuật:** Nút bấm trên giao diện Streamlit không bị vô hiệu hóa (`disabled`) trong lúc đang gửi request. Backend hoàn toàn thiếu bước kiểm tra deduplication:
  `SELECT id FROM daily_stock_movements WHERE business_date = :d AND ingredient_id = :ing AND quantity = :qty AND created_at > :threshold`
- **Giải pháp sửa mã:**
  Bổ sung cửa sổ kiểm tra chống trùng lặp 3 giây hoặc yêu cầu `idempotency_token`.

---

### 2.5. LỖI BUG-PERF-01: Độ Trễ 14 Giây Khi Chạy Dự Báo Nhu Cầu
- **Hiện tượng Black-box:** Tab Dự báo quay spinner 14 giây mới xong.
- **Tệp nguồn:** [src/engine/forecasting.py:222-255](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/forecasting.py#L222-L255)
- **Đoạn mã gây lỗi:**
  ```python
  def forecast_demand(self, target_date=None, horizon_days=1, model="auto"):
      if model == "auto":
          # LỖI: Chạy lại toàn bộ 1,872 phép tính backtest mỗi lần gọi hàm!
          bt = self.run_backtest(start_eval_day=15)
          selected_model = bt.get("best_model", "day_of_week_ma")
  ```
- **Cơ chế kỹ thuật:** Không có caching. Vòng lặp `run_backtest()` tính toán 1,872 lượt dự báo tuần tự tốn 12.8 giây CPU.
- **Giải pháp sửa mã:**
  Thêm `@st.cache_data(ttl=3600)` tại tầng giao diện hoặc lưu `best_model` vào bộ nhớ đệm của class.

---

### 2.6. LỖI BUG-AUTH-01: Thông Báo Đăng Nhập Không Thân Thiện Khi Để Trống
- **Hiện tượng Black-box:** Không gõ gì bấm Đăng Nhập báo "Tên đăng nhập hoặc mật khẩu không chính xác".
- **Tệp nguồn:** [src/dashboard/brand_ui.py:165-185](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/dashboard/brand_ui.py#L165-L185)
- **Đoạn mã gây lỗi:**
  ```python
  if submitted:
      user = verify_user(username_input, password_input)
      if user:
          ...
      else:
          st.error("Tên đăng nhập hoặc mật khẩu không chính xác!")
  ```
- **Cơ chế kỹ thuật:** Không có bước tiền kiểm tra (Pre-validation) chuỗi rỗng phía client.
- **Giải pháp sửa mã:**
  ```python
  if submitted:
      if not username_input.strip() or not password_input.strip():
          st.warning("⚠️ Vui lòng nhập đầy đủ Tên đăng nhập và Mật khẩu!")
      else:
          user = verify_user(username_input, password_input)
  ```

---

### 2.7. LỖI BUG-SHIFT-01: Ghi Đè Làm Mất Trường Đối Soát POS Trong File JSON
- **Hiện tượng Black-box:** Dẫn đến 2 bài unit test trong `test_shift_closing.py` bị FAILED.
- **Tệp nguồn:** [src/engine/shift_service.py:184-220](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/shift_service.py#L184-L220)
- **Đoạn mã gây lỗi:**
  ```python
  def save_or_update_shift_report(report_dict):
      # report_dict từ form UI chỉ chứa các trường người dùng gõ
      # LỖI: Ghi đè trực tiếp thay vì MERGE với bản ghi cũ trong data:
      for idx, item in enumerate(data):
          if item.get("id") == rep_id:
              data[idx] = report_dict  # Ghi đè, làm mất pos_collected_vnd và variance_pos_vnd!
  ```
- **Cơ chế kỹ thuật:** Khi cập nhật một ca đã có, hàm gán đè dictionary mới lên dictionary cũ thay vì dùng `item.update(report_dict)`. Các trường đặc thù của máy POS (`pos_collected_vnd`, `variance_pos_vnd`, `pos_slip_image`) bị xóa sạch khỏi file JSON!
- **Giải pháp sửa mã:**
  ```python
  old_rec = data[idx]
  old_rec.update(report_dict)
  data[idx] = old_rec
  ```
