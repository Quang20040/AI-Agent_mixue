# Cài đặt môi trường và tạo bộ dữ liệu đầy đủ

**Đã bổ sung mẫu tiếng Việt:** ưu tiên điền 7 file trong `DU_LIEU_CAN_NHAP` và đọc
[hướng dẫn tiếng Việt](HUONG_DAN_NHAP_LIEU.md). Công cụ kiểm tra đọc được cả mẫu
tiếng Việt mới và mẫu tên cột kỹ thuật dưới đây. Hai bộ mẫu là hai lựa chọn nhập;
không cần điền cả hai hoặc gộp chúng với nhau.

## 1. Đã chuẩn bị những gì?

- `.env`: cấu hình phát triển local; mật khẩu DB và khóa JWT sinh ngẫu nhiên, không in ra log.
- `.env.example`: mẫu cấu hình không chứa bí mật để chia sẻ qua Git.
- `docker-compose.yml`: PostgreSQL 16, chỉ mở cổng trên máy local và lưu dữ liệu trong volume.
- `scripts/setup_local.py`: chạy lại an toàn, không ghi đè `.env` hoặc file nhập đã có.
- `data/templates`: 7 mẫu CSV chỉ có tiêu đề, trích đúng hợp đồng tài liệu 04.
- `data/staging_private`: bản mẫu để bạn điền dữ liệu thật.
- `data/public_examples`: ví dụ giả lập nguyên bản tài liệu 04, không phải dataset hoàn chỉnh.
- `scripts/validate_data.py`: kiểm tra sơ bộ file CSV, không sửa file và không ghi vào DB.

Đây là cấu hình ở phạm vi dự án, không thay đổi biến môi trường Windows toàn máy.
Docker Compose tự đọc `.env` ở gốc. Ứng dụng Python/Next.js chưa tồn tại nên chưa có
module đọc những biến còn lại; khi triển khai phải dùng loader `.env` ở backend
và cấu hình frontend tương ứng. Không chép khóa LLM hoặc JWT vào biến `NEXT_PUBLIC_*`.

## 2. Bật môi trường local

Mở terminal tại thư mục dự án rồi chạy:

```powershell
python scripts/setup_local.py
docker compose up -d postgres
docker compose ps
```

Nếu báo không kết nối Docker engine, mở Docker Desktop, chờ engine chạy rồi thử lại.
Nếu cổng 5432 bị chiếm, sửa `POSTGRES_PORT` và phần cổng trong `DATABASE_URL` cùng lúc.
Nếu đổi user/password/database, cũng sửa `DATABASE_URL` cho khớp.
Thông tin khởi tạo PostgreSQL chỉ áp dụng lần đầu khi volume còn trống; đổi `.env`
không tự đổi mật khẩu bên trong DB đã có dữ liệu. Không xóa volume để xử lý lỗi này.

`DATABASE_URL` hiện dùng cho backend chạy trực tiếp trên máy. Khi backend được chạy
trong Compose, host phải là `postgres`, cổng 5432. Chưa tạo container API/web giả vì
chưa có mã ứng dụng để chạy. Chưa cài các thư viện FastAPI/LangGraph/Next.js ở bước này.
Công cụ chuẩn bị dữ liệu chỉ cần Python 3.11+ và thư viện chuẩn, không cần API trả phí.

### Nhóm biến và phần bạn cần cung cấp

| Nhóm | Nội dung | Việc cần làm |
|---|---|---|
| Local | môi trường, timezone `Asia/Ho_Chi_Minh`, cổng 8000/3000, CORS | Giữ mặc định khi phát triển |
| Cửa hàng | `STORE_ID=STORE_LOCAL` | Dùng mã ẩn danh này nhất quán trong CSV thật |
| DB/Auth | kết nối DB, mật khẩu, JWT, thời hạn 30 phút | Đã sinh khóa local; không chia sẻ `.env` |
| Dữ liệu | raw, staging, processed, reports, snapshots | Đường dẫn tương đối tính từ gốc dự án |
| Forecast | lịch sử tối thiểu 14 ngày, horizon 1 ngày, chu kỳ/cửa sổ 7 ngày, seed 42 | Cấu hình dự kiến; chưa có engine |
| Agent | timeout, giới hạn tool/retry, shadow mode, yêu cầu duyệt | Cấu hình dự kiến; không thay thế kiểm soát quyền trong backend |
| LLM | provider, base URL, API key, model | Để trống và `LLM_ENABLED=false` cho tới khi chọn nhà cung cấp |

Khi tích hợp LLM, điền `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`
từ tài khoản của bạn. Chỉ bật `LLM_ENABLED` và quyền truyền dữ liệu ngoài khi đã
có adapter ứng dụng và phạm vi dữ liệu được phép. Không cần gửi khóa cho cuộc trò chuyện.
Redis/Celery, S3 và OCR chưa bắt buộc theo ARD nên không dựng dịch vụ hoặc khóa giả.

## 3. Thu thập nguồn trước khi nhập

Chọn một khoảng 30 ngày liên tiếp, ví dụ **13/09/2026–12/10/2026**, hoặc khoảng bạn thực sự có.
Xin/xác nhận phạm vi sử dụng báo cáo, BOM và giá vốn. Lưu:

