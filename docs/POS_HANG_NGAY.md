# Nạp số liệu bán hàng từ phiếu POS

Nguồn: màn hình POS **Báo biểu → Thống kê số lượng sản phẩm** (Sản phẩm + Phân loại), mỗi ngày một phiếu.

1. Chép từng dòng của phiếu vào `data/pos_daily/YYYY-MM-DD.csv` với các cột `name,category,quantity,amount_vnd`.
   `name` giữ đúng tên POS (bỏ hậu tố "(MT)"), `category` là nhóm in trên phiếu (TRÀ HOA QUẢ, TRÀ SỮA, KEM, CÀ PHÊ, SỮA THẠCH, TRÀ NGUYÊN CHẤT, TOPPING, ĐỒ LƯU NIỆM + ĂN VẶT).
2. Ghi phần cuối phiếu vào `data/pos_daily/manifest.json`: `items` (Tổng số lượng sản phẩm, không tính topping), `revenue_vnd` (Tổng doanh thu, có topping), `complete: true`.
   Nếu ngày đó còn thiếu ảnh thì ghi `complete: false`: số liệu vẫn được nạp nhưng ở trạng thái *Chờ xác nhận*.
3. Kiểm tra: `python -m src.engine.pos_import --check`. Ngày nào lệch với phiếu (sai một số lượng hay một số tiền) sẽ bị báo và **không** được nạp.
4. Khi deploy, app tự nạp các ngày mới hoặc vừa sửa lúc khởi động (`POS_IMPORT_AUTO=0` để tắt). Nạp lại một ngày sẽ ghi đè đúng ngày đó, không tạo trùng.

Tên POS được gán mã món trong `src/engine/pos_import.py` (`POS_TO_SKU`). Món mới chưa có trong thực đơn (`NEW_SKUS`) được tự thêm: kem ốc quế Matcha / Matcha Mix (DK11, DK12), Super sundae Ococo Matcha (DK13, DK14), Sữa tươi Matcha (TS12), Trà sữa hoa nhài (TS13), Trà sữa trân châu size L (TS14), Trà Việt Quất Triple Kill (THQ13), Americano cam / chanh (CF4, CF5), Hồng trà / Trà nhài mật ong (TNC1, TNC2), móc khóa (LN1), topping (TP1–TP8).
Gặp tên POS lạ, bước kiểm tra sẽ báo "Món POS chưa có mã" để bổ sung vào một trong hai bảng trên.
