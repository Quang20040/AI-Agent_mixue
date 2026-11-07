# PRD — BeverageOps AI

> **Product Requirements Document · Phiên bản 1.0 · Ngày 13/10/2026**  
> **Tên đồ án:** Nghiên cứu và phát triển AI Agent dựa trên bằng chứng nhằm dự báo nhu cầu, tối ưu nguyên liệu và giảm hao hụt tại cửa hàng đồ uống.  
> **English:** *Evidence-Driven AI Agent for Demand Forecasting, Inventory and Waste Optimization in Beverage Stores*  
> **Trạng thái:** Phạm vi MVP đề xuất, cần xác nhận với cửa hàng trước khi pilot.

## 1. Executive summary

BeverageOps AI là **lớp hỗ trợ ra quyết định vận hành**, không phải phần mềm POS thay thế. Hệ thống tiếp nhận doanh số từng món theo **ngày**, bảng giá, công thức/định lượng (BOM), tồn kho, nhập hàng, kiểm kê, lượng topping **chuẩn bị và hủy cuối ngày**; tạo báo cáo, dự báo số lượng bán, ước tính nhu cầu nguyên liệu, đề xuất chuẩn bị/nhập hàng và nêu rõ bằng chứng của từng đề xuất. Quản lý phê duyệt hoặc từ chối; hệ thống ghi nhận kết quả thực tế để đánh giá.

**Pilot:** 01 cửa hàng đang vận hành theo mô hình Mixue, với dữ liệu mà người phát triển được phép tiếp cận. **Định vị sản phẩm dài hạn:** SaaS trung lập cho cửa hàng cà phê/trà sữa độc lập; không dùng thương hiệu Mixue làm tên thương mại.

### Điều kiện dữ liệu đã xác nhận

| Nguồn | Hiện trạng | Hệ quả thiết kế |
|---|---|---|
| Số lượng bán từng SKU/ngày | Có ~30 ngày | Dự báo ở **độ phân giải ngày**, không hứa dự báo theo giờ/ca |
| Doanh thu, giá bán, danh mục món | Có | Báo cáo doanh thu/ngày, đối soát cơ bản |
| BOM/định lượng nguyên liệu | Có | Quy đổi doanh số bán thành nguyên liệu lý thuyết |
| Nhập hàng, tồn kho, kiểm kê | Có | Kiểm tra vị thế tồn kho và lập kế hoạch nhập có phê duyệt |
| Topping chuẩn bị và hủy | Ghi nhận **cuối ngày** | Phân tích lượng/tỷ lệ hủy theo ngày; cần kiểm tra độ dài lịch sử thực có |
| Bán theo khung giờ; nhật ký ca | Không có | **Loại khỏi MVP** chức năng tối ưu theo giờ/ca |

**Giới hạn quan trọng:** 30 ngày đủ để dựng và kiểm tra pipeline, nhưng **chưa đủ để khẳng định mô hình ML phức tạp hay mức tiết kiệm dài hạn**. Pilot thực tế cần tiếp tục thu thập dữ liệu nhiều tuần.

## 2. Problem statement và pain points

| Mã | Vấn đề thực tế cần xác minh | Tác động | Cơ hội sản phẩm |
|---|---|---|---|
| P-01 | Quyết định chuẩn bị topping chủ yếu dựa vào kinh nghiệm | Có thể chuẩn bị dư/hủy hoặc thiếu bán | Đề xuất lượng chuẩn bị **theo ngày** với sai số/bất định |
| P-02 | Nhiều món dùng chung nguyên liệu, khó tính đủ nhu cầu | Nhập thiếu/dư, tồn không cân đối | Quy đổi demand forecast qua BOM có version |
| P-03 | Lượng topping hủy ghi cuối ngày nhưng khó phân tích xu hướng | Không biết ngày/món/nguyên liệu nào cần điều tra | Dashboard waste theo ngày, chi phí, xu hướng, bằng chứng |
| P-04 | Tồn kho, mua hàng, kiểm kê và doanh số tách rời | Mất thời gian đối chiếu | Một workflow dữ liệu có xác nhận và audit |
| P-05 | Báo cáo bán hàng không trực tiếp chỉ ra việc nên làm | Phụ thuộc kinh nghiệm quản lý | Agent chủ động đề xuất hành động có giải thích |
| P-06 | Khi dự báo sai không có phản hồi hệ thống | Sai lặp lại | Closed-loop evaluation: kế hoạch → thực tế → đánh giá |

