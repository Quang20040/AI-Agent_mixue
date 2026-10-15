# Checkpoints 30 ngày — BeverageOps AI

> **30 ngày full-time (ước tính 8 giờ/ngày) · 13/10/2026 · Checklist triển khai có thể thực thi**  
> Mục tiêu: một **vertical slice** chạy được từ dữ liệu ngày → dự báo → nhu cầu nguyên liệu → gợi ý chuẩn bị/nhập → kiểm chứng → quản lý phê duyệt → đánh giá.  
> **Không** cam kết SaaS thương mại hoàn chỉnh hay giảm hao hụt thực tế sau 30 ngày.

## 0. Nguyên tắc ưu tiên

- **P0 bắt buộc:** dữ liệu có nguồn & validation; SKU/BOM; dashboard cơ bản; forecast baseline; ingredient projection; daily topping preparation suggestion; purchase draft; Agent tools; verification/approval; benchmark tối thiểu.
- **P1 nếu còn thời gian:** OCR ảnh báo cáo; OR-Tools tối ưu đa nguyên liệu (nếu có chi phí/pack/lead time); anomaly detection nâng cao; tích hợp POS API.
- **Không làm:** forecast theo giờ/ca, autonomous buying, tự sửa BOM/quy trình, multi-store đầy đủ, native app.
- **Quy tắc chất lượng:** mỗi ngày kết thúc bằng commit, test hoặc minh chứng rõ ràng; không tính xong chỉ vì giao diện đã hiện.

## 1. Tài nguyên và tiền đề

- Python 3.11+, FastAPI, SQLAlchemy, Alembic, pandas, pytest.
- PostgreSQL, Docker Compose; Frontend Next.js + TypeScript.
- LangGraph + LLM API có tool-calling. Chi phí API giới hạn và không gửi dữ liệu độc quyền khi chưa được phép.
- Dữ liệu doanh số từng món/ngày khoảng 30 ngày, BOM, giá sản phẩm, tồn kho/nhập hàng/kiểm kê, lượng chuẩn bị và hủy topping cuối ngày.
- Cần chốt: quyền sử dụng dữ liệu, cách đặt ngày kinh doanh, đơn vị, phiên bản công thức, số ngày lịch sử topping thật, quy cách mẻ/nhập.

## 2. Lộ trình 30 ngày (từng ngày có deliverable và điều kiện xong)

### Tuần 1 — Requirements, Data Foundation & Backend skeleton

#### Ngày 01 — Problem definition & KPI
- [ ] Viết 1 trang problem statement, 3 primary use case: dự báo ngày, chuẩn bị topping, đề xuất nhập hàng.
- [ ] Chốt P0/P1/out-of-scope và nhóm người dùng `Owner/Manager/Staff`.
- [ ] Xác định KPI phân biệt mô phỏng, shadow pilot và thực tế.
- **Deliverable:** `docs/problem.md`, `docs/scope.md`, bản PRD được duyệt nội bộ.
- **Done:** Giải thích trong 2 phút vì sao đây không phải chatbot/POS mới.

#### Ngày 02 — Survey nghiệp vụ tại quán
- [ ] Vẽ luồng bán → nhập hàng → chốt ngày → kiểm kê → chuẩn bị/hủy.
- [ ] Xác nhận format số bán mỗi ngày, BOM có size/topping, đơn vị thành phẩm của topping.
- [ ] Xác nhận quy định hạn sử dụng, quy cách mẻ, quyền nhập hàng.
- **Deliverable:** `docs/operations_flow.md`, danh sách business rules.
- **Done:** Không còn giả định bắt buộc về giờ bán/ca.

#### Ngày 03 — Data audit 30 ngày
- [ ] Kiểm kê ngày có dữ liệu, SKU, trùng, missing, hàng trả/hủy, giá bán.
- [ ] Kiểm tra số ngày prep/waste hiện có **riêng** so với 30 ngày sales.
- [ ] Lập bảng mapping tên SKU → SKU ID, quy đổi ingredient unit.
- **Deliverable:** `docs/data_profile.md`, bản mẫu `sales_daily.csv` đã ẩn danh.
- **Done:** Báo cáo được missing rate, coverage, số SKU hợp lệ.

