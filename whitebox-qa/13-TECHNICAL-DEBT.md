# BÁO CÁO DANH MỤC NỢ KỸ THUẬT (TECHNICAL DEBT CATALOG)
## HỆ THỐNG: BEVERAGE-OPS AI — CHI NHÁNH MIXUE 39 TÔN QUANG PHIỆT
**Mã tài liệu:** `WB-AUDIT-13-DEBT`  
**Phiên bản:** 2.0.0-PROD-AUDIT  
**Đối tượng:** Thống kê, định lượng chi phí, ước tính công sức khắc phục (Story Points/Man-Days) và rủi ro nếu trì hoãn

---

## 1. TỔNG QUAN DANH MỤC NỢ KỸ THUẬT (TECHNICAL DEBT OVERVIEW)

Nợ kỹ thuật trong hệ thống **BeverageOps AI** được phân loại thành 5 nhóm trụ cột:
1. **Nợ Kiến Trúc (Architectural Debt):** Ghép đôi chặt chẽ giữa UI và Engine, thiếu REST API Gateway, kế hoạch dự thảo lưu trong RAM.
2. **Nợ Mã Nguồn (Code Debt):** God Classes, 375 cảnh báo phân tích tĩnh, 22 blind excepts, giá trị gắn cứng ngày tháng.
3. **Nợ Cơ Sở Dữ Liệu & Lưu Trữ (Data Storage Debt):** Phân mảnh lưu trữ giữa SQLite và JSON file, thiếu Alembic migrations, thiếu cột `store_id`.
4. **Nợ Kiểm Thử (Testing Debt):** 2 bài test thất bại, thời gian chạy test suite quá chậm (~3.5 phút), thiếu mock fixtures.
5. **Nợ Hạ Tầng & DevOps (DevOps Debt):** Không có `requirements.txt`, không có `Dockerfile`, không có CI/CD tự động.

---

## 2. BẢNG ĐỊNH LƯỢNG NỢ KỸ THUẬT (TECHNICAL DEBT SIZING MATRIX)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TECHNICAL DEBT CATALOG & ESTIMATION                      │
├──────┬────────────────────┬─────────────────────────────┬──────────┬────────┤
│ STT  │ Hạng Mục Nợ Kỹ     │ Mô Tả Chi Tiết Vấn Đề       │ Điểm     │ Công   │
│      │ Thuật              │                             │ Story    │ Sức    │
├──────┼────────────────────┼─────────────────────────────┼──────────┼────────┤
│ 1    │ **DEBT-AUTH-01**   │ Chuyển SHA-256 sang bcrypt/ │ 3 SP     │ 1 Day  │
│      │                    │ argon2; bỏ plaintext cửa hậu│          │        │
├──────┼────────────────────┼─────────────────────────────┼──────────┼────────┤
│ 2    │ **DEBT-DATA-01**   │ Chuyển shift_reports.json   │ 5 SP     │ 2 Days │
│      │                    │ sang bảng SQL ShiftReport   │          │        │
├──────┼────────────────────┼─────────────────────────────┼──────────┼────────┤
│ 3    │ **DEBT-PERF-01**   │ Caching kết quả backtest và │ 3 SP     │ 1 Day  │
│      │                    │ dự báo D+1 (@cache_data)    │          │        │
├──────┼────────────────────┼─────────────────────────────┼──────────┼────────┤
│ 4    │ **DEBT-DEVOPS-01** │ Tạo requirements.txt,       │ 5 SP     │ 1.5 Day│
│      │                    │ Dockerfile và GitHub CI     │          │        │
├──────┼────────────────────┼─────────────────────────────┼──────────┼────────┤
│ 5    │ **DEBT-TEST-01**   │ Sửa 2 test fail, mock hàm   │ 3 SP     │ 1 Day  │
│      │                    │ dự báo giảm test time <15s  │          │        │
├──────┼────────────────────┼─────────────────────────────┼──────────┼────────┤
│ 6    │ **DEBT-RECON-01**  │ Sửa công thức tồn kho thiếu │ 3 SP     │ 1 Day  │
│      │                    │ Tồn đầu kỳ trong bom_engine │          │        │
├──────┼────────────────────┼─────────────────────────────┼──────────┼────────┤
│ 7    │ **DEBT-MIG-01**    │ Khởi tạo Alembic Migrations │ 5 SP     │ 1.5 Day│
│      │                    │ thay cho create_all()       │          │        │
├──────┼────────────────────┼─────────────────────────────┼──────────┼────────┤
│ 8    │ **DEBT-CODE-01**   │ Phân rã God Class           │ 8 SP     │ 3 Days │
│      │                    │ mixue_agent.py (1,652 dòng) │          │        │
├──────┼────────────────────┼─────────────────────────────┼──────────┼────────┤
│ 9    │ **DEBT-CODE-02**   │ Phân rã app.py (1,234 dòng) │ 5 SP     │ 2 Days │
│      │                    │ thành các View components   │          │        │
├──────┼────────────────────┼─────────────────────────────┼──────────┼────────┤
│ 10   │ **DEBT-LINT-01**   │ Dọn dẹp 375 cảnh báo ruff   │ 2 SP     │ 0.5 Day│
│      │                    │ (unused imports, asserts)   │          │        │
├──────┼────────────────────┼─────────────────────────────┼──────────┼────────┤
│ 11   │ **DEBT-API-01**    │ Xây dựng tầng FastAPI       │ 13 SP    │ 5 Days │
│      │                    │ Headless REST Gateway       │          │        │
├──────┼────────────────────┼─────────────────────────────┼──────────┼────────┤
│ 12   │ **DEBT-MULTI-01**  │ Bổ sung store_id vào toàn bộ│ 5 SP     │ 2 Days │
│      │                    │ bảng để sẵn sàng đa chuỗi   │          │        │
├──────┴────────────────────┴─────────────────────────────┴──────────┼────────┤
│ **TỔNG CỘNG NỢ KỸ THUẬT**                               │ **60 SP**│**21.5D**│
└─────────────────────────────────────────────────────────┴──────────┴────────┘
```

---

## 3. PHÂN TÍCH RỦI RO LÃI SUẤT NỢ (COMPOUNDING INTEREST RISK)

Nếu đội ngũ kỹ thuật quyết định đưa phần mềm vào vận hành chính thức mà **không trả bớt nợ kỹ thuật**, chi phí lãi suất (Technical Debt Interest) sẽ tăng theo cấp số nhân:

```
                  CHI PHÍ LÃI SUẤT NỢ KỸ THUẬT THEO THỜI GIAN