**Giả thuyết nghiên cứu H1:** So với quy trình thủ công, công cụ Forecast + Optimizer có thể giảm thời gian lập kế hoạch hoặc rủi ro thiếu/dư trong mô phỏng.  
**Giả thuyết H2:** Thêm Agent + Verification giúp xử lý ngoại lệ và truy vết quyết định tốt hơn so với dashboard/optimizer thuần túy.  
**Không mặc định:** AI Agent làm dự báo chính xác hơn một thuật toán forecast dùng cùng dữ liệu.

## 3. Người dùng và Jobs-to-be-done

### Primary persona — Quản lý cửa hàng
- **JTBD:** “Cuối ngày tôi muốn nhập số bán và nguyên liệu đã chuẩn bị/hủy để biết ngày mai cần làm gì, tại sao, và rủi ro ở đâu.”
- **Tiêu chí thành công:** nhập liệu nhanh; nhìn thấy đề xuất hợp lý; có quyền sửa/chấp thuận; có thể đối chiếu nguồn.

### Secondary persona — Chủ cửa hàng
- **JTBD:** “Tôi muốn xem hiệu quả nhập và sử dụng nguyên liệu mà không phải tính thủ công nhiều bảng.”
- **Tiêu chí thành công:** có dashboard, lịch sử kế hoạch, chênh lệch, tỷ lệ sử dụng thực tế; kiểm soát quyền.

### Supporting persona — Nhân viên được ủy quyền
- **JTBD:** “Tôi ghi lượng đã chuẩn bị, hủy và kiểm kê cuối ngày mà không phải học phần mềm phức tạp.”
- **Tiêu chí thành công:** biểu mẫu đơn giản, xác nhận đơn vị và thời điểm; không chỉnh sửa giá/BOM nếu không có quyền.

## 4. Product goals, non-goals

### P0 — Bắt buộc trong MVP 30 ngày
1. **Data Import & Review:** nhập CSV/Excel; nhận báo cáo ngày theo mẫu; phát hiện thiếu ngày, trùng SKU, số âm, sai đơn vị; duyệt trước khi ghi. Ảnh báo cáo được hỗ trợ dạng *optional assisted import* nếu còn thời gian.
2. **Daily Analytics:** doanh số, doanh thu, Top SKU, biểu đồ xu hướng, theo dõi lịch sử chuẩn bị và hủy topping.
3. **Recipe/BOM & Inventory:** danh mục nguyên liệu, quy đổi đơn vị, phiên bản BOM, đơn nhập, kiểm kê, số tồn tại thời điểm có bằng chứng.
4. **Demand Forecasting:** baseline Seasonal Naive + Moving Average cho 1 ngày; khả năng forecast 7 ngày nhưng phải hiển thị độ tin cậy thấp khi dữ liệu hạn chế.
5. **Daily Preparation & Replenishment:** tính nhu cầu topping/nguyên liệu theo BOM; đề xuất số lượng dựa vào forecast, tồn, lead time, pack/batch size, chính sách cửa hàng.
6. **AI Agent & Approval:** Agent gọi tool, trích dẫn số liệu nguồn, hỏi khi thiếu dữ liệu, kiểm chứng độc lập, tạo **draft** chờ phê duyệt, audit log.
7. **Benchmark & Shadow Mode:** chạy đề xuất song song, không tự thay đổi vận hành, ghi kết quả dự báo và kết quả kiểm kê.

### P1 — Sau MVP
- Hỗ trợ chụp ảnh OCR/VLM kèm màn hình xác nhận.
- Chi phí hủy topping, nếu có **giá vốn thực tế đã được phép sử dụng**.
- Phát hiện chênh lệch tồn kho nâng cao, theo dõi hạn sử dụng theo lô.
- Phân quyền multi-store, tích hợp POS API có quyền truy cập hợp lệ.