#### Ngày 04 — Chuẩn hóa Recipe/BOM & chính sách nguyên liệu
- [ ] Tạo `menu_items`, `ingredients`, `recipe_versions`, `recipe_lines`.
- [ ] Viết test 10 trường hợp chuyển món bán → lượng nguyên liệu; xử lý size/topping.
- [ ] Ghi các trường thiếu để không dự báo sai (optional ingredient).
- **Deliverable:** `data/schema_examples/` (dữ liệu synthetic), `tests/test_bom.py`.
- **Done:** Không nhân nhầm g/ml/pcs; phiên bản BOM đúng theo ngày.

#### Ngày 05 — Database design
- [ ] Thiết kế ERD, ràng buộc unique/key/index, audit, import batch.
- [ ] Viết migration cho bảng P0.
- [ ] Có seed dữ liệu giả lập, không commit dữ liệu Mixue thật.
- **Deliverable:** `alembic/versions/*`, `docs/erd.md`.
- **Done:** `alembic upgrade head` và rollback trên DB trống chạy đúng.

#### Ngày 06 — Setup project
- [ ] Tạo monorepo `apps/api`, `apps/web`, `experiments`, `docs`.
- [ ] Docker Compose: Postgres + API + web.
- [ ] CI lint/unit tests và `.env.example`.
- **Deliverable:** repo có README hướng dẫn chạy local.
- **Done:** Máy mới clone → `docker compose up` → healthcheck pass.

#### Ngày 07 — CSV/Excel Import v1
- [ ] POST import, preview lỗi, xác nhận ghi DB.
- [ ] Kiểm tra mapping SKU, doanh thu/quantity, idempotency.
- [ ] Import 30 ngày sales đã xác nhận; lưu checksum nguồn.
- **Deliverable:** màn import tối giản + API/test.
- **Done:** import lại cùng file không nhân đôi dữ liệu; file lỗi không ghi nửa chừng.

**CHECKPOINT CP1 (Ngày 7):** API chạy; nhập liệu lặp lại an toàn; có tài liệu nguồn dữ liệu và BOM/test. Nếu CP1 fail, ưu tiên fix trước mọi AI.

### Tuần 2 — Inventory, Waste & Forecasting baselines

#### Ngày 08 — Sales analytics API
- [ ] Endpoint tổng hợp doanh số/ngày, SKU top/bottom, doanh thu.
- [ ] Phân biệt missing ngày và ngày quantity=0.
- **Deliverable:** `/sales/daily` + unit tests.
- **Done:** tổng từ DB đối chiếu đúng với bảng nguồn sau khi xác nhận.

#### Ngày 09 — Inventory ledger & stock count
- [ ] CRUD nguyên liệu, receipts, stock count, adjustments (theo quyền).
- [ ] Tính inventory position và ngày tồn đáng tin cậy.
- **Deliverable:** inventory endpoints + test.
- **Done:** pending PO không làm tăng on-hand; không double count.

#### Ngày 10 — Preparation & waste logs
- [ ] Form/API nhập topping chuẩn bị và hủy theo ngày, cùng đơn vị cơ sở.
- [ ] Cho phép nhiều lần nhập/ngày; phân biệt ngày kinh doanh và timestamp.
- [ ] Hiển thị `insufficient_data` khi thiếu prep hoặc waste.
- **Deliverable:** bảng và màn Prep/Waste ngày.
- **Done:** waste rate không chia 0 và không tính nếu không cùng mẫu/chính sách.

#### Ngày 11 — Daily analytics dashboard
- [ ] Biểu đồ sản lượng/ngày, top SKU, lịch sử waste từng topping.
- [ ] Filter date/ingredient; hiện badge “demo” nếu dữ liệu giả lập.
- **Deliverable:** dashboard v0.
- **Done:** đối chiếu ít nhất 3 ngày với báo cáo gốc.

#### Ngày 12 — Forecast baseline 1
- [ ] Cài Seasonal Naive 7 ngày, Moving Average 7 ngày.
- [ ] Phân biệt zero vs missing; fallback cho SKU lịch sử quá ngắn.
- **Deliverable:** `forecasting/baselines.py`.
- **Done:** testcase leakage/edge cases pass.

