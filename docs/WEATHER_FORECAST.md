# Dự báo theo sức bán và thời tiết

Luồng dùng chung: dashboard / Agent → `ForecastingEngine` → số ly từng SKU →
BOM → nhu cầu thành phẩm/nguyên liệu → kế hoạch sơ chế theo từng đợt.
LLM không tính hệ số mưa hoặc tự chọn con số sản lượng.

## Dữ liệu đầu vào và kiểm chứng

- Số ly từng món của ngày trước, cùng thứ tuần trước và trung bình 7 ngày.
- Doanh thu ngày trước được chuẩn hóa theo số ly thành giá bán bình quân/mix,
  tránh cộng doanh thu và số ly như hai nguồn sức mua độc lập.
- Thứ trong tuần; nhiệt độ, lượng mưa trong giờ bán và khung cao điểm 14–20h.
- Chênh lệch thời tiết ngày cần bán so với ước tính thời tiết ngày trước.

Mô hình bổ sung là hồi quy có regularization, học tổng nhu cầu cửa hàng.
Nó được so với mô hình chỉ có sức bán và mô hình nền, trên tối đa 14 ngày
kiểm chứng nối tiếp. Mỗi lần học chỉ dùng dữ liệu trước ngày đánh giá.
Việc chuẩn hóa biến và chọn mô hình nền cũng không đọc doanh số tương lai.
Mô hình được chọn bằng WAPE; kiểm chứng này phục vụ chọn mô hình, chưa thay thế
một tập kiểm tra độc lập dài hạn.

Lịch sử thời tiết dùng API Previous Runs: bản dự báo lưu từ trước 24 giờ cho
ngày đích, thay vì gắn thời tiết thực tế ngày tương lai vào backtest. Ngày trước
dùng bản ước tính day0; đây là dữ liệu mô hình, không phải số đo tại cửa hàng.
Dự báo cho hôm nay/ngày tới dùng bản dự báo hiện hành. Các ngày quá khứ dùng
bản day1 lưu trữ, không lấy thời tiết thực tế để giả làm dự báo.

Nếu mô hình sức bán + thời tiết thắng cả hai đối chứng, áp dụng hệ số học được
vào dự báo từng món. Hiện hệ số chung cho cả cửa hàng, chưa học độ nhạy mưa
riêng cho từng nhóm món hoặc kênh mua trực tiếp/giao hàng.

Nếu thời tiết không giúp giảm sai số, giữ mô hình sức bán hoặc mô hình nền.
Thiếu dữ liệu hôm trước, thiếu thời tiết, hoặc thời tiết nằm ngoài miền đã học
thì báo rõ. Không giả định mất kết nối là trời nắng, không bù ngày thiếu bằng
0 ly và không tự đặt “mưa giảm 30%”. Giới hạn an toàn hệ số 0,5–1,5 chỉ là giới
hạn triển khai, không phải mức tác động đã học hay khoảng tin cậy.

Dự báo nhiều ngày không dùng doanh số thực tế của những ngày sau thời điểm
lập dự báo. Chỉ ngày đầu đủ dữ liệu trễ để xét mô hình bối cảnh; các ngày sau
hiện dùng mô hình nền và có chú thích.

## Thời tiết và cấu hình

API Open-Meteo chỉ nhận tọa độ, ngày và biến thời tiết, không nhận doanh số.
Dữ liệu được lưu tạm ngoài Git tại `data/weather_private/`: dự báo hiện hành
tối đa 1 giờ, lịch sử tối đa 24 giờ. Metadata ghi nguồn và thời điểm lấy.

```dotenv
WEATHER_ENABLED=true
WEATHER_LATITUDE=21.0285
WEATHER_LONGITUDE=105.8542
WEATHER_LOCATION_LABEL="Hà Nội · điểm tham chiếu thành phố"
STORE_OPENING_HOUR=8
STORE_CLOSING_HOUR=22
```

Tọa độ mặc định là điểm tham chiếu thành phố, không phải tọa độ cửa hàng đã
được xác minh. Khi có tọa độ cửa hàng, thay đồng thời tọa độ và nhãn. API dùng
mô hình ECMWF IFS; không coi dự báo theo ô lưới là mưa đo ngay trước cửa quán.

Dashboard hiển thị thời tiết hai ngày, sức bán ngày trước, cảnh báo dữ liệu
thiếu và WAPE tính từ dữ liệu đang dùng. Không còn bảng WAPE 20,27% ghi cứng.
Khoảng thấp/cao của sản lượng chỉ là tham khảo từ dao động lịch sử, chưa phải
khoảng xác suất được hiệu chỉnh cho mô hình thời tiết.

## Sơ chế và định mức ước lượng

Đã sửa mã hàng để khớp danh mục: TP02 là trân châu nguyên vị đã nấu, đơn vị g;
TP07/TP08 là trà đã ủ, đơn vị ml. Validator từ chối đơn vị không khớp danh mục.

