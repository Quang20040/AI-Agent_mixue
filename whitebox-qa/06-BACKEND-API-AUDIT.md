# BÁO CÁO KIỂM TOÁN TẦNG DỊCH VỤ VÀ GIAO DIỆN LẬP TRÌNH (BACKEND & API AUDIT)
## HỆ THỐNG: BEVERAGE-OPS AI — CHI NHÁNH MIXUE 39 TÔN QUANG PHIỆT
**Mã tài liệu:** `WB-AUDIT-06-API`  
**Phiên bản:** 2.0.0-PROD-AUDIT  
**Đối tượng:** Đánh giá cấu trúc Service Layer, vòng đời giao dịch (Transactions), quản lý kết nối, Logging và thiếu hụt chuẩn REST API

---

## 1. ĐÁNH GIÁ CẤU TRÚC SERVICE LAYER & API ABSTRACTION

### 1.1. Sự Thiếu Hụt Hoàn Toàn Chuẩn Giao Tiếp Headless API (No REST/GraphQL API)
- **Thực trạng kiến trúc:**
  Trong toàn bộ codebase của `BeverageOps AI`, **hoàn toàn không có bất kỳ endpoint REST API (FastAPI / Flask / Django) nào**.
  Hệ thống đang hoạt động dưới dạng **Internal In-process Python Calls**: Giao diện Streamlit gọi trực tiếp các hàm Python trong `src/engine/` và `src/auth.py`.
- **Rủi ro vận hành & Hạn chế tích hợp:**
  1. **Không thể tích hợp máy POS tự động:** Máy tính tiền POS tại quầy Mixue 39 Tôn Quang Phiệt không thể gửi webhook hoặc REST request đẩy đơn hàng thời gian thực (Real-time Sales Push) vào BeverageOps AI. Hiện tại, dữ liệu POS phải được nạp thông qua script chạy tay (`populate_mixue_operational_data.py`) hoặc import gián tiếp.
  2. **Không thể phát triển ứng dụng di động (Mobile App):** Quản lý hoặc Chủ quán không thể sử dụng ứng dụng di động để duyệt lệnh xuất kho hoặc xem báo cáo doanh thu từ xa vì không có API Gateway cung cấp dữ liệu qua JSON.
  3. **Không thể tích hợp nhà cung cấp:** Đơn đặt hàng nhập kho (PO) được tạo bởi `OptimizerEngine` chỉ có thể xem trên màn hình, không thể tự động bắn API sang hệ thống kho tổng của chuỗi Mixue.

---

## 2. QUẢN LÝ GIAO DỊCH VÀ VÒNG ĐỜI KẾT NỐI (TRANSACTION & CONNECTION MANAGEMENT)