#### Ngày 13 — Rolling-origin backtesting
- [ ] Train cutoff từng ngày; forecast 1 ngày ở nhiều mốc (ví dụ ngày 15–30 nếu đủ data).
- [ ] Tính MAE, WAPE, bias cả tổng và từng SKU; đánh dấu coverage.
- **Deliverable:** `experiments/backtest.py`, `reports/forecast_baseline.md`.
- **Done:** tái lập metric được, không dùng target/future làm feature.

#### Ngày 14 — Model selection & forecast API
- [ ] Chọn policy theo benchmark, ưu tiên mô hình đơn giản ổn định.
- [ ] API forecast 1 ngày; 7 ngày chỉ có nhãn exploratory.
- [ ] Lưu model/snapshot/version.
- **Deliverable:** `/forecast-runs` và biểu đồ đối chiếu.
- **Done:** kết quả predict tái lập trên snapshot cố định.

**CHECKPOINT CP2 (Ngày 14):** Dashboard thật, prep/waste theo ngày và ít nhất hai forecast baselines với bảng sai số. Nếu data chưa đủ, nêu cảnh báo — không giả lập hiệu quả thực.

### Tuần 3 — Deterministic optimization + Agent

#### Ngày 15 — BOM projection engine
- [ ] Nhân forecast SKU × BOM version, tổng hợp theo ingredient.
- [ ] Loại hay đánh dấu món thiếu variant/optional topping.
- **Deliverable:** `calculate_ingredient_demand()` + 15 tests.
- **Done:** tính tay 3 ví dụ trùng kết quả máy.

#### Ngày 16 — Topping preparation plan v1
- [ ] Quy tắc target theo forecast, usable stock, batch size, buffer hợp lệ.
- [ ] Hard constraints: quy định chuẩn bị/bảo quản không được vi phạm.
- **Deliverable:** `optimize_preparation()` rule-based.
- **Done:** không âm; có cảnh báo khi policy/batch chưa đủ dữ liệu.

#### Ngày 17 — Replenishment v1
- [ ] Tính on-hand, on-order, lead time, review period, pack round-up.
- [ ] Nếu thiếu lead time/pack size: trạng thái `NEEDS_INPUT`.
- **Deliverable:** `create_replenishment_candidate()` + tests.
- **Done:** không tự ý thay dữ liệu tồn/nguyên liệu.

#### Ngày 18 — Solver optional & independent validator
- [ ] Nếu đã có unit cost, pack, budget: dùng OR-Tools giải tối ưu nhiều nguyên liệu.
- [ ] Nếu chưa đủ: giữ deterministic rule-based; **không block tiến độ**.
- [ ] Viết `verify_plan` độc lập với Agent.
- **Deliverable:** `validation.py`, baseline optimizer, solver optional.
- **Done:** các test ngân sách, pack, tồn hợp lệ; solver trả `INFEASIBLE` khi không có nghiệm.

**CHECKPOINT CP3 (Ngày 18):** Quy trình `sales → forecast → BOM → valid plan` chạy deterministic, có nguồn và test.

#### Ngày 19 — LangGraph skeleton
- [ ] Xây graph: authorize → validate → forecast → project → optimize → verify → draft.
- [ ] State lưu run_id, store_id xác thực, source refs, errors.
- **Deliverable:** `agent/graph.py`, mock tool tests.
- **Done:** graph chạy end-to-end không cần UI.

#### Ngày 20 — Agent tool contracts
- [ ] Kết nối tools `get_daily_sales`, `get_recipes`, `get_inventory_position`, `forecast`, `optimize`, `get_waste_summary`.
- [ ] Type/schema validation; giới hạn số tool calls/timeouts.
- **Deliverable:** `agent/tools.py`, contract tests.
- **Done:** Agent không chạy SQL tùy ý và không tự tạo số liệu nguồn.

#### Ngày 21 — Approval, audit, safety
- [ ] Tạo draft/approval request, Manager approve/reject từ backend.
- [ ] Test staff bị từ chối duyệt, LLM không thể gọi approve trực tiếp.
- [ ] Audit tool calls và source evidence.
- **Deliverable:** `approval` API + traces.
- **Done:** test unauthorized action, duplicate draft, missing evidence pass.

