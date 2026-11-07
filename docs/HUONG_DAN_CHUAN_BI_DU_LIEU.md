# Hướng dẫn chuẩn bị dữ liệu thật — BeverageOps AI / Mixue pilot

> **Data Preparation Playbook v1.0 · 13/10/2026**  
> Đầu vào **đã xác nhận:** số lượng bán từng món/ngày trong 30 ngày, doanh thu, giá bán, BOM, tồn kho, nhập hàng, kiểm kê; ghi nhận lượng topping **đã chuẩn bị và đã hủy cuối ngày**.  
> **Không có:** doanh số từng giờ/ca.  
> Mục tiêu: tạo dữ liệu phân tích có thể truy vết để dự báo theo **ngày**, đề xuất topping/nhập nguyên liệu và đánh giá kết quả.

## 1. Kết quả phải có sau bước chuẩn bị

```text
input nguồn (được phép sử dụng)
    ├── Báo cáo bán từng sản phẩm theo ngày (30 ngày)
    ├── Danh mục sản phẩm + giá bán
    ├── BOM/recipe từng món
    ├── Danh mục nguyên liệu
    ├── Nhập hàng và kiểm kê
    └── Lượng topping chuẩn bị/hủy cuối ngày
               |
               v
      Mapping & Data Validation
               |
               v
      Bảng chuẩn sạch + log lỗi
               |
               v
      Forecast / Ingredient Demand / Waste Analytics
               |
               v
      Agent evidence + kế hoạch có phê duyệt
```

Các file chuẩn xuất ra cho MVP:

```text
data/
├── raw_private/                 # KHÔNG commit Git, không public
│   ├── sales_reports/           # ảnh/Excel gốc
│   ├── inventory_docs/
│   └── preparation_waste_logs/
├── staging_private/             # bản parse, chờ người duyệt
├── processed_private/           # dữ liệu được chuẩn hóa, đủ phân tích
│   ├── menu_items.csv
│   ├── ingredients.csv
│   ├── recipe_bom.csv
│   ├── sales_daily.csv
│   ├── purchases.csv
│   ├── stock_counts.csv
│   └── topping_daily.csv
├── public_examples/             # CHỈ dữ liệu synthetic / đã được phép chia sẻ
└── quality_reports/
```

**Lưu ý:** Các đoạn CSV trong tài liệu dưới đây là **dữ liệu giả lập** để làm mẫu cấu trúc, không phải công thức, giá bán hay số liệu nội bộ Mixue thực tế.

## 2. Nguyên tắc dữ liệu & quyền sử dụng

- Chỉ xuất và xử lý báo cáo, công thức và thông tin giá vốn trong phạm vi được chủ thể có thẩm quyền cho phép. Được xem tại cửa hàng **không mặc nhiên có nghĩa** được tải lên cloud hoặc chia sẻ lên GitHub.
- Không đưa mã cửa hàng, nhân sự, khách hàng, tài khoản, số điện thoại, giá vốn và công thức độc quyền vào repo công khai. Tạo bộ synthetic để public demo.
- Lưu ảnh/Excel gốc (nếu được phép) ở private storage, đặt tên có ngày, lưu checksum; dữ liệu parse phải truy ra `source_id`.
- Dữ liệu doanh thu có thể khác `qty × list_price` do giảm giá, trả hàng, combo; lưu cả hai và chỉ cảnh báo đối soát, không tự ghi đè.
- Thời gian chuẩn hóa theo **ngày kinh doanh của cửa hàng**, timezone `Asia/Ho_Chi_Minh`, không tự cắt ngày theo UTC.
- Mỗi thông tin ước lượng phải gắn `estimated=true` hoặc trạng thái `UNKNOWN`, không để trông như dữ liệu đo thực tế.

## 3. Bảy bộ dữ liệu tối thiểu

### 3.1. `menu_items.csv` — Danh mục đồ uống

| Field | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `sku_id` | string | Có | Mã định danh ổn định, không lấy tên làm khóa |
| `sku_name` | string | Có | Tên đã chuẩn hóa |
| `variant` | string | Có thể | Size/mức đường/topping nếu tách SKU |
| `selling_price_vnd` | integer | Có, nếu có giá | Giá niêm yết theo phiên bản/dữ liệu có hiệu lực |
| `effective_from` | date | Có | Ngày hiệu lực giá và mapping |
| `effective_to` | date | Không | Null nếu hiện hành |
| `is_active` | boolean | Có | Có đang bán không |

