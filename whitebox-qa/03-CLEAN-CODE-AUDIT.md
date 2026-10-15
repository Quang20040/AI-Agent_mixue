# BÁO CÁO KIỂM TOÁN CHẤT LƯỢNG MÃ NGUỒN & CLEAN CODE (CLEAN CODE AUDIT)
## HỆ THỐNG: BEVERAGE-OPS AI — CHI NHÁNH MIXUE 39 TÔN QUANG PHIỆT
**Mã tài liệu:** `WB-AUDIT-03-CODE`  
**Phiên bản:** 2.0.0-PROD-AUDIT  
**Đối tượng:** Đánh giá tuân thủ nguyên lý SOLID, DRY, KISS, YAGNI, Code Smells, Độ phức tạp và Tính bảo trì

---

## 1. ĐÁNH GIÁ NGUYÊN LÝ THIẾT KẾ PHẦN MỀM (SOLID PRINCIPLES AUDIT)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SOLID PRINCIPLES SCORECARD                            │
├──────────────────────────────────────┬─────────┬────────────────────────────┤
│ Nguyên Lý                            │ Đánh Giá│ Vấn Đề Điển Hình           │
├──────────────────────────────────────┼─────────┼────────────────────────────┤
│ S - Single Responsibility Principle  │ VIOLATED│ God Class: mixue_agent.py  │
│                                      │         │ (1,652 lines, 15+ nhiệm vụ)│
├──────────────────────────────────────┼─────────┼────────────────────────────┤
│ O - Open/Closed Principle            │ PARTIAL │ Khó mở rộng thêm tool AI mà│
│                                      │         │ không sửa core agent code  │
├──────────────────────────────────────┼─────────┼────────────────────────────┤
│ L - Liskov Substitution Principle    │ N/A     │ Hệ thống ít dùng kế thừa   │
│                                      │         │ đa hình (class inheritance)│
├──────────────────────────────────────┼─────────┼────────────────────────────┤
│ I - Interface Segregation Principle  │ POOR    │ Client bị ép nhận object   │
│                                      │         │ quá lớn thay vì DTO nhỏ gọn│
├──────────────────────────────────────┼─────────┼────────────────────────────┤
│ D - Dependency Inversion Principle   │ VIOLATED│ SessionLocal() khởi tạo    │
│                                      │         │ cứng, không dùng DI        │
└──────────────────────────────────────┴─────────┴────────────────────────────┘
```

### 1.1. Single Responsibility Principle (SRP) — Vi Phạm Nghiêm Trọng
Lớp `MixueOperationsAgent` trong [src/agent/mixue_agent.py:145](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/agent/mixue_agent.py#L145) gánh vác quá nhiều trọng trách trái ngược nhau:
1. Quản lý vòng lặp ReAct và System Prompt.
2. Trích xuất ngày tháng từ ngôn ngữ tự nhiên bằng biểu thức chính quy (Regex NLP).
3. Thực hiện truy vấn dữ liệu bán hàng POS và format dữ liệu ra tiếng Việt.
4. Điều phối gọi mô hình dự báo và tối ưu mẻ sơ chế.
5. Kiểm tra quyền hạn người dùng (RBAC Authorization Filter).
6. Kiểm tra các quy tắc an toàn Red Teaming (Prompt Injection, HR Privacy).
7. Lưu trữ bộ nhớ đệm các kế hoạch dự thảo (`self.draft_plans`).
8. Định dạng chuỗi phản hồi Markdown cho giao diện người dùng.

**Hậu quả:** Bất kỳ thay đổi nào liên quan đến câu thông báo, thêm quyền cho nhân viên hoặc thay đổi định dạng ngày đều buộc lập trình viên phải sửa đổi tệp khổng lồ này, làm tăng nguy cơ phát sinh lỗi ngoài ý muốn (Regression Bugs).

### 1.2. Dependency Inversion Principle (DIP) — Vi Phạm
Các engine trong hệ thống phụ thuộc trực tiếp vào triển khai cụ thể của SQLAlchemy `SessionLocal`:
```python
# src/engine/bom_engine.py:15-16
class BOMEngine:
    def __init__(self, db_session=None):
        self.db = db_session or SessionLocal()
