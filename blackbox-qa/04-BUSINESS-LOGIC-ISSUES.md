# 04 – BUSINESS LOGIC ISSUES (PHÂN TÍCH VẤN ĐỀ LOGIC NGHIỆP VỤ)

> **Dự án:** BeverageOps AI — Quản trị Điều phối Vận hành Chi nhánh Mixue 39 Tôn Quang Phiệt  
> **Chuyên môn đánh giá:** Business Analyst & F&B Operations Auditor  
> **Nguyên tắc phân loại:** 
> - **Confirmed Logic Bug:** Lỗi logic đã được kiểm chứng bằng thực nghiệm.
> - **Suspected Logic Bug:** Điểm nghi vấn logic tiềm ẩn rủi ro trong luồng thao tác phức tạp.
> - **Missing Business Rule:** Thiếu quy tắc ràng buộc nghiệp vụ thực tế.
> - **UX Design Weakness:** Bất cập trong thiết kế làm suy giảm trải nghiệm hoặc gây nhầm lẫn nghiệp vụ.

---

## 1. ĐÁNH GIÁ 10 KỊCH BẢN BẮT BUỘC (SCENARIOS A – J)

### Scenario A – Duplicate Data (Dữ liệu trùng lặp)
- **Kịch bản kiểm tra:**
  1. Thử tạo tài khoản nhân viên với Username đã có sẵn (`nhanvien`).
  2. Thử tạo 2 phiếu đề xuất lệnh kho liên tiếp có cùng mặt hàng, cùng số lượng trong cùng 1 phút.
- **Kết quả thực nghiệm:**
  - *Quản lý nhân viên:* Hệ thống kiểm tra và chặn trùng Username thành công (`db.query(User).filter(...)`). **[ĐẠT]**
  - *Lệnh xuất kho:* Hệ thống cho phép tạo 2 phiếu xuất kho giống hệt nhau liên tiếp mà không có cảnh báo trùng lặp ("Bạn vừa tạo một phiếu xuất tương tự cách đây 30 giây, bạn có chắc chắn không?").
- **Phân loại:** **Missing Business Rule (Mức độ P2)**  
- **Rủi ro vận hành:** Nhân viên pha chế có thể click nhầm 2 lần làm gửi 2 đề xuất xuất kho, nếu Quản lý duyệt nhanh có thể trừ trùng gấp đôi số lượng tồn kho.

---

### Scenario B – Invalid State Transition (Chuyển trạng thái trái quy tắc)
- **Kịch bản kiểm tra:**
  1. Lệnh kho đã được Duyệt (APPROVED) hoặc Từ chối (REJECTED), thử bấm lại nút Duyệt.
  2. Kế hoạch sơ chế đã được Quản lý ký duyệt, kiểm tra xem có thể bị ký đè hoặc hủy bởi tài khoản nhân viên không.
- **Kết quả thực nghiệm:**
  - Khi Quản lý bấm "Duyệt" một lệnh kho trong hòm thư, lệnh đó lập tức biến mất khỏi danh sách chờ (`pending_requests`) và chuyển sang trạng thái APPROVED. Không có cách nào chuyển ngược về PENDING hay bấm duyệt lần 2.
  - Kế hoạch sơ chế và đơn PO sau khi duyệt được gắn cờ `is_approved = True`.
- **Phân loại:** **ĐẠT (Hệ thống kiểm soát trạng thái chặt chẽ)**

---

### Scenario C – Missing Prerequisite (Bỏ qua bước chuẩn bị bắt buộc)
- **Kịch bản kiểm tra:**
  1. Thử tạo phiếu đề xuất kho với số lượng bằng 0 hoặc số âm (`-5.0`).
  2. Thử tạo đơn nhập hàng PO khi chưa nạp dữ liệu tồn kho hiện tại.
- **Kết quả thực nghiệm:**
  - Form tạo lệnh kho có `min_value=0.1`, chặn hoàn toàn việc nhập số 0 hoặc số âm ngay tại input component.
  - Động cơ tối ưu PO kiểm tra dữ liệu tồn kho, nếu thiếu sẽ fallback về ngưỡng an toàn.
- **Phân loại:** **ĐẠT**

---

### Scenario D – Conflicting Actions (Hai thao tác mâu thuẫn đồng thời)
- **Kịch bản kiểm tra:**
  1. Thử vừa sửa số lượng tại một ô trên ma trận thẻ kho, vừa xóa lệnh phát sinh trong cùng ngày.