**Ví dụ:**

```csv
sku_id,sku_name,variant,selling_price_vnd,effective_from,effective_to,is_active
SKU001,Tra Sua A,M,29000,2026-09-01,,true
SKU002,Kem Tuoi B,standard,15000,2026-09-01,,true
```

### 3.2. `ingredients.csv` — Danh mục nguyên liệu

| Field | Kiểu | Ghi chú |
|---|---|---|
| `ingredient_id` | string | Mã duy nhất |
| `ingredient_name` | string | Tên chuẩn hóa (không public công thức nhạy cảm) |
| `base_unit` | enum | `g`, `ml`, `pcs` |
| `unit_cost_vnd` | numeric/null | Giá vốn tương ứng **1 base_unit** nếu được phép dùng |
| `ingredient_group` | string | `dry`, `syrup`, `prepared_topping`, `packaging`... |
| `shelf_life_rule_id` | string/null | Tham chiếu chính sách hạn dùng được xác minh |

```csv
ingredient_id,ingredient_name,base_unit,unit_cost_vnd,ingredient_group,shelf_life_rule_id
ING001,Topping A,g,30,prepared_topping,RULE_A
ING002,Nguyen Lieu B,ml,15,syrup,
ING003,Ly Dung,pcs,700,packaging,
```

**Cẩn trọng:** `unit_cost_vnd` phải theo base unit, ví dụ 30 VND/g khác với 30.000 VND/kg; giữ cả giá nguồn và phép quy đổi trong bảng audit.

### 3.3. `recipe_bom.csv` — Định lượng theo sản phẩm

| Field | Kiểu | Ghi chú |
|---|---|---|
| `recipe_id` | string | Mã công thức/phiên bản |
| `sku_id` | string | Món đã mapping |
| `ingredient_id` | string | Nguyên liệu |
| `quantity_per_item` | decimal | Lượng dùng 1 món, **sau chuẩn hóa** |
| `unit` | enum | Phải trùng base unit của nguyên liệu |
| `effective_from` / `effective_to` | date | Hỗ trợ versioning |
| `is_optional` | boolean | Đánh dấu topping tùy chọn; không cộng nếu thiếu số bán variant |

```csv
recipe_id,sku_id,ingredient_id,quantity_per_item,unit,effective_from,effective_to,is_optional
RCP001v1,SKU001,ING001,30,g,2026-09-01,,false
RCP001v1,SKU001,ING002,40,ml,2026-09-01,,false
RCP002v1,SKU002,ING003,1,pcs,2026-09-01,,false
```

**Quan trọng về topping sau sơ chế:** nếu BOM ghi 20 g trân châu chín nhưng phiếu nhập ghi 10 kg trân châu khô, **không cộng trực tiếp**. Lưu `raw_ingredient_id`, `prepared_ingredient_id`, hệ số chuyển đổi/yield thực tế có xác nhận; nếu không có, chỉ lập kế hoạch theo dạng nguyên liệu đã được chuẩn hóa tương ứng.

### 3.4. `sales_daily.csv` — Bán theo món/ngày

| Field | Kiểu | Ghi chú |
|---|---|---|
| `business_date` | date ISO | YYYY-MM-DD |
| `store_id` | string | Mã ẩn danh |
| `sku_id` | string | Khớp menu mapping |
| `quantity_sold` | integer >=0 | Số món đã bán theo báo cáo |
| `revenue_vnd` | integer >=0/null | Doanh thu thực nếu báo cáo có |
| `source_id` | string | Tên/ID báo cáo gốc |
| `verification_status` | enum | `pending`, `verified`, `rejected` |

```csv
business_date,store_id,sku_id,quantity_sold,revenue_vnd,source_id,verification_status
2026-10-10,STORE_DEMO,SKU001,42,1218000,report_20261010,verified
2026-10-10,STORE_DEMO,SKU002,25,375000,report_20261010,verified
2026-10-11,STORE_DEMO,SKU001,38,1102000,report_20261011,verified
```

**Khóa logic:** `store_id + business_date + sku_id`. Nếu có bản sửa, lưu phiên bản mới và lịch sử cũ; không lưu hai bản cùng `is_current=true`.