**CHECKPOINT CP4 (Ngày 21):** Agent điều phối được công cụ, đưa ra kế hoạch có bằng chứng; chỉ người có quyền mới phê duyệt.

### Tuần 4 (+ 2 ngày) — Productization, benchmark, shadow pilot

#### Ngày 22 — Dashboard thống nhất
- [ ] Hoàn thiện trang bán hàng, tồn kho, waste, trạng thái đồng bộ.
- [ ] Hiển thị data coverage, freshness và cảnh báo thiếu số liệu.
- **Deliverable:** UI dashboard v1.
- **Done:** responsive desktop/mobile cho luồng quản lý chính.

#### Ngày 23 — Plan & forecast UX
- [ ] Màn forecasts theo SKU; ingredient requirements; plan lines.
- [ ] So sánh manual vs baseline plan.
- **Deliverable:** UI preparation/replenishment.
- **Done:** hiển thị rõ giả định/bất định, đơn vị và ngày.

#### Ngày 24 — Agent chat & evidence panel
- [ ] Chat hỏi: “Ngày mai nên chuẩn bị bao nhiêu topping A, vì sao?”
- [ ] Hiện evidence: sales date range, forecast run, BOM version, inventory snapshot.
- **Deliverable:** chat v1 + evidence detail.
- **Done:** không có kết luận không nguồn; test câu hỏi thiếu dữ liệu.

#### Ngày 25 — End-to-end & security
- [ ] Import → forecast → optimizer → verify → draft → approve.
- [ ] RBAC, bad inputs, store scope, retries, idempotency.
- **Deliverable:** e2e test script + video/screenshot demo.
- **Done:** ít nhất 10 luồng end-to-end pass.

#### Ngày 26 — Golden dataset
- [ ] Tạo **ít nhất 30 scenario** có ground truth & expected behavior.
- [ ] Nhóm: bình thường, dữ liệu thiếu, tồn lỗi, ngân sách/pack, yêu cầu cấm.
- [ ] Lộ trình mở rộng 100 scenario sau MVP.
- **Deliverable:** `experiments/golden_cases.jsonl`, rubric.
- **Done:** có automatic evaluator cho hard constraints.

#### Ngày 27 — Benchmark
- [ ] So sánh naive vs moving average, manual/rule vs optimizer, deterministic workflow vs Agent.
- [ ] Báo số test, coverage, CI, giới hạn do 30 ngày dữ liệu.
- **Deliverable:** `reports/benchmark_v1.md`, số liệu và biểu đồ có thể tái lập.
- **Done:** tách rõ kết quả giả lập, historical replay, shadow pilot thật.

**CHECKPOINT CP5 (Ngày 27):** Có bảng benchmark có protocol và ít nhất 30 ca agent eval; không có future leakage.

#### Ngày 28 — Deployment & backup
- [ ] Docker deploy staging/protected VPS, HTTPS, env secrets.
- [ ] Migrate DB, kiểm tra backup & restore.
- [ ] Dữ liệu thật không lưu trong repo công khai.
- **Deliverable:** staging URL nội bộ, runbook.
- **Done:** deploy/rollback được, tài khoản staff không xem dữ liệu nhạy cảm.

#### Ngày 29 — Shadow pilot
- [ ] Dùng dữ liệu ngày mới; Agent đề xuất nhưng không thay quy trình cửa hàng.
- [ ] Ghi mức hữu ích, người quản lý đánh giá, forecast vs actual khi đến ngày.
- [ ] Không lấy một ngày làm claim tiết kiệm thực tế.
- **Deliverable:** `reports/shadow_pilot_day1.md`.
- **Done:** có bằng chứng một workflow trên dữ liệu thật đã được phép dùng.

#### Ngày 30 — Demo & defense pack
- [ ] Review toàn bộ acceptance criteria, fix bug blocker.
- [ ] Hoàn thiện README, architecture diagram, API docs, demo script.
- [ ] Viết limitations & roadmap 60–90 ngày; gắn nhãn pending features.
- **Deliverable:** release candidate `v0.1.0`, `docs/demo.md`, `reports/limitations.md`.
- **Done:** demo từ file sales → đề xuất topping/nhập → evidence → approval trong < 10 phút.

