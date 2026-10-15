# Nguồn hình ảnh & chuyển động

Các ảnh sản phẩm được tải từ trang chính thức https://my.mixue.com/product_strength.html ngày 15/10/2026.
Ảnh trên thẻ thực đơn đại diện cho nhóm món, không bảo đảm trùng từng biến thể trong dữ liệu chi nhánh.

- lemonade.png: 2a001be18d17020f2a43c3147e429d82.jpg
- ice-cream.png: a04291fb2965e68b9821f361d043b6db.jpg
- strawberry.png: 480c25b495c6663980a22ba214ad4c22.jpg
- latte.png: a2f4cad72b13acb5d34bc0c11f289f87.jpg
- milk-tea.png: 83019d78bef038c11f4a7412be0bfbba.png

Nguồn gốc ảnh: https://mymixues.oss-ap-southeast-1.aliyuncs.com/uploads/images/202509/
Linh vật snow-king-reference.png: ảnh người dùng cung cấp trong cuộc trò chuyện.
Ảnh đã thu nhỏ để dùng tại máy; không phát sinh yêu cầu ảnh ra mạng khi mở ứng dụng.

GSAP 3.14.2 và ScrollTrigger 3.14.2 từ npm/CDN jsDelivr, giữ nguyên thông tin bản quyền và giấy phép trong thư viện.
Tài liệu: https://gsap.com/docs/v3/ và https://gsap.com/standard-license/

Chuyển động được quản lý trong ../motion.js; hỗ trợ prefers-reduced-motion, hủy animation và listener khi giao diện Streamlit cập nhật.

## Cập nhật ảnh theo từng món

39 mã món được ánh xạ riêng tại `product-images.json`. Mỗi bản ghi giữ tên món nội bộ, tên trên nguồn thực đơn, URL gốc và tệp ảnh đã tải.
Nguồn thực đơn Việt Nam: https://mixuevn.net/ (ảnh sản phẩm từ CDN ShopeeFood được trang liên kết) và https://mixuevietnam.net/ (Kem ốc quế).
Đây là các trang giới thiệu thực đơn, không coi là website chính thức của tập đoàn Mixue.
Ba mã DK3/ST2/THQ8 dùng ảnh Việt quất phiên bản hiện tại Buff Xanh/Hồi Mana/Triple Kill; ghi chú hiển thị trên thẻ.
Các biến thể size L giữ đúng dòng món; không dùng ảnh của món khác.

Linh vật tự vẽ đã được loại khỏi mã giao diện, kể cả avatar chat và thanh bên. Tất cả dùng `snow-king-reference.png` do người dùng cung cấp.
GSAP lặp chuyển động ở hero, Tuyết Vương, ảnh món, ánh sáng, ngôi sao và dải chữ; tự chạy theo yêu cầu người dùng và có nút tạm dừng.