- Báo cáo bán theo món/ngày → `data/raw_private/sales_reports`.
- Phiếu nhập và kiểm kê → `data/raw_private/inventory_docs`.
- Phiếu chuẩn bị/hủy cuối ngày → `data/raw_private/preparation_waste_logs`.

Đặt tên có ngày, giữ nguyên bản gốc. Tạo danh sách nguồn riêng gồm `source_id`,
tên file, ngày báo cáo, báo cáo đầy đủ hay chỉ top món, người xác nhận, thời điểm
xác nhận, revision và checksum SHA-256. Ví dụ `sales_20261010` liên kết tới
`sales_2026-10-10.xlsx`. Không dùng tên nguồn giả cho số liệu thật.

Thư mục này nằm trong OneDrive. `.gitignore` chỉ chặn Git; hãy chọn nơi lưu không
đồng bộ nếu thỏa thuận dữ liệu yêu cầu. Không tự di chuyển dữ liệu khi chưa chốt nơi lưu.

## 4. Điền 7 file theo thứ tự

Mở file trong `data/staging_private` bằng Excel qua **Data → From Text/CSV**,
chọn UTF-8, dấu phẩy. Giữ mã SKU và ngày ISO dưới dạng Text khi nhập để tránh Excel
tự đổi mã/ngày. Khi lưu, dùng CSV UTF-8, giữ đúng hàng tiêu đề, không thêm dòng tiêu đề
báo cáo, dòng tổng, ô gộp hoặc công thức. Dùng `1200.5`, không dùng `1.200,5`.

| Thứ tự/file | Mỗi dòng là gì? | Nguồn và cách điền |
|---|---|---|
| 1. `menu_items.csv` | Một SKU trong một giai đoạn hiệu lực | Danh mục POS. Mỗi size/biến thể có định lượng khác cần mã rõ ràng. Giữ mã ổn định; giá đổi thì tạo giai đoạn mới |
| 2. `ingredients.csv` | Một nguyên liệu | Danh mục kho. Chọn `g`, `ml`, `pcs`; tách nguyên liệu sống và topping đã chế biến bằng mã khác nhau |
| 3. `recipe_bom.csv` | Một nguyên liệu trong một phiên bản công thức của SKU | Định lượng đã được phép dùng, lượng cho 1 món và ngày hiệu lực. Một món có nhiều nguyên liệu thì có nhiều dòng |
| 4. `sales_daily.csv` | Một cửa hàng × một ngày × một SKU | Số lượng bán từ báo cáo, doanh thu thực nếu có; nguồn thật; ban đầu `pending`, chỉ chuyển `verified` sau đối chiếu |
| 5. `purchases.csv` | Một chứng từ nhập × một nguyên liệu | Số thực nhận theo đơn vị cơ sở và ngày nhận thật. Đơn mới đặt chưa nhận không làm tăng tồn |
| 6. `stock_counts.csv` | Một lần kiểm × một nguyên liệu | Lượng đếm thực tế, thời điểm như `2026-10-12T22:00:00+07:00`, ngày kinh doanh, vai trò xác nhận |
| 7. `topping_daily.csv` | Một cửa hàng × một ngày × một topping đã chế biến | Tổng chuẩn bị/hủy, tồn đầu/cuối dùng được nếu biết, lý do nếu biết và nguồn |

Ví dụ cách đọc: bán 42 món SKU001 ngày 10/10 thì nhập quantity_sold=42. Nếu BOM
được duyệt là 30 g topping/món, nhu cầu lý thuyết là 1.260 g; không nhập con số này
thay cho lượng chuẩn bị thực tế. Các số ví dụ không phải công thức Mixue.

Nếu ghi topping nhiều lần/ngày, giữ nhật ký gốc và tổng hợp thành một dòng/ngày/topping
cho mẫu CSV này. Không ghi đè mất lịch sử hoặc trộn các đơn vị/phạm vi khác nhau.

### Những quy tắc bắt buộc khi điền

- Ô chưa biết để trống nếu trường cho phép; nếu bắt buộc thì ghi nhận thiếu và tìm nguồn, không đoán.
- Không có báo cáo khác với bán 0. Chỉ nhập 0 nếu nguồn đầy đủ xác nhận món đó bán 0.
- Giá niêm yết không thay cho doanh thu thực sau khuyến mãi/hoàn tiền.
- Đổi kg → g, L → ml; không đổi g ↔ ml bằng 1:1.
- Không dùng trân châu khô để đối chiếu trực tiếp với trân châu đã nấu.
- Không tự điền tồn chuyển ngày bằng 0 nếu chưa xác nhận quy tắc bảo quản.
- Với trường hợp hoàn hàng/sửa báo cáo, giữ chứng từ và revision; không ép số âm vào mẫu bán hàng không âm.

## 5. Bảy file chưa đủ cho mọi bài toán tối ưu

Để bộ dữ liệu **hoàn chỉnh theo chức năng**, cần ghi thêm các bảng/thông tin sau
(thiết kế cột bổ sung; chưa có importer/validator cho các bảng này):