**CHECKPOINT CP6 (Ngày 30):** End-to-end demo, checkpoint report, limitations minh bạch và kế hoạch pilot tiếp.

## 3. Bảng checkpoint tổng hợp

| Gate | Thời điểm | Pass criteria | Nếu fail |
|---|---|---|---|
| CP1 | D7 | Import hợp lệ + BOM schema + DB & API chạy | Dừng thêm AI, sửa data model |
| CP2 | D14 | Analytics + waste + 2 forecast baselines có backtest | Chọn naive, không cố LightGBM |
| CP3 | D18 | Ingredient demand và 2 kế hoạch deterministic có verify | Bỏ solver OR-Tools, giữ rule-based |
| CP4 | D21 | Agent tool orchestration + approval/role safety | Chạy workflow deterministic, Agent chỉ giải thích |
| CP5 | D27 | Benchmark report + ≥30 golden scenarios | Không claim hiệu quả trước khi test |
| CP6 | D30 | Demo full path + shadow log + docs | Ship limited demo thay vì feature chưa an toàn |

## 4. Definition of Done (DoD) dùng mỗi ngày

- [ ] Code được commit trên branch có ý nghĩa, không commit dữ liệu nội bộ/thông tin bí mật.
- [ ] Unit/integration tests liên quan pass; lỗi tồn đọng ghi rõ.
- [ ] Chức năng có test case input bình thường + edge case.
- [ ] Kết quả có ảnh hoặc log tái hiện (không chứa dữ liệu nhạy cảm).
- [ ] Không đưa mock data vào màn hình thật mà không gắn nhãn.
- [ ] Update changelog và next-day blockers (tối đa 3 việc ưu tiên).

## 5. Kế hoạch khi dữ liệu không đủ

| Thiếu gì | Fallback an toàn |
|---|---|
| <14 ngày bán đáng tin | Sales analytics + trung bình ngắn, không gọi là forecast chính xác |
| Chỉ có 30 ngày lịch sử | Rolling 1-day backtest, không benchmark dài hạn 7 ngày quá tự tin |
| Prep/waste chưa đủ 7–14 ngày | Form nhập và dashboard mô tả; chưa tối ưu dựa trên tỷ lệ hủy |
| Thiếu giá vốn | Không tính lợi nhuận/chi phí hủy chính xác |
| Thiếu lead time/pack size | Kế hoạch “ước tính nhu cầu”, không xuất PO chuẩn |
| BOM thiếu topping tùy chọn | Chỉ tính SKU/ingredient có mapping đáng tin, đánh dấu excluded |
| Không có quyền pilot tác động thật | Chạy shadow mode; đo forecast và task time, không tuyên bố giảm lãng phí |

## 6. Ưu tiên nếu phải cắt scope

**Giữ lại:** clean sales → BOM → 1-day forecast → daily topping plan → waste dashboard → verify → manager approval.  
**Cắt trước:** tích hợp ảnh OCR, OR-Tools nhiều ràng buộc, chat tùy ý, nhiều cửa hàng, dashboard nâng cao, email/SMS, mobile native.  
**Không bao giờ cắt:** validation đầu vào, phân quyền, phê duyệt, dữ liệu nguồn, audit ở tác vụ ảnh hưởng vận hành.

## 7. Sau 30 ngày

- Thu thập thêm tối thiểu 30–60 ngày dữ liệu sales/prep/waste nhất quán.
- Đánh giá accuracy trên nhiều ngày, nhiều SKU, các thời điểm biến động.
- Thử nghiệm giới hạn với kế hoạch đã được quản lý phê duyệt, đo waste/shortage/effort trong điều kiện so sánh công bằng.
- Phỏng vấn người dùng và kiểm thử sẵn sàng trả phí trước khi đầu tư multi-tenant SaaS.

## 8. Cross-reference

- `01_PRD_BeverageOps_AI.md`
- `02_ARD_ADR_BeverageOps_AI.md`
- `04_Huong_Dan_Chuan_Bi_Du_Lieu.md`
