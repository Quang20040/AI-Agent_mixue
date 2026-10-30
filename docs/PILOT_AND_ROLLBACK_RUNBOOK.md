# HƯỚNG DẪN VẬN HÀNH THỬ NGHIỆM VÀ XỬ LÝ SỰ CỐ / QUAY VỀ PHIÊN BẢN CŨ
## (STORE PILOT OPERATIONS & ROLLBACK RUNBOOK)
**Dự án:** Mixue BeverageOps AI Agent System  
**Địa điểm Pilot:** Mixue 39 Tôn Quang Phiệt, Cổ Nhuế, Bắc Từ Liêm, Hà Nội (Mã CH: `2132`)  
**Phiên bản phát hành:** `v2.0-pilot-ready`  
**Ngày hiệu lực:** Tháng 10/2026

---

## 1. TỔNG QUAN KIẾN TRÚC VÀ CÁC THÀNH PHẦN PILOT

Hệ thống AI Agent hỗ trợ vận hành cửa hàng Mixue gồm các thành phần cốt lõi:
1. **Giao diện Dashboard Streamlit (`src/dashboard/app.py`):**
   - Cung cấp giao diện đăng nhập bảo mật (RBAC: `ADMIN`, `STAFF_OFFICIAL`, `STAFF_PROBATION`).
   - Các phân hệ: Trang chủ, Báo cáo & Kho, Dự báo nhu cầu, Sơ chế mẻ lớn, Nhập hàng PO, Tem & công thức, Quản lý nhân viên, Tuyết Vương AI.
2. **Lõi Điều Phối AI Agent (LangGraph Agent Runtime):**
   - Điều phối công cụ an toàn, hỗ trợ hội thoại nhiều lượt, bộ nhớ ngữ cảnh và ghi nhận tùy chọn hiển thị xuyên phiên.
   - Cơ chế tách bạch: **Xem thử / Lời khuyên (`preview_topping_prep`)** vs **Tạo dự thảo (`optimize_topping_prep`)** vs **Phê duyệt (`request_plan_approval`)**.
3. **Bộ Tra Cứu Tri Thức Quy Chuẩn Địa Phương (Local Hybrid RAG):**
   - Kết hợp BM25 + Trigram 3 ký tự + Nhận diện thực thể mã nguyên liệu/món (Hit@1 = 100%, MRR = 1.0).
   - **Hoàn toàn offline/local**, không gửi tài liệu ra các API bên ngoài nếu chưa được cấp quyền.
4. **Hệ Thống Đọc Chứng Từ Chốt Ca Thực Tế (OCR Real Receipts):**
   - Tách vùng hóa đơn in POS và sổ chốt ca viết tay.
   - Nhận diện đúng mã tệp do máy chủ cấp (`FILE_[A-F0-9]{16}`), không nhận đường dẫn tùy ý.
   - Không tự động làm tròn hay nhân 1.000 khi thiếu căn cứ; lưu dự thảo kiểm định chờ xác nhận.
5. **Cơ Sở Dữ Liệu & Cách Ly Dữ Liệu:**
   - CSDL Nghiệp vụ: `data/beverageops.db` (SQLite WAL / PostgreSQL).
   - CSDL Hội thoại & Audit: `data/agent_private/conversations.sqlite` (SQLite WAL).
   - Ảnh chứng từ: `data/shift_photos/` được bảo mật nội bộ, cách ly theo tài khoản và cửa hàng.

---

## 2. QUY TRÌNH KHỞI CHẠY VÀ THEO DÕI HẰNG NGÀY (DAILY OPERATIONS)

### 2.1. Khởi chạy hệ thống bằng Docker
```bash
# Khởi chạy toàn bộ hệ thống (App + Database)
docker compose up -d --build

# Kiểm tra logs vận hành
docker compose logs -f app
```

### 2.2. Khởi chạy hệ thống trực tiếp (Native Python)
```bash
# Kích hoạt môi trường ảo và chạy Dashboard
streamlit run src/dashboard/app.py --server.port=8501 --server.address=0.0.0.0
```

### 2.3. Kiểm tra sức khỏe hệ thống (Health Check)
Thực hiện định kỳ mỗi sáng trước giờ mở ca (7:30) và sau khi chốt ca tối (23:00):
```bash
python scripts/healthcheck.py
```
*Tiêu chuẩn đạt:*
- `overall_status`: `"HEALTHY"`
- CSDL `database_operations` & `database_conversations`: `"HEALTHY"`
- Dung lượng đĩa còn trống: `>= 500 MB`
- `rag_and_sop_agent`: `"HEALTHY"` (`indexed_chunks >= 5700`)
- `auth_and_users`: `"HEALTHY"`

### 2.4. Sao lưu dữ liệu trực tuyến định kỳ (Daily Online Backup)
Thực hiện tự động cuối mỗi ngày sau khi đã chốt ca tối:
```bash
python scripts/backup_restore.py --backup
```
*Cơ chế an toàn:* Sử dụng SQLite Online Backup API với cơ chế `PRAGMA wal_checkpoint(PASSIVE)` và `PRAGMA integrity_check`, đảm bảo sao lưu không làm gián đoạn người dùng và không gây hỏng dữ liệu.

