# BẮT ĐẦU NHẬP DỮ LIỆU TẠI ĐÂY

Mở thư mục **DU_LIEU_CAN_NHAP**. Cả 7 file đều có tên và tiêu đề cột tiếng Việt.
Thư mục **MAU_MINH_HOA** (tạo ra khi chạy `python scripts/setup_local.py`) có ví dụ để nhìn cách điền; toàn bộ số liệu ở đó là giả lập.
Không sao chép các số ví dụ làm dữ liệu thật của cửa hàng.

## Điền lần lượt 7 file

| File | Bạn cần làm gì? |
|---|---|
| 01_Danh_muc_mon.csv | Mỗi dòng ghi một món: mã món, tên, kích cỡ, giá bán, ngày bắt đầu áp dụng. Cột Đang bán điền Có hoặc Không |
| 02_Nguyen_lieu.csv | Mỗi dòng ghi một nguyên liệu. Đơn vị dùng g, ml hoặc cái. Nhóm ghi Nguyên liệu khô, Si rô, Topping đã chế biến hoặc Bao bì |
| 03_Cong_thuc_dinh_luong.csv | Mỗi dòng là một nguyên liệu cần cho một món. Ví dụ một món dùng 3 nguyên liệu thì ghi 3 dòng. Cột Là thành phần tùy chọn điền Có hoặc Không |
| 04_Ban_hang_hang_ngay.csv | Mỗi ngày, mỗi món ghi một dòng số bán và doanh thu thực. Trạng thái điền Chờ xác nhận, Đã xác nhận hoặc Từ chối |
| 05_Nhap_hang.csv | Ghi nguyên liệu và số lượng thực nhận theo từng phiếu nhập. Ngày đặt khác ngày nhận; chưa nhận thì không cộng vào tồn |
| 06_Kiem_ke.csv | Ghi số đếm thực tế và thời điểm kiểm. Vai trò người xác nhận ghi Quản lý, Chủ cửa hàng hoặc Nhân viên |
| 07_Chuan_bi_va_huy_topping.csv | Mỗi ngày, mỗi topping ghi tổng đã chuẩn bị, đã hủy, tồn đầu/cuối còn dùng được nếu biết |

**Mã món** do bạn đặt ổn định, ví dụ MON001. Cùng món phải dùng cùng mã ở danh mục,
công thức và bán hàng. **Mã nguyên liệu** cũng vậy, ví dụ NL001. Mã topping đã nấu
phải khác mã nguyên liệu khô. **Mã cửa hàng** dùng STORE_LOCAL hoặc một mã ẩn danh
bạn chọn thống nhất. **Mã chứng từ nguồn** là mã để tìm lại báo cáo/phiếu gốc.

## Cách mở và lưu bằng Excel

1. Mở Excel → Dữ liệu → Từ văn bản/CSV, chọn file cần điền.
2. Chọn mã hóa UTF-8 và dấu phân cách dấu phẩy; giữ cột mã và ngày dưới dạng văn bản.
3. Giữ nguyên hàng tên cột tiếng Việt, nhập dữ liệu bên dưới. Không thêm dòng tổng.
4. Lưu dạng CSV UTF-8. Ngày ghi `2026-10-13`; số thập phân ghi `1200.5`, không có dấu phân cách hàng nghìn.

Thời điểm kiểm kê ghi cả giờ và múi giờ, ví dụ `2026-10-13T22:00:00+07:00`.
Giá vốn là giá cho **1 g, 1 ml hoặc 1 cái**, không phải giá cả bao. Không có giá
vốn hoặc doanh thu thì để trống, không tự tính thay cho nguồn thật.

Ngày không có báo cáo không được tự điền bán 0. Chưa rõ tồn đầu/cuối ngày thì để
trống, không đoán. Không dùng công thức minh họa thay cho công thức thực đã được phép sử dụng.

## Kiểm tra sau khi điền

Mở terminal tại thư mục dự án, chạy lệnh sau (thay khoảng ngày theo dữ liệu của bạn):

```powershell
python -X utf8 scripts/validate_data.py DU_LIEU_CAN_NHAP --start 2026-09-13 --end 2026-10-12 --output BAO_CAO_KIEM_TRA/ket_qua.json
```

Thông báo trên màn hình dùng tiếng Việt, chỉ rõ file và dòng cần sửa. Dòng 0 là
thông báo chung cho cả file. Không có lỗi vẫn cần người quản lý đối chiếu và xác nhận.
File kết quả JSON giữ mã kỹ thuật để ứng dụng có thể đọc; phần diễn giải lỗi là tiếng Việt.

Để dự báo, hướng tới 30 ngày bán thật. Để lập kế hoạch chuẩn bị/nhập hàng còn cần
quy định hạn dùng, quy cách mẻ, quy cách đóng gói, thời gian giao, tồn dùng được và
đơn đang về. Xem [hướng dẫn chi tiết](docs/05_Cai_Dat_Va_Nhap_Du_Lieu.md).

Các tên biến trong `.env` là mã cấu hình cho phần mềm nên giữ nguyên. Bạn không
cần sửa chúng để nhập 7 file này. Dữ liệu thật trong DU_LIEU_CAN_NHAP đã được loại
khỏi Git; việc này không tắt đồng bộ OneDrive.