- **Kết quả thực nghiệm:**
  - Hệ thống sử dụng cơ chế SQLite Transaction: Mỗi thao tác ghi nhận đều cập nhật lại bảng biến động kho (`daily_stock_movements`) và tính toán lại lũy kế theo ngày.
  - Tuy nhiên, nếu Quản lý sửa ô trực tiếp bằng tay trên bảng `st.data_editor` mà quên bấm nút *"💾 Lưu Các Ô Đã Sửa Vào Sổ Kho"*, sau đó chuyển tab thì dữ liệu vừa gõ sẽ bị mất mà không có hộp thoại cảnh báo (Unsaved Changes Warning).
- **Phân loại:** **UX Design Weakness / Confirmed Logic Bug (Mức độ P2)**  
- **Rủi ro vận hành:** Quản lý nghĩ rằng đã sửa xong số liệu nhưng thực chất dữ liệu chưa được ghi xuống cơ sở dữ liệu.

---

### Scenario E – Refresh / Back During Workflow (Rời quy trình giữa chừng)
- **Kịch bản kiểm tra:**
  1. Đang điền form tạo nhân viên mới hoặc tạo lệnh kho, bấm F5 hoặc Back trình duyệt.
- **Kết quả thực nghiệm:**
  - Form Streamlit bị reset về mặc định, dữ liệu đang gõ dở bị xóa (đúng tiêu chuẩn stateless web form).
  - Không phát sinh bản ghi rác (orphan records) trong database.
- **Phân loại:** **ĐẠT**

---

### Scenario F – Double Submission (Bấm gửi liên tiếp nhiều lần)
- **Kịch bản kiểm tra:**
  1. Bấm nút "Gửi Đề Xuất Lệnh Kho Chờ Quản Lý Duyệt" liên tiếp 3 lần thật nhanh (Rapid Double Click).
- **Kết quả thực nghiệm:**
  - Streamlit có cơ chế disable button sau khi click lần đầu trong lúc script rerun. Tuy nhiên, nếu mạng chậm hoặc client trễ một vài millisecond, vẫn có xác suất gửi 2 request liên tiếp tạo 2 bản ghi.
- **Phân loại:** **Suspected Logic Bug (Mức độ P2)**  
- **Khuyến nghị:** Thêm cơ chế Idempotency Key hoặc Client Debounce / Disable state tức thì.

---

### Scenario G – Data Consistency (Đồng bộ dữ liệu đa phân hệ)
- **Kịch bản kiểm tra:**
  1. Nhân viên tạo lệnh xuất `2.0 thùng Trà đen`.
  2. Quản lý duyệt lệnh.
  3. Kiểm tra xem ô ngày hôm nay trên Sổ Thẻ Kho Ma Trận 31 Ngày có tự động tăng thêm `2.0` không.
  4. Kiểm tra xem Báo Cáo Đối Soát Hao Hụt có phản ánh lượng xuất mới không.
- **Kết quả thực nghiệm:**
  - Cột ngày tương ứng trên Ma trận thẻ kho cập nhật tức thì tăng đúng `2.0 thùng`.
  - Tồn sổ sách cuối kỳ giảm chính xác tương ứng.
  - Logic tính toán liên kết giữa `daily_stock_service.py` và `bom_engine.py` hoạt động nhất quán và đồng bộ 100%.
- **Phân loại:** **ĐẠT (Độ đồng bộ dữ liệu xuất sắc)**

---

### Scenario H – User Permission (Cách ly phân quyền bảo mật)
- **Kịch bản kiểm tra:**
  1. Đăng nhập tài khoản `nhanvien` (Staff).
  2. Kiểm tra xem có thể xem được Báo cáo Doanh thu, Ma trận kho 31 ngày, Dự báo nhu cầu, hoặc duyệt đơn PO không.
  3. Thử can thiệp vào `st.session_state` hoặc radio navigation để ép hiển thị các trang cấm.
- **Kết quả thực nghiệm:**
  - Phân quyền RBAC kiểm soát ở cả 2 tầng: Tầng hiển thị (Navigation Filter) và Tầng xử lý logic (`can_access_page()`).
  - Nếu Staff cố tình truy cập trang cấm, hệ thống hiển thị thông báo lỗi bảo mật nghiêm ngặt: *"🔒 Truy cập bị từ chối: Bạn không có quyền truy cập trang này. Chức năng chỉ dành riêng cho Quản lý và Chủ cửa hàng (Admin)."*
  - Chatbot Tuyết Vương AI cũng kích hoạt Guardrail chặn nhân viên hỏi về số liệu tài chính.