### 2.1. Mô Hình Mở / Đóng Session Tùy Tiện (Ad-hoc Session Creation)
- Tại [src/database.py:31-36](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/database.py#L31-L36):
  ```python
  def get_db():
      db = SessionLocal()
      try:
          yield db
      finally:
          db.close()
  ```
  Hàm generator `get_db()` được khai báo theo chuẩn FastAPI Dependency Injection, nhưng **trong thực tế mã nguồn không có FastAPI**!
- Thay vào đó, trong các dịch vụ như [src/engine/daily_stock_service.py](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/daily_stock_service.py) và [src/auth.py](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/auth.py), mỗi hàm lại tự tay khởi tạo một phiên kết nối mới:
  ```python
  def approve_stock_request(request_id: int, admin_username: str):
      db = SessionLocal()
      try:
          ...
          db.commit()
      except Exception as e:
          db.rollback()
      finally:
          db.close()
  ```
- **Hậu quả kiến trúc:**
  - **Connection Overhead:** Mỗi tác vụ nhỏ (đọc một ô trong bảng kho, lấy tên nhân viên) đều mở một session mới và đóng ngay, làm tăng chi phí handshake và connection pool churn.
  - **Thiếu Transaction Phân Tán (Unit of Work):** Nếu một luồng nghiệp vụ phức tạp đòi hỏi phải ghi đồng thời vào bảng `daily_stock_movements` và cập nhật bảng `stock_counts`, việc mỗi hàm tự commit/rollback độc lập sẽ phá vỡ tính nguyên tử (Atomicity). Nếu hàm thứ hai thất bại, dữ liệu của hàm thứ nhất đã bị commit vào DB và không thể rollback được.

---

## 3. ĐÁNH GIÁ HỆ THỐNG GHI NHẬT KÝ & GIÁM SÁT (LOGGING & OBSERVABILITY AUDIT)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       OBSERVABILITY MATURITY AUDIT                          │
├────────────────────┬──────────┬─────────────────────────────────────────────┤
│ Tiêu Chí           │ Trạng    │ Hiện Trạng & Rủi Ro                         │
│                    │ Thái     │                                             │
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ 1. Standard Logger │ VIOLATED │ Dùng lệnh print() thô sơ; không dùng        │
│                    │          │ logging.getLogger(__name__)                 │
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ 2. Log Levels      │ KHÔNG CÓ │ Không phân cấp DEBUG, INFO, WARNING, ERROR  │
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ 3. Structured Log  │ KHÔNG CÓ │ Log dạng plain text, không có JSON format   │
│                    │          │ cho ELK / CloudWatch / Datadog              │
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ 4. Correlation ID  │ KHÔNG CÓ │ Không có Request-ID để truy vết luồng gọi   │
├────────────────────┼──────────┼─────────────────────────────────────────────┤
│ 5. Audit Trail     │ TỐT MỘT  │ Bảng daily_stock_movements có recorded_by   │
│                    │ PHẦN     │ và approved_by; nhưng thiếu bảng audit chung│
└────────────────────┴──────────┴─────────────────────────────────────────────┘
```

- Tại [src/engine/shift_service.py:60, 72, 285](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/shift_service.py#L60):
  ```python
  except Exception as e:
      print(f"[shift_service] Lỗi đọc {SHIFT_DATA_FILE}: {e}")
  ```
  Việc sử dụng lệnh `print()` thô sơ khiến các thông báo lỗi bị trôi vào stdout của console, không lưu được timestamp, không có stack trace chi tiết và không thể đẩy sang các hệ thống giám sát tập trung (APM / Sentry). Khi xảy ra lỗi âm thầm trên server production, đội ngũ kỹ thuật hoàn toàn không nhận được cảnh báo.

---

## 4. TÍNH BẢO ĐẢM TÍNH ĐƠN NHẤT (IDEMPOTENCY & CONCURRENCY CONTROL)

### 4.1. Lỗ Hổng Thiếu Khóa Chống Trùng Lặp (Idempotency Flaw)
- Hàm `create_stock_request()` tại [src/engine/daily_stock_service.py:240-275](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/daily_stock_service.py#L240-L275) nhận các tham số: `business_date`, `ingredient_id`, `movement_type`, `quantity`, `recorded_by`.
- **Thiếu sót:** Hàm này không nhận `idempotency_key` (UUID v4 do client sinh ra). Nếu client gửi lại cùng một request trong vòng 2 giây (do nhân viên bấm nút 2 lần hoặc mạng bị trễ), hàm sẽ thực hiện `INSERT` một bản ghi mới với ID tự tăng khác nhau.
- **Rủi ro:** Số lượng hàng xuất ra quầy bar bị nhân đôi trong sổ kho 31 ngày mà không có bất kỳ cơ chế nào ngăn chặn.

---

## 5. THIẾT KẾ ĐỀ XUẤT REST API CHUẨN DOANH NGHIỆP (TARGET REST API SPECIFICATION)

Để chuẩn bị cho việc tích hợp POS tự động và phát hành ứng dụng di động cho chi nhánh, hệ thống cần bổ sung tầng FastAPI với bộ hợp đồng API chuẩn OpenAPI 3.0:

```yaml
openapi: 3.0.3
info:
  title: BeverageOps AI Gateway API
  version: 1.0.0
paths:
  /api/v1/auth/login:
    post:
      summary: Xác thực người dùng và cấp phát JWT token
      responses:
        '200': { description: Đăng nhập thành công, trả về access_token và role }
        '401': { description: Sai tài khoản hoặc mật khẩu }

  /api/v1/pos/sync-sales:
    post:
      summary: Đồng bộ dữ liệu bán hàng POS thời gian thực
      security: [{ BearerAuth: [] }]
      requestBody:
        content:
          application/json:
            schema: { $ref: '#/components/schemas/POSSyncPayload' }
      responses:
        '201': { description: Ghi nhận doanh thu thành công }

  /api/v1/stock/requests:
    post:
      summary: Tạo yêu cầu lệnh xuất / nhập kho (Maker-Checker)
      parameters:
        - in: header
          name: X-Idempotency-Key
          required: true
          schema: { type: string, format: uuid }
      responses:
        '201': { description: Lệnh đã được tạo ở trạng thái PENDING hoặc APPROVED }

  /api/v1/stock/requests/{request_id}/approve:
    put:
      summary: Quản lý phê duyệt lệnh xuất / nhập kho
      responses:
        '200': { description: Duyệt thành công, cập nhật thẻ kho }
        '403': { description: Từ chối quyền - yêu cầu tài khoản Quản lý }

  /api/v1/agent/chat:
    post:
      summary: Gửi câu hỏi đàm thoại tới Tuyết Vương AI
      responses:
        '200': { description: Trả về câu trả lời Markdown, công cụ đã gọi và bằng chứng số liệu }
```

### Lộ Trình Triển Khai Backend:
1. **Tuần 1:** Xây dựng khung ứng dụng FastAPI trong thư mục `src/api/` tái sử dụng các engine hiện có.
2. **Tuần 2:** Chuyển đổi cơ chế xác thực sang chuẩn OAuth2 Bearer Token (JWT) thay thế cho Session State.
3. **Tuần 3:** Bổ sung Middleware logging có gắn `request_id` (Correlation ID) và cấu hình log format JSON chuẩn.
4. **Tuần 4:** Bổ sung cơ chế kiểm tra `X-Idempotency-Key` lưu trong Redis cho tất cả các endpoint ghi dữ liệu (`POST`, `PUT`, `DELETE`).