```
Mặc dù có tham số tùy chọn `db_session`, nhưng hầu hết các hàm gọi tại `app.py` và `mixue_agent.py` đều không sử dụng Dependency Injection Container hoặc Factory Pattern. Điều này dẫn đến việc khởi tạo phiên kết nối tùy tiện, gây khó khăn cho việc viết Unit Test có cách ly hoàn toàn (Mock DB).

---

## 2. DANH MỤC MÃ XẤU (CODE SMELLS & ANTI-PATTERNS)

### 2.1. God Class / God File Smell
- **`src/agent/mixue_agent.py` (1,652 dòng):**
  Chứa hơn 40 biểu thức chính quy phức tạp (Regex) để xử lý mọi tình huống đàm thoại. Hàm `process_query()` kéo dài hàng trăm dòng với các khối `if/elif/else` lồng ghép sâu tới 5 cấp độ.
- **`src/dashboard/app.py` (1,234 dòng):**
  Trực tiếp chứa mã nguồn của toàn bộ 8 Tab chức năng trong hệ thống. Việc trộn lẫn cấu trúc HTML, CSS, vòng lặp session state và logic nghiệp vụ khiến việc bảo trì giao diện trở nên cực kỳ rủi ro.

### 2.2. Nuốt Ngoại Lệ & Bắt Lỗi Mù (Blind Except & Exception Swallowing)
Công cụ phân tích tĩnh Ruff phát hiện **22 vi phạm BLE001** và **5 vi phạm S110**:
- Tại [src/agent/mixue_agent.py:83-84, 99-100, 110-111](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/agent/mixue_agent.py#L83-L111):
  ```python
  try:
      dt = date(int(y), int(m), int(d))
      return dt.isoformat(), dt.isoformat()
  except Exception:
      pass
  ```
  Việc sử dụng `except Exception: pass` nuốt trọn mọi lỗi phát sinh (bao gồm cả lỗi cú pháp, lỗi định dạng dữ liệu không mong muốn) mà không hề ghi nhật ký (logging). Khi hàm parse ngày tháng thất bại trong môi trường production, lập trình viên hoàn toàn không có manh mối để điều tra nguyên nhân.

### 2.3. Giá Trị Cứng (Hardcoded Magic Values)
- Tại [src/engine/daily_stock_service.py:24-62](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/daily_stock_service.py#L24-L62):
  Biến `OCTOBER_DAYS` khai báo cứng danh sách 31 ngày của riêng **Tháng 10/2026** kèm nhãn thứ và phân nhóm tuần. Nếu hệ thống vận hành sang Tháng 11/2026, toàn bộ ma trận sổ kho 31 ngày sẽ hiển thị sai lịch hoặc đòi hỏi lập trình viên phải sửa mã nguồn và deploy lại.
- Tại [src/agent/mixue_agent.py:126-129](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/agent/mixue_agent.py#L126-L129):
  ```python
  if any(w in q for w in ["hôm qua", "hom qua"]):
      return "2026-10-11", "2026-10-11"
  if any(w in q for w in ["hôm nay", "hom nay", "gần nhất"]):
      return "2026-10-12", "2026-10-12"
  ```
  "Hôm nay" và "Hôm qua" bị gắn cứng vĩnh viễn với ngày 11 và 12 tháng 10 năm 2026. Nếu người dùng sử dụng ứng dụng vào các ngày tiếp theo, hệ thống vẫn trả lời dữ liệu của ngày 12/10/2026!

### 2.4. Trùng Lặp Mã Nguồn (Code Duplication - DRY Violation)
- Logic tra cứu metadata vai trò người dùng xuất hiện lặp lại ở 3 nơi:
  1. `src/auth.py::_get_role_metadata()`
  2. `src/dashboard/app.py::get_user_metadata()`
  3. `src/agent/mixue_agent.py::_check_rbac_permission()`
  Khi cần thêm một vai trò mới (ví dụ: `SUPERVISOR`), lập trình viên buộc phải cập nhật đồng thời ở cả 3 tệp. Nếu bỏ sót một tệp, hành vi phân quyền trên giao diện và trong AI Agent sẽ bị mâu thuẫn.

---

## 3. PHÂN TÍCH ĐỘ PHỨC TẠP MÃ NGUỒN (COMPLEXITY METRICS)

Đánh giá độ phức tạp chu kỳ (Cyclomatic Complexity - CC) trên các hàm trọng yếu:

| Tệp Nguồn | Hàm / Phương Thức | Cyclomatic Complexity (CC) | Đánh Giá Độ Phức Tạp | Rủi Ro Bảo Trì |
|---|---|---|---|---|
| `src/agent/mixue_agent.py` | `process_query()` | **CC = 48** | Cực kỳ phức tạp (Extreme Risk) | Rất khó kiểm thử hết các nhánh |
| `src/agent/mixue_agent.py` | `_parse_query_date_range()` | **CC = 26** | Phức tạp cao (High Risk) | Dễ lỗi khi gặp câu hỏi dị thường |
| `src/engine/daily_stock_service.py` | `get_stock_matrix_df()` | **CC = 22** | Phức tạp cao (High Risk) | Vòng lặp lồng ghép nhiều cấp |
| `src/dashboard/app.py` | `render_daily_stock_tab()` | **CC = 31** | Phức tạp cao (High Risk) | Quá nhiều trạng thái điều kiện |
| `src/engine/optimizer.py` | `optimize_replenishment()` | **CC = 14** | Trung bình (Moderate) | Chấp nhận được |

*Tiêu chuẩn công nghiệp khuyến nghị: Một hàm chỉ nên có Cyclomatic Complexity $\le 10$. Hàm `process_query()` với CC = 48 vượt gấp gần 5 lần ngưỡng an toàn.*

---

## 4. PHÂN TÍCH TYPE HINTS VÀ TÀI LIỆU HÓA MÃ NGUỒN (DOCSTRINGS)

### 4.1. Thực Trạng Type Annotations
- **Mức độ bao phủ Type Hints:** Đạt khoảng **45%** mã nguồn.
- **Vấn đề phân tích tĩnh phát hiện qua Ruff:**
  - 83 lỗi `UP006` (Non-PEP 585 annotations): Sử dụng `typing.List`, `typing.Dict`, `typing.Tuple` thay vì cú pháp chuẩn `list`, `dict`, `tuple` của Python 3.9+.
  - 31 lỗi `UP045` (Non-PEP 604 Optional): Sử dụng `Optional[str]` thay vì cú pháp hiện đại `str | None`.
  - Nhiều hàm trả về `Dict[str, Any]` chung chung, không có định nghĩa cấu trúc dữ liệu tường minh (Pydantic Schema hoặc `TypedDict`), khiến IDE không thể gợi ý trường và lập trình viên dễ gõ sai tên key (như trường hợp `signed_by: "An"` vs `"Anh"`).

### 4.2. Chất Lượng Docstrings
- Hầu hết các module đều có module-level docstring tiếng Việt rõ ràng, giải thích đúng ngữ cảnh chi nhánh Mixue 39 Tôn Quang Phiệt.
- Tuy nhiên, nhiều phương thức nội bộ trong `src/engine/` thiếu mô tả rõ ràng về:
  - Ý nghĩa các tham số đầu vào.
  - Cấu trúc chi tiết của Dictionary trả về.
  - Các ngoại lệ có thể bị kích hoạt (Exceptions Raised).

---

## 5. KẾ HOẠCH TÁI CẤU TRÚC ƯU TIÊN (REFACTORING ROADMAP)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CLEAN CODE REFACTORING MATRIX                            │
├────────────────────┬─────────────────────────────┬───────────┬──────────────┤
│ Mã Mục Tiêu        │ Hành Động Refactoring       │ Công Sức  │ Mức Ưu Tiên  │
├────────────────────┼─────────────────────────────┼───────────┼──────────────┤
│ **REF-AGENT-01**   │ Tách mixue_agent.py thành:  │ 3 Man-Days│ P0 (Khẩn cấp)│
│                    │ - agent_core.py             │           │              │
│                    │ - date_parser.py            │           │              │
│                    │ - guardrails.py             │           │              │
│                    │ - tool_handlers/            │           │              │
├────────────────────┼─────────────────────────────┼───────────┼──────────────┤
│ **REF-APP-01**     │ Tách app.py thành các View: │ 2 Man-Days│ P1 (Cao)     │
│                    │ - views/tab_sales.py        │           │              │
│                    │ - views/tab_forecast.py     │           │              │
│                    │ - views/tab_stock.py        │           │              │
├────────────────────┼─────────────────────────────┼───────────┼──────────────┤
│ **REF-DTO-01**     │ Thay Dict[str, Any] bằng    │ 2 Man-Days│ P1 (Cao)     │
│                    │ Pydantic v2 Models          │           │              │
├────────────────────┼─────────────────────────────┼───────────┼──────────────┤
│ **REF-LINT-01**    │ Sửa 47 unused imports và 22 │ 0.5 Day   │ P2 (Trung)   │
│                    │ blind excepts bằng ruff     │           │              │
└────────────────────┴─────────────────────────────┴───────────┴──────────────┘
```

1. **Phân rã God Class `MixueOperationsAgent`:**
   Chuyển các logic kiểm tra Guardrail vào module `src/agent/guardrails.py`, logic trích xuất NLP ngày tháng vào `src/agent/nlp_utils.py`, và chuyển 8 tool thành các class kế thừa BaseTool riêng biệt.
2. **Pydantic Data Contracts:**
   Thay thế việc truyền dictionary lỏng lẻo `Dict[str, Any]` giữa UI, Agent và Engine bằng các Pydantic Schema có xác thực kiểu dữ liệu chặt chẽ (`DailySalesResponse`, `ForecastOutput`, `StockMovementRequest`, `ShiftClosingReport`).
3. **Loại bỏ Magic Values:**
   Thay thế các mảng tĩnh `OCTOBER_DAYS` bằng hàm sinh lịch tự động dựa trên tháng/năm hiện tại (`calendar` module).