| Bảng/thông tin | Trường cần thu thập |
|---|---|
| Lịch báo cáo | store_id, business_date, report_available, full_sku_report, zero_omission_confirmed, source_id, người/thời điểm duyệt |
| Mapping tên POS | source_name, sku_id, variant, effective_from/to, người duyệt |
| Chính sách topping | prepared_ingredient_id, batch_qty_base, shelf_life_rule_id, quy tắc carry-over, usable_qty và thời điểm, buffer đã duyệt, phiên bản/ngày hiệu lực |
| Yield chế biến | raw_ingredient_id, prepared_ingredient_id, input_qty/unit, output_qty/unit, nguồn đo, người/ngày duyệt |
| Nhà cung cấp/quy cách | supplier_id, ingredient_id, approved_supplier, pack_qty_base, min_packs, lead_time_days, review_period_days |
| Đơn đang về | order_id, ingredient_id, status, ordered_qty, received_qty, expected_received_date, supplier_id, source_id |
| Biến động kho | movement_id, ingredient_id, occurred_at, movement_type, quantity_signed_base, source_ref; tránh trừ hủy hai lần |
| Ràng buộc chi phí | Giá vốn theo base unit, ngân sách, sức chứa, safety stock, ngày hiệu lực và người duyệt nếu dùng các ràng buộc đó |
| Duyệt dữ liệu | dataset, row_ref, source_ref, verified_by, verified_at, revision, trạng thái và ngoại lệ |

Không có pack size/lead time/tồn đáng tin thì chỉ tính nhu cầu nguyên liệu, chưa gọi
đó là đơn nhập tối ưu. Không tự lấy một tỷ lệ buffer cố định từ LLM.

## 6. Kiểm tra, đối chiếu và khóa bộ dữ liệu

```powershell
python scripts/validate_data.py data/staging_private --start 2026-09-13 --end 2026-10-12 --output data/quality_reports/current.json
```

Thay ngày bằng kỳ của bạn. Công cụ kiểm tra cột, ô bắt buộc, số âm/sai kiểu,
khóa trùng, mã liên kết, đơn vị, topping sống/chín, giới hạn hủy, và cặp món/ngày thiếu.
Mã thoát 1 nghĩa là có lỗi. `REQUIRES_HUMAN_REVIEW` nghĩa là chưa thấy lỗi trong
phạm vi kiểm tra sơ bộ, **không phải** dataset đã đủ điều kiện sử dụng.

Còn phải duyệt thủ công: quyền dữ liệu, nguồn/checksum, đầy đủ báo cáo, chồng lấn
phiên bản BOM/giá, BOM có hiệu lực từng ngày, độ tươi tồn kho, lịch sử điều chỉnh,
phạm vi mẻ hủy, yield, chính sách an toàn và trạng thái đơn đang về.

1. Sửa từng lỗi và chạy lại, giữ bản nguồn và lịch sử sửa.
2. Đối chiếu tổng bán/doanh thu theo ngày với báo cáo gốc. Chênh lệch cần giải thích.
3. Nhờ người có thẩm quyền xác nhận mapping, BOM, prep/waste và tồn kho.
4. Sao chép **bản đã duyệt** sang `data/processed_private`; không ghi đè bản kỳ cũ.
5. Tạo thư mục snapshot mới trong `data/snapshots_private`, lưu file đã duyệt và
   manifest gồm snapshot_id, store_id, khoảng ngày, revision, người/thời điểm duyệt,
   checksum từng file và các thiếu sót đã chấp nhận. Không sửa snapshot cũ.

Chưa có API/màn hình import vào PostgreSQL. Đặt CSV trong staging là chuẩn bị đầu
vào, không phải đã nhập vào cơ sở dữ liệu. Không dùng lệnh COPY trực tiếp thay cho
workflow preview → xác nhận → version/audit khi ứng dụng được xây dựng.

## 7. Khi nào coi là đủ?

- **Dự báo:** hướng tới 30 ngày sales thật; ít nhất 14 ngày liên tiếp đáng tin,
  đủ lag, lịch missing/zero rõ ràng. Không đảm bảo chính xác chỉ vì đủ số dòng.
- **Nhu cầu nguyên liệu:** mọi SKU trong phạm vi có BOM hiệu lực và đơn vị được duyệt.
- **Phân tích hủy:** có prep và waste cùng phạm vi; số ngày topping phải thống kê riêng.
- **Kế hoạch topping:** thêm tồn dùng được, quy cách mẻ, hạn dùng, buffer/chính sách xác nhận.
- **Kế hoạch nhập:** thêm tồn có thời điểm, ledger, hàng đang về, lead time, pack size và nhà cung cấp được phép.
- **Agent:** còn cần ứng dụng, tool kiểm thử, kiểm chứng độc lập và luồng duyệt; CSV đầy đủ chưa đủ để bật Agent.

Mỗi ngày tiếp tục bổ sung sales, chuẩn bị/hủy, phiếu nhận và kiểm kê đúng thực tế.
Nếu thiếu lịch sử topping, bắt đầu ghi từ hôm nay; không tạo ngược dữ liệu giả.
