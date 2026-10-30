# Đã nhập gì từ 19 ảnh?

Đây là **bản dữ liệu chờ đối chiếu**, chưa phải dữ liệu đã duyệt để chạy dự báo hoặc đặt hàng.

## Các bảng đã điền

| File | Kết quả |
|---|---|
| 01_Danh_muc_mon.csv | Giữ 39 món, mã và giá bạn đã điền. Chỉ đổi cách ghi ngày từ 1/10/2023 sang 2023-10-01 |
| 02_Nguyen_lieu.csv | 73 dòng: giữ 40 mã kho số của bạn, bổ sung 33 mã nguyên liệu/bán thành phẩm dùng trong công thức. Hai dòng tiêu đề/rỗng lẫn trong dữ liệu đã bỏ |
| 03_Cong_thuc_dinh_luong.csv | 120 dòng định lượng, tương ứng 35 món đã có ít nhất một phần công thức |
| 08_Danh_sach_anh_nguon.csv | 19 ảnh, tên gốc, bản lưu và mã kiểm tra SHA-256 |
| 09_Cong_thuc_so_che_theo_me.csv | 67 dòng nguyên liệu đầu vào cho 22 quy cách mẻ của 9 loại bán thành phẩm |
| 10_Quy_dinh_bao_quan_theo_anh.csv | 12 dòng điều kiện bảo quản chép từ tài liệu |
| 11_Dinh_luong_topping_them.csv | 27 dòng topping thêm theo nhóm món |
| 12_Cac_diem_can_xac_nhan.csv | 19 vấn đề cần đối chiếu; nêu rõ nguồn và lý do |
| 13_Thoi_gian_so_che_theo_anh.csv | Thời gian ghi trong 9 công thức sơ chế |
| 14_Mon_trong_anh_chua_co_ma_menu.csv | 8 món/biến thể đọc rõ nhưng chưa có mã trong menu bạn nhập |
| 15_Han_dung_nguyen_lieu_tren_anh.csv | 20 dòng hạn dùng từ ảnh nhận diện; tách khỏi hạn sau mở bao và sau chế biến |
| 16_Quy_tac_duong_va_topping.csv | Quy tắc thêm topping và điều chỉnh đường đọc được từ ảnh |

**Bốn file 04–07 vẫn trống:** ảnh là tài liệu công thức/đào tạo, không phải báo cáo
số bán, phiếu nhập hàng, biên bản kiểm kê hay nhật ký chuẩn bị/hủy thực tế.

## Những gì không được tự suy ra

- Ngày 25/05/2026 và 17/07/2025 là ngày trên tài liệu. Chưa biết cửa hàng áp dụng
  từ ngày nào nên cột ngày hiệu lực của BOM vẫn trống. Ngày giá/menu 2023-10-01
  là do bạn nhập trước đó, không được áp ngược cho công thức 2026.
- “Thêm đến vạch/cách miệng cốc 0,8 cm” chưa cho lượng ml/g. Vì vậy 35 món có
  định lượng **một phần**, không phải 35 BOM đầy đủ gồm cả nước, đá và bao bì.
- Trà sữa 2J có 3 lựa chọn nhưng chỉ lấy 2. Đã đánh dấu các topping là tùy chọn.
- Kem ốc quế 120±10 g **tính cả vỏ**; chưa đưa vào BOM như 120 g kem.
- Chưa có công thức Việt Quất của DK3, THQ8, ST2.
- Công thức mẻ cho số cốc ước tính; không dùng số cốc để suy ngược lượng đầu ra
  hay quy đổi nguyên liệu sống thành topping chín.
- TP09 là cà phê tươi trong tài liệu 2026; TP10 là cà phê cô đặc từ bột hòa tan
  trong tài liệu 2025. Hai loại chưa được coi là cùng một nguyên liệu.
- TP11 là hỗn hợp kem trước máy; TP01 là kem tươi sau máy. Chưa có hệ số chuyển đổi.
- Tài liệu mật mã tháng 06/2025 chỉ làm nguồn tham khảo. Chưa nhập các món chỉ có
  trong bảng mật mã cũ thành BOM hiện hành hoặc ghi đè công thức mới.

## Bạn cần làm tiếp

1. Mở file **12_Cac_diem_can_xac_nhan.csv**, xác nhận ngày áp dụng công thức và
   các tên món/nguyên liệu tương ứng với thực tế cửa hàng.
2. Đối chiếu mã NL với mã kho số trước khi tính nhập hàng. Một số mã được tách
   vì danh sách ghi “syrup” trong khi ảnh ghi “mứt”; chưa được cộng như hai mặt hàng
   độc lập hoặc tự gộp nếu chưa xác nhận.
3. Bổ sung báo cáo bán từng món theo ngày vào file 04. Sau đó thêm phiếu nhận,
   kiểm kê và nhật ký chuẩn bị/hủy vào các file 05–07.

Chạy công cụ kiểm tra hiện vẫn báo thiếu ngày hiệu lực của 120 dòng BOM, thiếu
đơn vị cho giấy in hóa đơn/giấy tem/màng dập cốc, và thiếu bốn bảng vận hành.
Đây là các thiếu sót đang giữ công khai, không phải đã xác nhận đủ dữ liệu.

Bản gốc trước sửa nằm trong `backups/truoc_nhap_anh_20261013_160820` tại gốc dự án.
Ảnh gốc được sao chép vào `data/raw_private/anh_cong_thuc`. Mọi bảng thật, bản sao
và ảnh đều nằm trong đường dẫn bị loại khỏi Git. Việc này không tắt OneDrive.