**Thiếu ngày:** Nếu thiếu hẳn báo cáo ngày 12/10, ghi `missing_report`. Không tạo một ngày 0 sản phẩm cho toàn cửa hàng.

**Không có hàng trong báo cáo:** xác minh báo cáo là full SKU list hay chỉ top-selling. Một SKU không xuất hiện **không chắc bán 0**, trừ khi biết báo cáo có đầy đủ dữ liệu và quy ước zero omission.

### 3.5. `purchases.csv` — Nhập nguyên liệu

| Field | Kiểu | Ghi chú |
|---|---|---|
| `purchase_id` | string | Mã chứng từ nhập |
| `order_date` | date | Ngày đặt nếu có |
| `received_date` | date/null | Ngày **đã nhận**, không suy từ ngày đặt |
| `ingredient_id` | string | Mã nguyên liệu |
| `quantity_received` | decimal | Số lượng thực nhận đã đổi base unit |
| `unit` | enum | g/ml/pcs |
| `unit_cost_vnd` | numeric/null | Cost/base unit nếu được phép |
| `source_id` | string | Phiếu nhập hoặc ledger ID |

```csv
purchase_id,order_date,received_date,ingredient_id,quantity_received,unit,unit_cost_vnd,source_id
PO001,2026-10-09,2026-10-10,ING001,10000,g,30,invoice_demo_001
PO002,2026-10-10,2026-10-11,ING002,5000,ml,15,invoice_demo_002
```

Nếu quản lý tồn kho bằng pack, lưu thêm `pack_size`, `pack_unit` trong bảng supplier item; không mất thông tin gốc.

### 3.6. `stock_counts.csv` — Kiểm kê thực tế

| Field | Kiểu | Ghi chú |
|---|---|---|
| `count_id` | string | ID lần kiểm |
| `counted_at` | datetime | Thời điểm thực sự kiểm kê |
| `business_date` | date | Ngày kinh doanh liên quan |
| `ingredient_id` | string | Mã nguyên liệu |
| `quantity_counted` | decimal | Lượng kiểm thực tế theo base unit |
| `unit` | enum | g/ml/pcs |
| `verified_by_role` | string | Chức danh, không cần public danh tính |

```csv
count_id,counted_at,business_date,ingredient_id,quantity_counted,unit,verified_by_role
CNT001,2026-10-10T22:00:00+07:00,2026-10-10,ING001,3500,g,manager
CNT002,2026-10-11T22:00:00+07:00,2026-10-11,ING001,2100,g,manager
```

**Tồn ngày D** chỉ đáng tin khi có count gần D hoặc ledger sự kiện đầy đủ từ lần kiểm gần nhất. Không dùng stock count cuối tháng làm `on_hand` cho ngày 10 nếu thiếu biến động giữa kỳ.

### 3.7. `topping_daily.csv` — Chuẩn bị và hủy cuối ngày

| Field | Kiểu | Ghi chú |
|---|---|---|
| `business_date` | date | Ngày báo cáo |
| `store_id` | string | Store |
| `prepared_ingredient_id` | string | Topping **đã chế biến** |
| `prepared_qty` | decimal | Tổng topping đã chuẩn bị trong ngày |
| `wasted_qty` | decimal | Tổng topping hủy cuối ngày |
| `unit` | enum | g/ml/pcs đã chuẩn hóa |
| `carry_in_qty` | decimal/null | Tồn đầu ngày còn sử dụng được nếu quy trình cho phép |
| `carry_out_qty` | decimal/null | Tồn cuối ngày còn dùng được nếu có |
| `reason` | string/null | Hết hạn, sai chất lượng, khác; chỉ nhập khi biết |
| `source_id` | string | Phiếu cuối ngày / xác nhận |

```csv
business_date,store_id,prepared_ingredient_id,prepared_qty,wasted_qty,unit,carry_in_qty,carry_out_qty,reason,source_id
2026-10-10,STORE_DEMO,ING001,5000,800,g,0,0,,closing_20261010
2026-10-11,STORE_DEMO,ING001,6000,1500,g,0,0,,closing_20261011
2026-10-12,STORE_DEMO,ING001,5000,300,g,0,0,,closing_20261012
```