### 2.5. Xuất báo cáo theo dõi Pilot (Pilot Scorecard)
```bash
python scripts/pilot_scorecard.py
```
Báo cáo được ghi tự động vào `data/agent_private/pilot-scorecard.json` gồm:
- Tỷ lệ lỗi công cụ và API (`tool_and_api_observability`).
- Thống kê sửa trường OCR và thời gian so với baseline thao tác tay thực nghiệm (`210 giây`).
- Đối soát kế hoạch sơ chế so với thực tế kèm nhãn rõ ràng: `[MEASURED]`, `[FORECASTED]`, `[ASSUMED]`.

---

## 3. XỬ LÝ SỰ CỐ THƯỜNG GẶP (TROUBLESHOOTING)

### Sự cố 1: Bảng chốt ca OCR đọc sai số hoặc ảnh bị mờ/mất góc
- **Hiện tượng:** Ô số tiền hiển thị `0 đ` hoặc để trống kèm cảnh báo `uncertain`/`unreadable`.
- **Nguyên nhân:** Ảnh chụp thiếu sáng, chữ viết tay đè lên nhau, hoặc nếp gấp giấy làm mất chữ số.
- **Xử lý chuẩn:**
  1. Tuyệt đối **không tự bịa số** hoặc tự nhân 1.000.
  2. Nhân viên quầy bar bấm vào ô cần chỉnh trên giao diện hoặc chat: `Sửa tiền mặt thành 2.000.000 đ`.
  3. Hệ thống sẽ cập nhật dự thảo, tính lại chênh lệch `variance` và ghi log chỉnh sửa để đánh giá chất lượng.
  4. Quản lý kiểm tra lại số thực tế trước khi bấm "Xác nhận & Lưu".

### Sự cố 2: Cảnh báo quá tải / Rate Limit
- **Hiện tượng:** Chat trả về: *"Vượt quá giới hạn 60 yêu cầu/phút. Vui lòng đợi trong giây lát."*
- **Nguyên nhân:** Người dùng click spam liên tục hoặc có script tự động truy vấn.
- **Xử lý:** Chờ 60 giây để sliding-window bucket tự động giải phóng.

### Sự cố 3: Người dùng quên mật khẩu hoặc bị khóa đăng nhập
- **Hiện tượng:** Nhân viên không thể vào ca vì quên mã PIN 6 số.
- **Xử lý:** Quản lý cửa hàng đăng nhập bằng tài khoản `quanly`, vào mục **👥 Quản lý nhân viên** -> chọn tài khoản nhân viên -> bấm **"Đặt lại mật khẩu"**. Mật khẩu sẽ được reset về `123456`, nhân viên đăng nhập lại và bắt buộc phải đặt mật khẩu 6 số mới.

---

## 4. QUY TRÌNH HẠ CẤP VÀ QUAY VỀ PHIÊN BẢN CŨ (ROLLBACK RUNBOOK)

Khi phát hiện sự cố nghiêm trọng trên hiện trường (ví dụ: lỗi logic tính toán, cơ sở dữ liệu gặp sự cố không thể khắc phục, hoặc phiên bản mới không tương thích), thực hiện quy trình hạ cấp theo 4 bước sau:

```
[BƯỚC 1: DỪNG DỊCH VỤ] ──> [BƯỚC 2: PHỤC HỒI DỮ LIỆU] ──> [BƯỚC 3: ROLLBACK MÃ NGUỒN] ──> [BƯỚC 4: KIỂM ĐỊNH LẠI]
```

### Bước 1: Tạm dừng dịch vụ để ngăn chặn lỗi phát sinh
```bash
# Nếu chạy bằng Docker:
docker compose down

# Nếu chạy native Streamlit:
# Nhấn Ctrl + C trên terminal đang chạy hoặc dừng tiến trình
```

### Bước 2: Phục hồi cơ sở dữ liệu về bản sao lưu ổn định gần nhất
```bash
# 1. Liệt kê các bản sao lưu đã có:
python scripts/backup_restore.py --list

# 2. Thực hiện phục hồi từ mốc thời gian an toàn đã chọn (ví dụ: 20261016_220017):
python scripts/backup_restore.py --restore 20261016_220017
```
*Lưu ý an toàn:* Lệnh restore sẽ tự động chụp một bản snapshot an toàn `_prerestore` trước khi ghi đè dữ liệu.

### Bước 3: Quay về phiên bản mã nguồn trước đó (Git Rollback)
```bash
# 1. Kiểm tra lịch sử commit gần nhất:
git log -n 5 --oneline

# 2. Checkout về tag hoặc commit ổn định trước đó:
git checkout <stable_commit_hash_hoặc_tag>
```

### Bước 4: Kiểm định lại toàn bộ hệ thống sau rollback
```bash
# 1. Chạy healthcheck:
python scripts/healthcheck.py

# 2. Chạy test suite xác nhận:
python -m pytest tests/test_agent_scorecard.py tests/test_vision_ocr.py -v

# 3. Khởi động lại dịch vụ:
docker compose up -d --build
# Hoặc: streamlit run src/dashboard/app.py
```

### Bước 5: Lập biên bản sự cố và báo cáo kỹ thuật
Ghi nhận vào sổ trực vận hành:
- Thời gian xảy ra sự cố và thời gian hoàn tất rollback.
- Nguyên nhân cốt lõi (Root Cause).
- Số lượng chứng từ bị ảnh hưởng (nếu có).
- Chữ ký xác nhận của Quản lý cửa hàng và Kỹ sư vận hành hệ thống.
