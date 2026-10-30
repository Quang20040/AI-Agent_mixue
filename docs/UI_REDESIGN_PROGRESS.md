# UI Redesign Progress (Mixue mockup style)

> File checkpoint — cập nhật sau MỖI bước để nếu phiên làm việc bị ngắt (hết token) vẫn biết đã làm gì / còn gì.

## Mục tiêu
Làm lại UI Streamlit theo 5 ảnh mẫu: sidebar trái cố định, topbar (chi nhánh / ngày / tìm kiếm / chuông / avatar),
banner hồng + Tuyết Vương mỗi trang, thẻ KPI, biểu đồ cột 7 ngày, chat AI dạng dashboard.

## Kiến trúc
- `src/dashboard/mockup.css` — lớp CSS phủ lên `brand.css` (nạp cuối cùng trong `install_brand`).
- `src/dashboard/brand_ui.py` — `render_sidebar_top/bottom`, `render_topbar`, `render_page_hero`, `render_kpi_cards`, `render_revenue_chart`, `render_home`.
- `src/dashboard/app.py` — sidebar mới + radio điều hướng (vertical, có icon qua `format_func=nav_label`; giá trị radio giữ nguyên nên logic phân quyền không đổi).
- `src/dashboard/assets/snow-king-cutout.png` — linh vật nền trong suốt (tạo từ snow-king.png).
- `scripts/ui_shot.py <nav_index> <out.png> [user] [pass]` — chụp màn hình bằng Playwright (server: `streamlit run src/dashboard/app.py --server.port 8599`).

## Checklist
- [x] Khảo sát code
- [x] mockup.css (tokens, sidebar, topbar, hero, KPI, card, chart)
- [x] install_brand nạp mockup.css + ẩn brandbar cũ
- [x] Sidebar mới (logo, thẻ cửa hàng, thẻ user, nav dọc có icon, đăng xuất, linh vật)
- [x] Topbar + hero từng trang
- [x] Trang chủ: 4 KPI + biểu đồ 7 ngày + thực đơn
- [ ] Trang Tuyết Vương AI: chip gợi ý + bong bóng chat kiểu mẫu (đã có hero + khung chat)
- [ ] Tinh chỉnh Quản lý nhân viên (KPI nhân sự, bảng) / Tem & công thức (2 cột BOM) theo mẫu
- [ ] Panel phải (nguồn dữ liệu, dự báo, việc cần làm) cho trang AI
- [ ] Responsive mobile check

## Nhật ký
- Đã chạy thật bằng Streamlit + Playwright, Trang chủ và trang AI hiển thị đúng layout mới.
- Còn thiếu: các mục chưa tick ở trên.

## Bản thiết kế theo bộ ảnh desktop/mobile — 16/10/2026

Đã bổ sung trực tiếp vào ứng dụng Streamlit:

- `src/dashboard/dashboard.css`: lớp giao diện hoàn thiện nạp sau CSS hiện có; palette đỏ/hồng, SVG icon nội bộ, thẻ KPI, các ô chức năng nhanh, bố cục biểu đồ/phê duyệt và ba thẻ tổng quan.
- `brand_ui.py`: doanh thu và món bán chạy từ dữ liệu bán hàng thật, lệnh kho chờ duyệt từ dịch vụ hiện có, dự báo D+1 dùng engine trung bình trượt 7 ngày. Ngày dữ liệu và ngày dự báo hiển thị riêng; không sao chép số minh họa trong ảnh tham chiếu.
- Tìm kiếm chức năng bằng nút trên header hoặc Ctrl/Cmd K: hỗ trợ tìm không dấu, Enter, Escape, giữ focus trong hộp thoại và chỉ liệt kê các trang được phép truy cập.
- Điều hướng dưới cùng trên điện thoại dùng widget Streamlit thật; đồng bộ với sidebar và quyền truy cập.
- Trang Tuyết Vương AI có khung hội thoại và cột dữ liệu/công thức; các nguồn dữ liệu được đếm từ database.
- `motion.js` phiên bản 4: banner nhiều lớp, mascot và sản phẩm nổi, ngôi sao chuyển động, thẻ xuất hiện với chiều sâu 3D khi vào khung nhìn, biểu đồ mọc cột, nghiêng thẻ theo chuột. Có tạm dừng, nhận thay đổi `prefers-reduced-motion`, hủy listener/animation cũ khi rerender và tạm dừng chuyển động ngoài khung nhìn.
- CSS được đưa vào vùng style chuyên dụng của Streamlit để tránh tạo khoảng trắng từ các đoạn HTML ẩn.

### Kiểm tra

- `python -m pytest tests/test_dashboard.py -q`: đăng nhập, phân quyền, công thức, các trang quản trị, đăng xuất và đồng bộ điều hướng mobile/sidebar.
- `python scripts/check_dashboard_responsive.py`: mở dashboard cục bộ trên cổng 8599 bằng Chromium, kiểm tra trang chủ ở 320, 375, 390, 430, 768, 1024, 1280, 1440 và 1920 px; kiểm tra thêm 8 trang ở 320/390/768 px.
- Đã xác nhận không tràn ngang cấp trang tại các kích thước trên; Ctrl K, thẻ chức năng, điều hướng mobile, pause/resume và tùy chọn giảm chuyển động hoạt động; không có lỗi JavaScript trình duyệt trong lượt kiểm tra.
- Ảnh chụp và báo cáo: `output/dashboard-review/`.

Các công việc chưa tick trong checklist cũ ở trên là ghi chú của bản trước; bản này hoàn thiện cột thông tin AI theo dữ liệu/công thức có sẵn, không tạo dữ liệu thời tiết hoặc danh sách công việc giả.