**Số liệu trên là giả lập.** Nếu thực tế chỉ biết tổng lượng hủy cuối ngày mà không phân biệt mẻ, không suy luận chính xác topping nào bị hủy vì chuẩn bị quá nhiều hay lỗi chất lượng.

## 4. Một nhật ký riêng cho chất lượng dữ liệu

`data_quality_issues.csv`:

```csv
issue_id,dataset,row_ref,severity,issue_type,description,status
ISS001,sales_daily,2026-10-12:SKU001,error,missing_source,Bao cao ngay khong ro,open
ISS002,topping_daily,2026-10-11:ING001,warning,unknown_carryover,Chua xac nhan co topping chuyen ngay khong,open
```

Status: `open`, `needs_review`, `resolved`, `accepted_with_caveat`. Không im lặng bỏ qua hàng dữ liệu lỗi.

## 5. Quy trình chuẩn hóa dữ liệu từng bước

### Bước 1 — Kiểm tra giấy tờ/screenshot thực tế
- [ ] Báo cáo ngày nào? Ngày in trên hóa đơn có phải `business_date` không?
- [ ] Có **toàn bộ SKU** hay chỉ Top sản phẩm bán chạy?
- [ ] Có cột số lượng riêng với doanh thu hay không?
- [ ] Có sản phẩm trùng tên nhưng khác size, topping, combo?
- [ ] Dòng bị che/cắt/không nhìn rõ? Đánh dấu `needs_review`, không đoán.

### Bước 2 — Tạo `SKU Mapping Master`
- [ ] Mã SKU ổn định không thay theo tên hiển thị.
- [ ] Danh sách alias được duyệt (`Trà A`, `Tra A` → `SKU001`).
- [ ] Quy định rõ các biến thể size/topping: SKU độc lập hay phụ kiện.
- [ ] Đơn vị và định lượng BOM có cùng ngày hiệu lực.

### Bước 3 — Quy đổi đơn vị

| Dữ liệu nguồn | Base unit | Công thức |
|---|---|---|
| 1.2 kg | g | `1.2 * 1000 = 1200` |
| 2.5 L | ml | `2.5 * 1000 = 2500` |
| 3 thùng × 50 ly | pcs | `3 * 50 = 150` |
| 10 kg nguyên liệu thô → thành phẩm | Không mặc định | Cần yield/conversion đã xác minh |

Không tự quy đổi g ↔ ml dựa vào 1:1. Không cộng nguyên liệu sống và thành phẩm nếu thiếu hệ số yield.

### Bước 4 — Kiểm tra lịch sử và độ phủ

Tạo bảng có:
- 30 cột ngày (hoặc 30 dòng/ngày) và từng SKU xuất hiện.
- `report_available` mỗi ngày.
- Số SKU có lịch sử đủ ≥14 ngày, ≥21 ngày, đủ 30 ngày.
- Bao nhiêu ngày tồn kho và topping prep/waste được ghi **cùng ngày với sales**.
- Danh sách SKU mới, ngừng bán, thay đổi giá, BOM thay đổi.

**Lưu ý:** 30 ngày của sales **không suy ra** 30 ngày topping; cần profile riêng.

### Bước 5 — Đối soát đa nguồn

1. `SUM(quantity_sold)` theo ngày so sánh tổng số món ghi trên báo cáo nếu có.
2. `SUM(revenue_vnd)` so sánh tổng doanh thu (chênh lệch có thể do discount, combo, hoàn tiền); không kết luận gian lận.
3. `expected BOM usage` so sánh với số nhập/kiểm kê có cùng kỳ (không suy ra trực tiếp usage từ hai snapshot nếu thiếu thông tin).
4. `prepared_qty`, `wasted_qty`: cảnh báo khi `wasted_qty > prepared_qty + carry_in_qty` trong cùng phạm vi, trừ khi có chứng từ điều chỉnh/khác ngày.
5. Kiểm tra món bị hủy/hoàn và topping dùng thêm ngoài BOM khi có dữ liệu.

### Bước 6 — Human validation
- [ ] Phê duyệt mapping và số ngày thiếu.
- [ ] Phê duyệt dữ liệu topping và đơn vị trước/sau sơ chế.
- [ ] Phê duyệt ngày hiệu lực BOM và quy tắc hạn dùng/batch.
- [ ] Gắn `verified_by`, `verified_at`, `source_ref`, `revision`.