### Không thuộc phạm vi (out of scope)
- Thu ngân/POS mới, thanh toán, kế toán pháp định; quản lý nhân sự đầy đủ.
- Dự báo số ly theo giờ/ca; tối ưu topping theo ca khi không có dữ liệu giờ.
- Tự sửa công thức tiêu chuẩn, quy định bảo quản, nhà cung cấp bắt buộc.
- Tự gửi lệnh mua hàng, ghi nhận nhập kho hoặc thanh toán **không qua phê duyệt**.
- Khẳng định giảm hao hụt thực tế chỉ bằng chạy dữ liệu lịch sử/mô phỏng.

## 5. Luồng nghiệp vụ (user journeys)

### UJ-01: Chốt dữ liệu bán hàng ngày
1. Quản lý nhập báo cáo cho ngày D (CSV/Excel hoặc nhập tay).
2. Hệ thống đối chiếu mã món chuẩn, số lượng, ngày, doanh thu, trùng bản ghi.
3. Người có quyền xác nhận; dữ liệu được gắn `source_file`, `import_batch_id`, `verified_by`.
4. Dashboard cập nhật; phiên bản forecast cũ không bị ghi đè mất lịch sử.

### UJ-02: Tối ưu chuẩn bị topping cho ngày D+1
1. Agent được kích hoạt sau khi dữ liệu D đã duyệt.
2. Tool dự báo nhu cầu SKU; recipe engine tính nhu cầu topping lý thuyết.
3. Tool đọc tồn usable, mẻ tối thiểu, quy tắc an toàn/hạn dùng do cửa hàng xác nhận.
4. Optimizer tạo các phương án, biểu diễn đánh đổi giữa thiếu và dư.
5. Validator kiểm tra ràng buộc; Agent trình bày **số lượng, lý do, giới hạn dự báo, nguồn**.
6. Quản lý duyệt/từ chối, tùy chỉnh phù hợp quy trình.
7. D+1 kết thúc, nhân viên nhập **lượng đã chuẩn bị** và **lượng hủy**; hệ thống đánh giá khác biệt.

### UJ-03: Đề xuất nhập nguyên liệu
1. Lấy lượng tiêu thụ dự kiến từ SKU forecast/BOM.
2. Đối chiếu tồn thực tế tại lần kiểm kê gần nhất + nhập/xuất/điều chỉnh được xác nhận; kiểm tra hàng đang về.
3. Giải bài toán lượng nhập, quy cách đóng gói và ngân sách (nếu có dữ liệu).
4. Ghi dự thảo; quản lý phê duyệt; **không tự gửi nhà cung cấp**.

### UJ-04: Xem nguyên nhân hao hụt
1. Người dùng hỏi: “Vì sao tuần này hủy topping A nhiều?”
2. Agent gọi `get_waste_summary`, `get_daily_sales`, `get_preparation_logs`, `get_recipe_usage`.
3. Trả lời có ngày tham chiếu và nguồn: biến động nhu cầu, lượng chuẩn bị, tỷ lệ hủy.
4. Nếu không có bằng chứng nguyên nhân, nói rõ: **“Có tương quan, chưa xác định nguyên nhân.”**

## 6. Yêu cầu chức năng có mã và acceptance criteria

| ID | Yêu cầu | Điều kiện chấp nhận tối thiểu |
|---|---|---|
| FR-01 | Import daily sales | Từ chối số lượng âm; xử lý duplicate có preview; upsert có version |
| FR-02 | Danh mục SKU và BOM | Tính đúng g/ml/pcs; BOM gắn ngày hiệu lực; test ít nhất 10 SKU |
| FR-03 | Inventory ledger | Mọi biến động có loại, nguồn, timestamp; không tự ghi tăng khi PO chưa nhận |
| FR-04 | Prep/Waste capture | Ghi riêng `prepared_qty`, `wasted_qty`, unit, business_date; nhiều lần nhập/ngày vẫn tổng hợp đúng |
| FR-05 | Dashboard | Lọc ngày, SKU, topping, hiển thị nguồn và ngày cập nhật gần nhất |
| FR-06 | Forecast | Tái lập được seed/split/model version; xuất dự báo 1 ngày, optional 7 ngày |
| FR-07 | Optimization | Không vi phạm ràng buộc cứng; hiển thị infeasible nếu không có nghiệm |
| FR-08 | Agent tool calling | Mỗi kết luận có `source_refs`, model/tool version; hỏi bổ sung nếu thiếu dữ liệu quyết định |
| FR-09 | Approval workflow | Tạo draft → pending → approved/rejected; chỉ role Manager/Owner có quyền duyệt |
| FR-10 | Auditability | Ghi ai, khi nào, nguồn dữ liệu, công cụ, kết quả, trạng thái phê duyệt |
| FR-11 | Shadow evaluation | Kế hoạch mô phỏng tách khỏi số liệu kế toán/tồn kho thực tế |
| FR-12 | Export | Xuất báo cáo kế hoạch/so sánh ra CSV/PDF là P1; CSV ưu tiên |

