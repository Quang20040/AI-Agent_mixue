# Báo cáo Benchmark v1.0 — BeverageOps AI (Mixue Operations)

> **Dự án:** BeverageOps AI — Hệ thống Điều phối Vận hành Cửa hàng Mixue  
> **Thời điểm đánh giá:** 13/10/2026  
> **Phạm vi dữ liệu:** 30 ngày kinh doanh chuẩn hóa (13/09/2026 – 12/10/2026), 39 món menu, 73 nguyên liệu, 120 định lượng BOM.

---

## 1. Tóm tắt kết quả cốt lõi (Executive Summary)

| Hạng mục kiểm thử | Đối tượng | Kết quả đạt được | Trạng thái Checkpoint |
|---|---|---|---|
| **Dữ liệu & BOM (CP1)** | Schema & 30-day Audit | 0 lỗi, 0 cảnh báo, 1.170 bản ghi sales hợp lệ | **PASSED (CP1)** |
| **Dự báo nhu cầu D+1 (CP2)** | 3 Mô hình Baseline (15 ngày backtest) | **Moving Average 7d đạt WAPE = 20.27%** (tốt nhất) | **PASSED (CP2)** |
| **Tối ưu & Thẩm định (CP3)** | Topping Prep & PO Draft + Validator | 100% tuân thủ quy cách mẻ & đóng gói, 0 lượng âm | **PASSED (CP3)** |
| **Agent & Phân quyền (CP4)** | RBAC & Tool Orchestration | Chặn 100% quyền duyệt từ Staff; duyệt hợp lệ bởi Manager/Owner | **PASSED (CP4)** |
| **Golden Scenarios (CP5)** | 30 kịch bản vận hành thực tế | **30/30 Đạt (100.0%)** | **PASSED (CP5)** |
| **Unit & Integration Tests** | Pytest Test Suite | **15/15 Tests Passed (100%)** | **PASSED (CP6)** |

---

## 2. Benchmark Mô hình Dự báo Nhu cầu (Forecasting Baselines)

Phương pháp kiểm thử: **Rolling-Origin Backtesting 1-day ahead** từ ngày thứ 15 (28/09/2026) đến ngày thứ 30 (12/10/2026), đánh giá trên toàn bộ 39 SKU (tổng cộng 585 điểm dự báo đối chiếu thực tế).

### 2.1. Bảng so sánh chỉ số sai số tổng hợp

| Mô hình (Model) | MAE (Ly) | WAPE (%) | Bias (%) | Tổng sản lượng thực tế | Tổng sản lượng dự báo | Đánh giá |
|---|---|---|---|---|---|---|
| **Seasonal Naive (7 ngày)** | 10.35 ly | 25.24% | +0.22% | 23.957 ly | 24.010 ly | Baseline chuẩn theo chu kỳ tuần |
| **Simple Moving Average (7 ngày)** | **8.31 ly** | **20.27%** | **+0.32%** | **23.957 ly** | **24.034 ly** | **Tối ưu nhất (Sai số thấp nhất, ổn định)** |
| **Day-of-Week Moving Average (3w)** | 8.92 ly | 21.76% | -0.78% | 23.957 ly | 23.770 ly | Tốt cho các ngày biến động cuối tuần |

> **Nhận định:** Với mẫu dữ liệu 30 ngày bán lẻ F&B, **Moving Average (7 ngày)** cho thấy khả năng chống nhiễu tốt nhất, giảm WAPE xuống mức 20.27%, không bị lệch tổng thể (Bias chỉ +0.32%).

---

## 3. Benchmark Động cơ Sơ chế Topping & Đề xuất Nhập hàng (Optimization Engine)

### 3.1. Kế hoạch sơ chế Topping theo mẻ
- Áp dụng công thức: $Prep = \text{roundUpToBatch}(\max(0, \hat{D} \times (1 + \text{Buffer}) - \text{Usable}))$.
- **Tuân thủ quy cách mẻ:** 100% số mẻ trà (TP02, TP03, TP04) tròn theo bội số 5.000 ml; trân châu và thạch tròn theo bội số 1.000 g.
- **Tuân thủ thời gian bảo quản (SOP Mixue):**
  - Trân châu chín (`NL06`): Tối đa 4 giờ.
  - Hồng trà lạnh (`TP02`), Trà xanh lạnh (`TP03`): Tối đa 4 giờ / đổ bỏ cuối ngày.
  - Thạch dừa (`NL07`), Thạch đường đen (`NL08`): Đổ bỏ cuối ngày (không chuyển tồn sang hôm sau).

### 3.2. Đề xuất đơn đặt hàng (Replenishment PO)
- Tự động phân loại nguyên liệu mua ngoài (loại trừ các bán thành phẩm tự làm tại quán như nước trà ủ, kem làm tại quán).
- Tự động làm tròn số lượng theo quy cách bao/gói/thùng chuẩn (1.000 g / 1.000 ml / 500 cái).
- Phát hiện kịp thời các mặt hàng rơi vào trạng thái `CRITICAL` (dưới Lead Time 2 ngày).

---

## 4. Benchmark An toàn Vận hành & Phân quyền (Governance & RBAC)

| Tiêu chí | Kỳ vọng | Thực tế đo được | Kết luận |
|---|---|---|---|
| **Chặn quyền duyệt của Staff** | Staff gọi phê duyệt bị từ chối `UNAUTHORIZED` | 100% bị từ chối | ✅ An toàn tuyệt đối |
| **Quyền duyệt của Manager/Owner** | Quản lý hoặc Chủ quán duyệt kế hoạch hợp lệ | 100% được ghi nhận audit trail | ✅ Hoạt động đúng nghiệp vụ |
| **Tự động đặt hàng độc lập (Autonomous Buying)** | AI bị cấm tự đặt hàng cho nhà cung cấp | Hệ thống chỉ xuất bản dự thảo `draft`, bắt buộc human approval | ✅ Tuân thủ ADR-006 |
| **Trích dẫn bằng chứng (Evidence Traceability)** | Mọi kết luận phải gắn `source_refs` | 100% phản hồi có nguồn bảng dữ liệu hoặc công thức | ✅ Không ảo giác số liệu |

---

## 5. Kết quả đánh giá Golden Cases (30 Scenarios)

- **Số lượng kịch bản:** 30 scenarios.
- **Tỷ lệ vượt qua:** **30/30 (100.0%)**.
- **Các nhóm kịch bản:**
  1. Doanh số & phân tích bán hàng: 2/2 đạt.
  2. Dự báo nhu cầu menu & món lẻ: 2/2 đạt.
  3. Kế hoạch sơ chế theo mẻ: 3/3 đạt.
  4. Đề xuất đơn nhập hàng: 2/2 đạt.
  5. Phân tích hao hụt & hủy topping: 2/2 đạt.
  6. Giải mã tem dán ly 5 chữ số: 3/3 đạt.
  7. Tra cứu công thức định lượng (BOM): 3/3 đạt.
  8. Phân quyền RBAC (Staff vs Manager/Owner): 3/3 đạt.
  9. Kiểm định kế hoạch độc lập (Validator): 4/4 đạt.
  10. Đối soát tồn kho & chênh lệch BOM: 1/1 đạt.
  11. Tuân thủ an toàn thực phẩm (SOP hold time): 2/2 đạt.
  12. Chống prompt injection & trích dẫn evidence: 3/3 đạt.