### Bước 7 — Khóa dataset snapshot
Sau khi dữ liệu đã duyệt: tạo `data_snapshot_id`, ghi phạm vi ngày và checksum, chỉ forecast/backtest từ snapshot đó. Nếu chỉnh sửa báo cáo, tạo revision mới và backtest mới — không âm thầm thay đổi báo cáo nghiên cứu.

## 6. Chọn dữ liệu cho từng bài toán

| Task | Bắt buộc | Optional | Không có thì sao? |
|---|---|---|---|
| Daily sales forecast | `sales_daily`, SKU mapping, ngày liên tục/trạng thái missing | ngày lễ, thời tiết, promotion | chỉ dùng baseline, giảm confidence |
| Ingredient demand | forecast SKU + BOM có hiệu lực, units | sales variants/topping tùy chọn | exclude thành phần thiếu mapping |
| Daily topping prep suggestion | ingredient demand + prep policy + batch size | usable carry-over, lịch sử waste | ra kế hoạch ước tính + cần người duyệt |
| Waste analytics | prepared qty + wasted qty **cùng scope** | reason, unit cost, batch_id | chỉ mô tả tổng lượng, không khẳng định tỷ lệ |
| Replenishment | tồn đáng tin, lead time, pack size, purchase status | unit cost, budget, safety stock | `NEEDS_INPUT` hoặc kế hoạch lượng nhu cầu thuần |
| Stock variance | stock count + receipts + mapping BOM + movement history | adjustments, return records | nêu thiếu nguồn, không quy kết thất thoát |

## 7. Forecast dataset & split thực tế cho 30 ngày

### Định dạng wide/long
Dùng **long format** mỗi dòng là một `(business_date, sku_id)`. Gắn `observed`, `zero_confirmed` hoặc `missing` để tránh coi missing=0.

### Rolling-origin 1-day test (ví dụ)

| Fold | Dữ liệu quá khứ | Ngày cần dự báo |
|---|---|---|
| 1 | Ngày 1–14 | Ngày 15 |
| 2 | Ngày 1–15 | Ngày 16 |
| ... | ... | ... |
| 16 | Ngày 1–29 | Ngày 30 |

Áp dụng khi ít nhất 14 ngày liên tiếp đáng tin, và mô hình có đủ lag cần thiết. 7-day forecast chỉ có vài fold hoàn chỉnh ở chuỗi 30 ngày; không nên chọn mô hình từ một lần holdout rồi công bố độ chính xác ổn định.

### Baselines

```python
import pandas as pd

# df có cột business_date, sku_id, quantity_sold và đã validate.
# Kết quả chỉ có nghĩa khi mỗi ngày là ngày được báo cáo đầy đủ.
df = df.sort_values(["sku_id", "business_date"]).copy()
df["seasonal_naive_7"] = df.groupby("sku_id")["quantity_sold"].shift(7)
df["moving_avg_7"] = df.groupby("sku_id")["quantity_sold"].transform(
    lambda s: s.shift(1).rolling(7, min_periods=7).mean()
)
```

Trong pipeline thực tế cần **reindex lịch ngày và kiểm soát missing**; `shift(7)` trên 7 bản ghi chỉ tương đương 7 ngày nếu dữ liệu SKU đã được hoàn thiện lịch đúng quy tắc.

### Metrics

\[
MAE = \frac{1}{N}\sum_{i=1}^{N}|y_i-\hat y_i|
\]

\[
WAPE = \frac{\sum |y_i-\hat y_i|}{\sum |y_i|}\times100\%
\]

Nếu `sum actual = 0`, WAPE undefined → ghi `N/A`; không gán 0%.

## 8. Cách tính topping demand, waste & đối soát

### Ví dụ synthetic

- Ngày 10/10: 100 ly có dùng topping A.
- Định lượng BOM (đã sơ chế): 30 g/ly.
- Sử dụng **lý thuyết**: 3.000 g.
- Lượng đã chuẩn bị: 4.000 g.
- Lượng hủy cuối ngày: 700 g.
- Tồn đầu/cuối có thể dùng: chưa chắc chắn.

**Từ đây được kết luận:** Theo BOM ước tính dùng 3.000 g; báo cáo chuẩn bị 4.000 g và hủy 700 g; nếu cùng phạm vi và không có carry-over thì waste rate theo lượng chuẩn bị là 17,5%.

