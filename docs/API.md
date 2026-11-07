# REST API (backend)

`src/api/main.py` — FastAPI, dùng **cùng engine** với giao diện Streamlit (cùng cơ sở dữ liệu, cùng luật
phân quyền, cùng AI). Giao diện hiện tại giữ nguyên; frontend mới (React, app điện thoại, máy POS) gọi API này.

```
uvicorn src.api.main:app --host 0.0.0.0 --port 8000     # tài liệu tương tác: http://localhost:8000/docs
docker compose up api                                     # hoặc chạy cùng app + Postgres
```

## Kiến trúc
```
 Frontend (Streamlit hiện tại | React / mobile sau này)
                │  HTTPS + Bearer token
                ▼
 FastAPI  /api/v1/stores/{store_id}/…   ← xác thực, phân quyền, phạm vi cửa hàng
                │
 Engine dùng chung: agent LangGraph · OCR · tra cứu SOP (learning-to-rank + vector) · kho · dự báo · phê duyệt
                │
 Cơ sở dữ liệu (SQLite / PostgreSQL)
```

## Các endpoint
| Nhóm | Endpoint | Quyền |
|---|---|---|
| Hệ thống | `GET /api/v1/health` | — |
| Đăng nhập | `POST /api/v1/auth/login` → token · `POST /auth/logout` · `GET /me` · `GET /stores` | mọi tài khoản |
| Doanh thu | `GET /stores/{id}/sales?start&end` · `GET /stores/{id}/shift-revenue?q=` | Quản lý |
| Kho | `GET /stores/{id}/inventory` · `GET /stores/{id}/stock-matrix?year&month` | Quản lý |
| Dự báo | `GET /stores/{id}/forecast?target_date&horizon_days` | Quản lý |
| Tra cứu | `GET /stores/{id}/sop/search?q=` · `GET /stores/{id}/recipes/{code}` | mọi tài khoản |
| Chốt ca | `POST /stores/{id}/ocr/read` (1–5 ảnh, `business_date`, `shift`) → **chỉ trả gợi ý, không lưu** | mọi tài khoản |
| Phê duyệt | `GET /stores/{id}/approvals` · `POST /stores/{id}/approvals/{shift\|stock\|plan}/{item_id}` `{approve}` | Quản lý |
| Trợ lý | `POST /stores/{id}/chat` `{message}` · `POST /stores/{id}/chat/approval` `{approve}` | chat: mọi tài khoản; duyệt: Quản lý |
| Chi phí AI | `GET /stores/{id}/ai-usage?days=7` | Quản lý |

Quy tắc giữ nguyên như app: danh tính và vai trò lấy từ token (không tin dữ liệu trong body); đọc ảnh chỉ là gợi ý,
doanh thu chỉ được ghi khi Quản lý duyệt; tài khoản phải đổi mật khẩu thì bị chặn cho tới khi đổi.

## Mở rộng nhiều cửa hàng
Mọi route nghiệp vụ đã nằm dưới `/stores/{store_id}`; việc "người dùng nào xem được cửa hàng nào" nằm ở **một**
dependency (`store_access`). Bước tiếp theo khi có chuỗi cửa hàng:
1. bảng `stores` và bảng `user_stores` (người dùng ↔ cửa hàng, vai trò theo từng cửa hàng);
2. thêm cột `store_id` vào các bảng giao dịch (doanh thu, chốt ca, kho, kế hoạch) và lọc theo nó trong engine;
3. `store_access` đọc `user_stores` thay vì danh sách một cửa hàng; PostgreSQL thay SQLite.
Không phải đổi đường dẫn API hay frontend.