Chi Phí
  ▲
  │                                                  / (Sụp đổ khi scale 10 quán)
  │                                                /
  │                                              / 
  │                                      ┌─────/ (Lỗi đối soát POS, mất doanh thu)
  │                                ┌─────┘
  │                          ┌─────┘ (Bể vỡ khi deploy cloud vì thiếu Docker)
  │                    ┌─────┘
  │              ┌─────┘ (Lag 14s làm nhân viên không muốn dùng)
  │        ┌─────┘
  │  ┌─────┘ (Chi phí trả nợ hiện tại: 21.5 Man-Days)
  └──┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────► Thời Gian Vận Hành
    Tháng 1     Tháng 2     Tháng 3     Tháng 6
```

1. **Lãi Suất Tháng 1 (Vận hành tại 39 Tôn Quang Phiệt):**
   - Độ trễ 14 giây khiến nhân viên quầy bar nản lòng và từ bỏ việc hỏi Tuyết Vương AI về định lượng sơ chế, quay lại cách làm thủ công ước lượng bằng mắt.
   - Lỗi mất dữ liệu chốt ca trong file JSON khiến số liệu doanh thu cuối tháng không khớp với báo cáo kế toán.
2. **Lãi Suất Tháng 3 (Nâng Cấp Tính Năng Mới):**
   - Mỗi lần sửa code giao diện hoặc thêm món mới vào menu, God Class `mixue_agent.py` và `app.py` sẽ phát sinh lỗi hồi quy (Regression Bugs). Chi phí kiểm thử thủ công và debug sẽ chiếm 60% thời gian của đội ngũ phát triển.
3. **Lãi Suất Tháng 6 (Mở Rộng Thêm 10 Cửa Hàng Mới):**
   - Hệ thống hoàn toàn tê liệt vì không có cột `store_id` trong thẻ kho 31 ngày, CSDL SQLite bị `database is locked` liên tục khi có 10 cửa hàng cùng đẩy dữ liệu chốt ca. Chi phí viết lại hệ thống lúc này sẽ gấp 4 lần chi phí refactor ban đầu.

---

## 4. CHIẾN LƯỢC TRẢ NỢ THEO GIAI ĐOẠN (DEBT REPAYMENT STRATEGY)

- **Giai Đoạn 1 (Sprint 1 - Immediate Hardening - 5.5 Days):**
  Tập trung trả các khoản nợ nguy hiểm nhất: `DEBT-AUTH-01` (Bảo mật), `DEBT-DATA-01` (Toàn vẹn chốt ca), `DEBT-PERF-01` (Caching dự báo), `DEBT-DEVOPS-01` (Docker & Requirements), `DEBT-TEST-01` (Sửa 2 test fail).
- **Giai Đoạn 2 (Sprint 2 - Code Quality & Reliability - 6 Days):**
  Trả các khoản nợ mã nguồn: `DEBT-RECON-01` (Sửa công thức tồn kho), `DEBT-MIG-01` (Alembic), `DEBT-CODE-02` (Tách app.py), `DEBT-LINT-01` (Sửa linter).
- **Giai Đoạn 3 (Sprint 3 - Architecture Evolution - 10 Days):**
  Xây dựng nền tảng lâu dài: `DEBT-CODE-01` (Tách mixue_agent.py), `DEBT-API-01` (FastAPI Gateway) và `DEBT-MULTI-01` (Multi-store support).