**Không được kết luận:** 300 g còn lại là hao hụt không rõ nguyên nhân hay chắc chắn có thất thoát. Có thể do thay đổi định lượng, thao tác phát sinh, tồn chuyển ngày hoặc phạm vi nhật ký khác nhau.

### Công thức khuyến nghị

```text
BOM_estimated_usage = Σ (daily_sold_SSKU × verified_prepared_topping_qty_per_SSKU)
Recorded_waste = Σ waste records within same business_day and topping
Recorded_prep = Σ prep records within same business_day and topping
Waste_rate = Recorded_waste / Recorded_prep  # khi mẫu số >0 và định nghĩa phạm vi nhất quán
```

Với đặc thù Mixue: nếu quy định yêu cầu hủy toàn bộ topping vào cuối ngày, xác nhận điều đó trong business rules rồi mới sử dụng giả định `carry_out=0`. Không tự giả định.

## 9. Tối ưu nhập hàng — dữ liệu bổ sung cần chốt

| Field | Bắt buộc để làm đúng bài toán | Thu từ đâu? |
|---|---|---|
| `pack_size` | Có | Bao bì/phiếu nhập |
| `lead_time_days` | Có | Lịch giao/nhà cung cấp |
| `on_hand` | Có | Kiểm kê/ledger |
| `on_order` | Có nếu đã đặt | Danh sách đơn chờ nhận |
| `review_period_days` | Có | Quy trình kiểm kho/đặt hàng |
| `approved_supplier` | Có | Quy định cửa hàng |
| `unit_cost` | Cần khi tối ưu chi phí | Chứng từ/được phép sử dụng |
| `budget` | Cần khi ràng buộc ngân sách | Quản lý xác nhận |
| `expiration` | Cần khi lập kế hoạch hạn dùng/lô | Nhãn/nghiệp vụ đã xác minh |

Nếu chưa có lead time/pack size, hệ thống được phép hiển thị **estimated requirement**, không được xuất “optimal purchase order” như đã tính đầy đủ.

## 10. Data quality checklist trước khi đưa vào Agent

- [ ] Nguồn được phép sử dụng và có scope rõ ràng.
- [ ] Có 30 ngày bán thật hoặc ghi chính xác những ngày thiếu.
- [ ] Sản phẩm được map tới SKU chuẩn, không nhầm size/topping.
- [ ] Revenue và giá bán có hiệu lực ngày, không gán doanh thu bằng giá niêm yết nếu có khuyến mãi.
- [ ] BOM và đơn vị quy đổi chuẩn; phân biệt raw/prepared.
- [ ] Prep/waste logs có số ngày thực, đơn vị, ngày kinh doanh và người xác nhận.
- [ ] `wasted_qty <= prepared_qty + carry_in_qty` hoặc có giải trình ngoại lệ phù hợp.
- [ ] Kiểm kê có timestamp, không dùng số cuối kỳ cho ngày trước tùy ý.
- [ ] Đơn nhập `ordered` không được tính thành `received`.
- [ ] Có `data_snapshot_id`, nguồn, revision, trạng thái xác nhận.
- [ ] Không có thông tin nội bộ/bí mật trong public repo, test fixtures, prompt logs.

## 11. Data quality report mẫu

```yaml
snapshot_id: "snapshot_demo_20261013"
store_id: "STORE_DEMO"
sales:
  expected_days: 30
  reported_days: 30
  verified_days: 28
  sku_count: 32
  missing_sku_day_pairs: 14
  unmatched_sku_names: 2
recipes:
  sku_with_verified_bom: 28
  sku_total: 32
topping_logs:
  prep_recorded_days: 12
  waste_recorded_days: 12
  same_scope_verified_days: 10
inventory:
  last_verified_stock_count: "2026-10-12"
release_gates:
  analytics: PASS
  forecasting: CONDITIONAL
  preparation_planning: NEEDS_REVIEW
  purchase_optimization: NEEDS_INPUT
```

**Các số trên là ví dụ giả lập.** `PASS/CONDITIONAL/NEEDS_REVIEW/NEEDS_INPUT` phải được suy từ validator, không do LLM tự gán thiếu căn cứ.

## 12. Phần nào phải làm ngay trong 7 ngày đầu?