## 7. Yêu cầu phi chức năng

- **An toàn dữ liệu:** HTTPS, tài khoản riêng, RBAC backend, secrets trong environment, log che thông tin nhạy cảm; không tải báo cáo nội bộ lên dịch vụ ngoài khi chưa được phép.
- **Phân lập cửa hàng:** mọi truy vấn kiểm tra `store_id` thuộc người dùng; hướng SaaS có `tenant_id`.
- **Độ tin cậy:** import idempotent, có rollback; forecast và optimize có timeout/fallback; Agent không ghi trực tiếp các bảng nghiệp vụ.
- **Khả năng tái lập:** mỗi báo cáo/forecast/plan lưu thời điểm, snapshot, phiên bản rule/BOM/model.
- **Hiệu năng MVP mục tiêu:** dashboard dữ liệu 30–90 ngày mở trong vài giây trên môi trường thử nghiệm; nhiệm vụ Agent 1–2 phút tối đa tùy LLM/network; benchmark đo thực tế.
- **Khả dụng:** web responsive cho điện thoại quản lý; form cuối ngày thao tác nhanh, ít trường bắt buộc.
- **An toàn thực phẩm:** kết quả AI không được dùng để vượt qua quy định an toàn/thời gian bảo quản/quy trình nhượng quyền.

## 8. Logic nghiệp vụ và định nghĩa KPI

### Lượng tiêu thụ lý thuyết theo BOM

\[
Usage^{theory}_{i,d}=\sum_s Sales_{s,d}\times BOM_{s,i,d}
\]

Đơn vị phải quy về cùng base unit; lịch sử tính theo **BOM có hiệu lực tại ngày bán**.

### Lượng hủy và tỷ lệ hủy

\[
WasteRate_{i,d}=\frac{WasteQty_{i,d}}{PreparedQty_{i,d}}\times100\%
\]

Chỉ tính khi cùng đơn vị, `PreparedQty > 0`, số liệu tương ứng **cùng cohort/mẻ** hoặc quy tắc kế toán được xác định; không mặc định `prepared - wasted = consumed` khi còn topping từ hôm trước/được chuyển sang hôm sau.

### Inventory reconciliation

\[
ExpectedClosing = Opening + Received - ExpectedUsage - LoggedWaste + Adjustments
\]

`ExpectedUsage` dựa BOM là **ước tính**, chênh lệch với kiểm kê không tự chứng minh thất thoát; cần xét mẫu thử, làm lại, khuyến mãi, sai nhập liệu và các trường hợp đặc thù.

### Chỉ số nghiên cứu
- Dự báo: MAE, WAPE (chỉ tính khi tổng thực tế > 0), Bias; luôn kèm số ngày/SKU đánh giá.
- Tối ưu: tổng chi phí mô phỏng (mua + tồn + thiếu + hủy), predicted shortage, waste proxy và constraint violations.
- Waste thực tế: kg/đơn vị hủy, chi phí hủy (nếu có giá vốn), WasteRate theo định nghĩa đã xác thực.
- Agent: Task Success Rate, Tool Argument Accuracy, Evidence Traceability, Unauthorized Action Rate, Time-to-Decision.
- Sản phẩm: số lần dùng/tuần, thời gian nhập liệu, tỷ lệ chấp nhận đề xuất, lỗi thao tác.

## 9. Benchmark & nguyên tắc so sánh