Theo yêu cầu người dùng, khi thiếu số đo đầu ra sẽ dùng ước lượng rõ nhãn:

| Thành phẩm | Đầu ra/mẻ tạm tính |
|---|---:|
| TP02 trân châu | 2.000 g đã ráo từ 1.000 g hạt khô |
| TP03 / TP04 thạch đã chế biến | 1.000 g |
| TP05 trà sữa lạnh | 5.000 ml |
| TP07 / TP08 trà đã ủ | 2.500 ml |
| NL06 / NL07 / NL08 topping dùng pha món | 1.000 g mỗi đơn vị chuẩn bị |

Đây là giả định lập kế hoạch, không phải định lượng Mixue đã xác nhận. Riêng
trân châu có kịch bản ±25% đầu ra (1,5–2,5 kg từ 1 kg hạt khô), không phải
khoảng tin cậy thống kê. Thay định mức trân châu ngay trên trang Sơ chế rồi
tính lại; Agent cũng có tham số `pearl_yield_g`. Đổi định mức không tự biến
ước lượng thành số đo đã kiểm chứng.

Nhu cầu thành phẩm = tổng số ly dự báo từng SKU × BOM. Trừ tồn còn dùng được
(hiện chưa có xác nhận hạn dùng theo lô, mặc định không tính tồn mở ca), thêm
buffer rồi làm tròn theo đầu ra/mẻ tạm tính. Chỉ trân châu có thêm quy đổi ra
hạt khô; không coi gram thành phẩm của mọi topping là gram nguyên liệu khô.

Đợt đầu tính theo nhu cầu trong tối đa 4 giờ đầu, tạm chia đều theo giờ mở
cửa rồi làm tròn. Đây chưa phải mô hình theo giờ cao điểm. Trước đợt tiếp theo
cần đối chiếu POS và hạn dùng, không nấu hết lượng cả ngày ngay đầu ca.
Hạn dùng và cách nấu tiếp tục tra đúng SOP, không được suy ra từ định mức ước
lượng. Topping đóng gói được ghi chia phần, không mặc định đều phải luộc/nấu.

## Kiểm tra

Agent có công cụ công khai `get_weather_forecast(target_date)` độc lập với
doanh số: gọi Open-Meteo/ECMWF theo tọa độ cấu hình, trả dự báo theo giờ,
giờ có mưa còn lại, nguồn URL, thời điểm lấy và giới hạn dữ liệu. Cache tối
đa 60 phút; lỗi hoặc dữ liệu thiếu không được diễn giải thành trời khô.
Với hôm nay chỉ dùng từ giờ hiện tại trở đi cho lời khuyên. Chỉ hỗ trợ hôm
nay và 6 ngày tới. Đây là một nguồn, chưa đối chiếu đa nguồn; lưới ECMWF
0.25° khoảng 25 km, không phải dự báo chính xác từng số nhà.

Ngày 16/10/2026, cấu hình cục bộ được đổi từ điểm tham chiếu Hà Nội sang
ghim Google Maps người dùng cung cấp: 21.0520041, 105.7859159,
“Mixue KĐT Nam Cường - Cổ Nhuế”. Tọa độ lấy từ trường địa điểm `!3d/!4d`,
không lấy tâm khung nhìn bản đồ. Không mặc định ghim này là số nhà đã được
đơn vị địa chính xác minh. Cấu hình mẫu vẫn yêu cầu chọn vị trí phù hợp.

Khuyến nghị vận hành tách riêng khỏi điều chỉnh số ly: nếu dự báo có mưa
trong giờ bán, Agent và trang dự báo/sơ chế gợi ý chuẩn bị ít hơn ở đợt đầu,
chia mẻ nhỏ và bổ sung theo POS, đơn giao hàng, tồn còn dùng được. Gợi ý này
vẫn xuất hiện khi giữ mô hình nền; không tự cắt nhu cầu cả ngày, không gán
phần trăm giảm và không thay đổi định lượng dự thảo. Không có dữ liệu mưa
hợp lệ thì không khẳng định trời mưa. Dự báo mưa không phải quan trắc thực tế.

```powershell
python -m pytest tests/test_weather_forecast.py tests/test_forecasting.py tests/test_optimizer.py -q
python -m pytest tests/test_dashboard.py -q
```

Các kiểm thử gồm tác động mưa học từ dữ liệu giả lập, mưa không có tác động,
thời tiết cực đoan ngoài miền, lỗi API, ngày thiếu, biến D+1 thiếu, lọc giờ bán,
không dùng dữ liệu tương lai, tách cửa hàng, đổi định mức và đối chiếu đơn vị.

Tài liệu đối chiếu: [Open-Meteo Forecast API](https://open-meteo.com/en/docs),
[Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api).