| Ngày | Việc làm với dữ liệu thật | Kết quả |
|---|---|---|
| 1 | Xin phép sử dụng, xác nhận phạm vi và cách ẩn danh | Data permission & boundaries |
| 2 | Gom báo cáo SKU/ngày 30 ngày | Raw inventory of files |
| 3 | Tạo SKU mapping + business_date standard | `menu_items.csv`, mapping review |
| 4 | Chuyển BOM sang base units, lưu version | `ingredients.csv`, `recipe_bom.csv` |
| 5 | Nhập & chuẩn hóa kiểm kê/phiếu nhập | `purchases.csv`, `stock_counts.csv` |
| 6 | Nhập prep/waste, xử lý carry-over, mẻ | `topping_daily.csv` |
| 7 | Chạy quality checks; xác nhận bằng mắt và khóa snapshot | `data_quality_report`, verified dataset |

## 13. Mẫu trao đổi khi xin dữ liệu với chủ quán

> Tôi đang thực hiện đồ án nghiên cứu hỗ trợ dự báo số lượng bán và lập kế hoạch nguyên liệu. Tôi chỉ cần báo cáo tổng hợp theo món/ngày, nhập hàng, kiểm kê, và lượng topping chuẩn bị/hủy. Tôi sẽ ẩn định danh, bảo quản dữ liệu trong hệ thống riêng và không công bố công thức/giá vốn hay chứng từ gốc nếu chưa được phép. Giai đoạn đầu hệ thống chạy song song và chỉ đưa ra gợi ý để quản lý xem xét; không tự can thiệp vào hệ thống hay quy trình cửa hàng.

## 14. Definition of Ready cho từng module

- **Forecasting READY:** có `sales_daily` đã verified, lịch ngày/zero/missing rõ ràng, tối thiểu 14 ngày đáng tin để chạy baseline và báo giới hạn.
- **Ingredient Engine READY:** BOM version đầy đủ cho những SKU sẽ tối ưu, unit conversion đã duyệt.
- **Waste Analytics READY:** ít nhất một nhóm topping có cặp prep/waste cùng phạm vi; tỷ lệ hủy chỉ hiển thị khi có mẫu số hợp lệ.
- **Preparation Optimizer READY:** forecast + usable stock + batch policy + safety constraints đủ.
- **Replenishment READY:** tồn có thời điểm, lead time, pack size, trạng thái đơn đang về có thể đối chiếu.
- **AI Agent READY:** dữ liệu đã verified và tool deterministic có test; action chỉ ở draft + approval.

## 15. Các lỗi rất dễ làm sai đồ án

1. Tính theo giờ dù chỉ có dữ liệu ngày.
2. Lấy 30 ngày sales suy ra topping logs cũng đủ 30 ngày.
3. Dùng BOM **nguyên liệu khô** để đối chiếu trực tiếp với topping **đã nấu**.
4. Dùng số lượng sản phẩm bán nhưng bỏ qua size, option hoặc free topping nếu chúng làm thay đổi định lượng.
5. Điền 0 cho báo cáo ngày bị thiếu hoặc SKU bị ẩn vì báo cáo chỉ hiển thị top món.
6. Đưa cùng một dữ liệu ngày target vào rolling feature của dự báo ngày đó.
7. Coi tương quan prep/waste như nguyên nhân thất thoát hoặc sai phạm nhân viên.
8. Khẳng định sản phẩm đã “giảm waste X%” khi chỉ chạy replay dữ liệu cũ.
9. Để Agent tự thay đổi đơn nhập, công thức, tồn kho mà không có sự phê duyệt.
10. Đẩy dữ liệu thực tế có tính độc quyền lên repository công khai.

---

**Bước tiếp theo:** Khi có quyền hợp lệ, chuẩn bị bốn file đầu tiên: `sales_daily.csv`, `menu_items.csv`, `recipe_bom.csv`, `topping_daily.csv`. Chạy validator, sau đó mới kết nối forecast/optimization. Các bảng nhập hàng và kiểm kê được đưa vào kế hoạch nhập khi đã xác nhận đủ đơn vị, timestamp và trạng thái.

**Tài liệu liên quan:** [PRD.md](PRD.md), [ARCHITECTURE_ADR.md](ARCHITECTURE_ADR.md).