| Nhóm | Baseline A | Baseline B | Proposed |
|---|---|---|---|
| Demand | Yesterday/Seasonal Naive | 7-day Moving Average | Chọn baseline tốt hơn bằng rolling backtest, có thể thử model khác sau |
| Inventory | Mức tồn tối thiểu cố định | Forecast + deterministic optimizer | Cùng optimizer + Agent xử lý ngoại lệ, kiểm chứng, approval |
| Workflow | Excel/thủ công | Dashboard tự động | Agent điều phối dựa trên evidence |

**Quan trọng:** Nếu cùng dùng một forecast + optimizer, Agent **không tự nhiên tối ưu hơn**; giá trị cần chứng minh nằm ở chất lượng xử lý ngoại lệ, tính giải thích, thời gian quản lý và khả năng tuân thủ. Với 30 ngày, đánh giá forecast 1 ngày bằng rolling-origin; dự báo 7 ngày chỉ công bố như exploratory, không claim độ ổn định.

## 10. Điều kiện pilot & quyền dữ liệu

1. Có sự đồng ý của chủ thể có thẩm quyền đối với việc xuất/sao chép dữ liệu Mixue, đặc biệt là BOM và giá vốn.
2. Dữ liệu thực tế được ẩn thông tin nhận diện cửa hàng, nhân viên, khách hàng; không chia sẻ công thức độc quyền trong repo công khai.
3. Ban đầu chạy **shadow mode**, không thay đổi chuẩn bị thực tế. Chỉ chuyển sang được phê duyệt khi đáp ứng quy trình cửa hàng.
4. Thu thập thêm 30–60 ngày mới để đánh giá xu hướng; không lấy một ngày hiệu quả làm bằng chứng tác động.

## 11. Rủi ro và phương án giảm thiểu

| Rủi ro | Mức độ | Đối sách |
|---|---|---|
| Chỉ có 30 ngày lịch sử | Cao | Baseline đơn giản, rolling backtest, tiếp tục thu thập |
| Prep/waste log ít ngày hoặc lệch đơn vị | Cao | Chạy feature ở dạng analytics trước, có status `insufficient_data` |
| Dữ liệu bán không tách topping tùy chọn | Cao | Chỉ tính nguyên liệu chắc chắn theo BOM; thiếu thì không suy đoán |
| Tồn kho chụp snapshot không liên tục | Trung bình | Ledger + stock count anchor; luôn hiển thị ngày tồn đáng tin |
| Nhập liệu ảnh sai tên SKU/số lượng | Trung bình | Human confirmation; OCR P1 |
| Mua/nhập tự động gây sai phạm | Cao | Human approval + policy validator + sandbox |
| Nhiều tính năng trong 30 ngày | Cao | P0 rõ ràng; ưu tiên một vertical slice end-to-end |

## 12. Definition of Done sau 30 ngày

- [ ] Import được tối thiểu một tập dữ liệu bán/ngày, tồn kho, BOM, prep/waste có xác nhận.
- [ ] Dashboard doanh số và lượng hủy theo ngày; có ghi chú phạm vi dữ liệu.
- [ ] Có forecasting baseline và backtest **không rò rỉ dữ liệu tương lai**.
- [ ] BOM engine tính nhu cầu nguyên liệu chính xác trên test cases.
- [ ] Optimizer đề xuất chuẩn bị topping/ngày và/hoặc nhập hàng, ràng buộc được kiểm thử.
- [ ] Agent gọi tools → giải thích → `verify_plan` → draft → người quản lý phê duyệt.
- [ ] Audit và policy bảo vệ dữ liệu/role hoạt động.
- [ ] Golden dataset ít nhất 30 ca cho MVP, roadmap nâng lên 100 ca sau tháng đầu.
- [ ] Có báo cáo kết quả shadow pilot ban đầu; phân biệt rõ kết quả mô phỏng và kết quả thực tế.

## 13. Tài liệu liên quan

- [ARCHITECTURE_ADR.md](ARCHITECTURE_ADR.md): kiến trúc, schema, công cụ Agent và các quyết định kỹ thuật.
- [HUONG_DAN_CHUAN_BI_DU_LIEU.md](HUONG_DAN_CHUAN_BI_DU_LIEU.md): hợp đồng dữ liệu, ví dụ CSV, quy tắc làm sạch và đánh giá.
