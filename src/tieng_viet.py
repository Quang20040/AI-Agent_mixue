"""Tên hiển thị tiếng Việt; mã nội bộ vẫn tương thích tài liệu thiết kế."""
TEP = {
    'menu_items': '01_Danh_muc_mon', 'ingredients': '02_Nguyen_lieu',
    'recipe_bom': '03_Cong_thuc_dinh_luong', 'sales_daily': '04_Ban_hang_hang_ngay',
    'purchases': '05_Nhap_hang', 'stock_counts': '06_Kiem_ke',
    'topping_daily': '07_Chuan_bi_va_huy_topping',
}
COT = dict(pair.split('|') for pair in '''sku_id|Mã món
sku_name|Tên món
variant|Kích cỡ hoặc biến thể
selling_price_vnd|Giá bán niêm yết (đồng)
effective_from|Có hiệu lực từ ngày
effective_to|Có hiệu lực đến ngày
is_active|Đang bán
ingredient_id|Mã nguyên liệu
ingredient_name|Tên nguyên liệu
base_unit|Đơn vị cơ sở
unit_cost_vnd|Giá vốn mỗi đơn vị cơ sở (đồng)
ingredient_group|Nhóm nguyên liệu
shelf_life_rule_id|Mã quy định hạn sử dụng
recipe_id|Mã phiên bản công thức
quantity_per_item|Lượng nguyên liệu cho một món
unit|Đơn vị
is_optional|Là thành phần tùy chọn
business_date|Ngày kinh doanh
store_id|Mã cửa hàng
quantity_sold|Số lượng đã bán
revenue_vnd|Doanh thu thực tế (đồng)
source_id|Mã chứng từ nguồn
verification_status|Trạng thái xác nhận
purchase_id|Mã phiếu nhập
order_date|Ngày đặt hàng
received_date|Ngày thực nhận
quantity_received|Số lượng thực nhận
count_id|Mã lần kiểm kê
counted_at|Thời điểm kiểm kê
quantity_counted|Số lượng kiểm kê thực tế
verified_by_role|Vai trò người xác nhận
prepared_ingredient_id|Mã topping đã chế biến
prepared_qty|Lượng đã chuẩn bị
wasted_qty|Lượng đã hủy
carry_in_qty|Tồn đầu ngày còn dùng được
carry_out_qty|Tồn cuối ngày còn dùng được
reason|Lý do hủy'''.splitlines())
GIA_TRI = {
    'is_active': {'true': 'Có', 'false': 'Không'},
    'is_optional': {'true': 'Có', 'false': 'Không'},
    'verification_status': {'pending': 'Chờ xác nhận', 'verified': 'Đã xác nhận', 'rejected': 'Từ chối'},
    'ingredient_group': {'dry': 'Nguyên liệu khô', 'syrup': 'Si rô', 'prepared_topping': 'Topping đã chế biến', 'packaging': 'Bao bì'},
    'verified_by_role': {'manager': 'Quản lý', 'owner': 'Chủ cửa hàng', 'staff': 'Nhân viên'},
    'unit': {'g': 'g', 'ml': 'ml', 'pcs': 'cái'},
    'base_unit': {'g': 'g', 'ml': 'ml', 'pcs': 'cái'},
}


def chuan_hoa(cot, value):
    reverse = {v.casefold(): k for k, v in GIA_TRI.get(cot, {}).items()}
    return reverse.get(value.casefold(), value)


def tao_mau(root):
    import csv
    for table, name in TEP.items():
        source = root / 'data/public_examples' / (table + '.csv')
        with source.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames
            rows = list(reader)
        for folder, values in [('DU_LIEU_CAN_NHAP', []), ('MAU_MINH_HOA', rows)]:
            dest = root / folder / (name + '.csv')
            dest.parent.mkdir(exist_ok=True)
            if dest.exists():
                continue
            with dest.open('w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([COT[c] for c in columns])
                for row in values:
                    writer.writerow([GIA_TRI.get(c, {}).get(row[c], row[c]) for c in columns])