- **Phân loại:** **ĐẠT (Phân quyền bảo mật đa tầng kiên cố)**

---

### Scenario I – Interrupted Workflow (Mất kết nối giữa chừng và khôi phục)
- **Kịch bản kiểm tra:**
  1. Đang chạy tính toán mô hình dự báo (mất ~14 giây), làm gián đoạn kết nối trình duyệt hoặc refresh.
- **Kết quả thực nghiệm:**
  - Khi refresh giữa chừng, backend Python hoàn tất luồng tính toán nhưng UI hiển thị lại trạng thái trước khi bấm. Người dùng bấm lại nút sẽ chạy lại bình thường mà không bị treo vĩnh viễn (No Deadlock).
- **Phân loại:** **ĐẠT**

---

### Scenario J – Logical Contradictions (Mâu thuẫn logic nghiệp vụ)
- **Kịch bản kiểm tra:**
  1. Tồn kho thực tế âm: Nếu xuất kho vượt quá số lượng tồn hiện có thì sao?
  2. Thời gian bảo quản SOP: Nếu đề xuất nấu mẻ trà vượt quá dung tích tiêu thụ trong 4 giờ thì hệ thống có cảnh báo không?
- **Kết quả thực nghiệm:**
  - *Tồn kho âm:* Trong ma trận kho, nếu xuất lớn hơn tồn lũy kế, cột "Tồn sổ sách" có thể hiển thị số âm (ví dụ: `-1.5 thùng`). Mặc dù thực tế quầy có thể vay mượn kho tổng hoặc chưa kịp nhập hóa đơn xe hàng về sổ, nhưng hệ thống hiện **chưa có cảnh báo trực quan màu đỏ (Red Highlight Alert)** khi một mặt hàng rơi vào tình trạng âm kho.
  - *Hạn dùng SOP:* Động cơ sơ chế có tính toán đệm an toàn và ghi chú rõ thời hạn bảo quản 4 giờ của trà và trân châu.
- **Phân loại:** **Missing Business Rule / Confirmed Logic Bug (Mức độ P2)**  
- **Khuyến nghị:** Bổ sung cảnh báo khi Tồn sổ sách < 0: *"Cảnh báo: Mặt hàng này đang âm kho, vui lòng kiểm tra hóa đơn nhập chưa ghi sổ hoặc sai sót kiểm đếm!"*

---

## 2. BẢNG TỔNG HỢP VẤN ĐỀ LOGIC NGHIỆP VỤ PHÁT HIỆN

| Mã lỗi | Phân loại | Tên vấn đề | Tác động nghiệp vụ | Mức độ ưu tiên |
|---|---|---|---|---|
| **LOGIC-01** | Confirmed Logic Bug | Sổ thẻ kho ma trận cho phép tồn kho sổ sách hiển thị giá trị âm mà không có cảnh báo đỏ | Quản lý không nhận biết kịp thời việc quầy khui hàng vượt quá số lượng hóa đơn nhập, dẫn đến lệch sổ sách kế toán | **P2 (Medium)** |
| **LOGIC-02** | Missing Business Rule | Thiếu cơ chế kiểm tra trùng lặp (Duplicate Detection) khi nhân viên tạo 2 phiếu kho giống hệt nhau liên tiếp | Có nguy cơ trừ trùng gấp đôi tồn kho nếu Quản lý duyệt nhầm cả 2 lệnh | **P2 (Medium)** |
| **LOGIC-03** | UX Design Weakness | Sửa ô trực tiếp trên ma trận thẻ kho không có cảnh báo "Dữ liệu chưa lưu" (Unsaved Warning) nếu người dùng chuyển tab | Quản lý tưởng đã lưu nhưng thực chất dữ liệu sửa tay bị mất | **P2 (Medium)** |
| **LOGIC-04** | Confirmed State Bug | Nhập sai mã tem dán ly (ABC) nhưng tem đồ họa cũ của lần tra cứu trước không bị xóa bỏ | Barista nhìn nhầm tem cũ dưới thông báo lỗi, có nguy cơ pha sai món cho khách | **P2 (Medium)** |
| **LOGIC-05** | Missing Business Rule | Chưa có giới hạn trần (Max Ceiling) khi nhập số lượng xuất kho tại quầy (hiện cho phép nhập tối đa 50-100 thùng) | Nhân viên gõ nhầm 5 thành 50 thùng sẽ làm lệch hoàn toàn thẻ kho | **P3 (Low)** |
