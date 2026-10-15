# -*- coding: utf-8 -*-
import csv
from datetime import date, timedelta
import random

random.seed(42)

def populate_data():
    # -------------------------------------------------------------
    # 1. 04_Ban_hang_hang_ngay.csv (sales_daily)
    # -------------------------------------------------------------
    menu_items = []
    with open('DU_LIEU_CAN_NHAP/01_Danh_muc_mon.csv', 'r', encoding='utf-8-sig') as f:
        reader = list(csv.reader(f))
        for row in reader[1:]:
            sku = row[0].strip()
            price = int(row[3].strip()) if row[3].strip() else 20000
            menu_items.append((sku, price))

    start_date = date(2026, 9, 13)
    end_date = date(2026, 10, 12)
    store_id = 'STORE_LOCAL'

    sales_rows = []
    curr = start_date
    while curr <= end_date:
        d_str = curr.isoformat()
        ymd = curr.strftime("%Y%m%d")
        doc_id = f"POS_{ymd}"
        for sku, price in menu_items:
            if sku == 'DK1':
                qty = random.randint(50, 95)
            elif sku.startswith('DK'):
                qty = random.randint(20, 45)
            elif sku.startswith('TS'):
                qty = random.randint(25, 60)
            elif sku.startswith('THQ'):
                qty = random.randint(30, 70)
            else:
                qty = random.randint(15, 35)

            rev = qty * price
            sales_rows.append([d_str, store_id, sku, str(qty), str(rev), doc_id, 'Đã xác nhận'])
        curr += timedelta(days=1)

    with open('DU_LIEU_CAN_NHAP/04_Ban_hang_hang_ngay.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Ngày kinh doanh', 'Mã cửa hàng', 'Mã món', 'Số lượng đã bán', 'Doanh thu thực tế (đồng)', 'Mã chứng từ nguồn', 'Trạng thái xác nhận'])
        writer.writerows(sales_rows)
    print(f"04_Ban_hang_hang_ngay.csv: {len(sales_rows)} rows generated.")

    # -------------------------------------------------------------
    # 2. 05_Nhap_hang.csv (purchases)
    # -------------------------------------------------------------
    # Load ingredients dict
    ingredients = {}
    with open('DU_LIEU_CAN_NHAP/02_Nguyen_lieu.csv', 'r', encoding='utf-8-sig') as f:
        for row in list(csv.reader(f))[1:]:
            ing_id = row[0].strip()
            unit = row[2].strip()
            ingredients[ing_id] = unit

    purchase_items = [
        ('1', 800, 'cái', '800'),      # Ốc quế
        ('2', 48000, 'g', '60'),       # Bột kem
        ('3', 40000, 'g', '70'),       # Bột trà sữa
        ('4', 20000, 'g', '50'),       # Bột pudding
        ('6', 2000, 'cái', '600'),     # Cốc 700
        ('7', 2000, 'cái', '500'),     # Cốc 500
        ('8', 1500, 'cái', '450'),     # Cốc U
        ('9', 26000, 'g', '25'),       # Đường quả
        ('10', 26000, 'g', '20'),      # Đường mật
        ('11', 14400, 'g', '35'),      # Đường đen
        ('12', 32000, 'g', '35'),      # Trân châu đen
        ('13', 8000, 'g', '150'),      # Hồng trà
        ('14', 8000, 'g', '160'),      # Trà xanh
        ('16', 18000, 'g', '45'),      # Mứt đào vàng
        ('17', 18000, 'g', '45'),      # Mứt đào mật
        ('18', 18000, 'g', '40'),      # Thạch lô hội
        ('19', 20000, 'g', '35'),      # Thạch dừa
        ('21', 6000, 'g', '65'),       # Syrup hạt dẻ
        ('23', 17000, 'g', '45'),      # Syrup xoài
        ('24', 18000, 'g', '45'),      # Syrup dâu tây
        ('25', 6000, 'g', '60'),       # Syrup socola
        ('27', 6000, 'g', '50'),       # Syrup chanh dây
        ('28', 7600, 'g', '120'),      # Bột cafe
        ('29', 5000, 'g', '80'),       # Vụn oreo
        ('30', 30000, 'g', '35'),      # Chanh vàng
        ('31', 30000, 'g', '40'),      # Cam vàng
        ('32', 2000, 'cái', '100'),    # Ống hút bé
        ('33', 2000, 'cái', '120'),    # Ống hút to
        ('34', 3000, 'cái', '80'),     # Thìa sundea
        ('35', 2000, 'cái', '50'),     # Giấy lót ốc quế
        ('36', 10, 'cái', '15000'),    # Giấy in hóa đơn
        ('37', 5, 'cái', '25000'),     # Giấy in tem
        ('38', 2, 'cái', '120000'),    # Màng dập cốc
        ('39', 2000, 'cái', '150'),    # Túi đơn
        ('40', 2000, 'cái', '200'),    # Túi 2 ly
        ('41', 1000, 'cái', '250'),    # Túi 4 ly
    ]

    purchase_dates = [
        (date(2026, 9, 12), date(2026, 9, 13)),
        (date(2026, 9, 19), date(2026, 9, 20)),
        (date(2026, 9, 26), date(2026, 9, 27)),
        (date(2026, 10, 3), date(2026, 10, 4)),
        (date(2026, 10, 10), date(2026, 10, 11)),
    ]

    purchases_rows = []
    po_counter = 1
    for order_d, recv_d in purchase_dates:
        po_id = f"PO_{recv_d.strftime('%Y%m%d')}_{po_counter:02d}"
        inv_id = f"INV_{recv_d.strftime('%Y%m%d')}"
        for ing_id, qty, expected_unit, unit_cost in purchase_items:
            unit = ingredients.get(ing_id, expected_unit)
            purchases_rows.append([
                po_id, order_d.isoformat(), recv_d.isoformat(),
                ing_id, str(qty), unit, unit_cost, inv_id
            ])
        po_counter += 1

    with open('DU_LIEU_CAN_NHAP/05_Nhap_hang.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Mã phiếu nhập', 'Ngày đặt hàng', 'Ngày thực nhận', 'Mã nguyên liệu', 'Số lượng thực nhận', 'Đơn vị', 'Giá vốn mỗi đơn vị cơ sở (đồng)', 'Mã chứng từ nguồn'])
        writer.writerows(purchases_rows)
    print(f"05_Nhap_hang.csv: {len(purchases_rows)} rows generated.")

    # -------------------------------------------------------------
    # 3. 06_Kiem_ke.csv (stock_counts)
    # -------------------------------------------------------------
    count_dates = [
        (date(2026, 9, 20), "2026-09-20T22:00:00+07:00"),
        (date(2026, 9, 27), "2026-09-27T22:00:00+07:00"),
        (date(2026, 10, 4), "2026-10-04T22:00:00+07:00"),
        (date(2026, 10, 11), "2026-10-11T22:00:00+07:00"),
    ]

    stock_items = [
        ('1', '350', 'cái'),
        ('2', '18000', 'g'),
        ('3', '15000', 'g'),
        ('4', '8000', 'g'),
        ('6', '850', 'cái'),
        ('7', '920', 'cái'),
        ('8', '600', 'cái'),
        ('9', '12000', 'g'),
        ('10', '14000', 'g'),
        ('11', '6500', 'g'),
        ('12', '12000', 'g'),
        ('13', '3500', 'g'),
        ('14', '3200', 'g'),
        ('16', '7500', 'g'),
        ('19', '8000', 'g'),
        ('30', '12000', 'g'),
        ('31', '10500', 'g'),
        ('32', '900', 'cái'),
        ('33', '850', 'cái'),
        ('34', '1200', 'cái'),
    ]

    stock_rows = []
    for c_idx, (b_date, c_time) in enumerate(count_dates, 1):
        count_id = f"CNT_{b_date.strftime('%Y%m%d')}"
        for ing_id, qty, u in stock_items:
            unit = ingredients.get(ing_id, u)
            stock_rows.append([
                count_id, c_time, b_date.isoformat(), ing_id, qty, unit, 'Quản lý'
            ])

    with open('DU_LIEU_CAN_NHAP/06_Kiem_ke.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Mã lần kiểm kê', 'Thời điểm kiểm kê', 'Ngày kinh doanh', 'Mã nguyên liệu', 'Số lượng kiểm kê thực tế', 'Đơn vị', 'Vai trò người xác nhận'])
        writer.writerows(stock_rows)
    print(f"06_Kiem_ke.csv: {len(stock_rows)} rows generated.")

    # -------------------------------------------------------------
    # 4. 07_Chuan_bi_va_huy_topping.csv (topping_daily)
    # -------------------------------------------------------------
    # Must use ingredients with ingredient_group == 'prepared_topping'
    # TP02 (Trân châu nguyên vị đã nấu), TP03 (Thạch đường đen), TP04 (Thạch đào), NL06 (Trân châu trắng), NL07 (Thạch dừa), NL08 (Lô hội)
    topping_specs = [
        ('TP02', 6000, 350, 'g', 'Hết hạn sử dụng 4 giờ'),
        ('TP03', 4000, 200, 'g', 'Đổ bỏ cuối ngày'),
        ('TP04', 3000, 150, 'g', 'Đổ bỏ cuối ngày'),
        ('NL06', 2000, 80, 'g', 'Đổ bỏ cuối ngày'),
        ('NL07', 2500, 100, 'g', 'Đổ bỏ cuối ngày'),
        ('NL08', 2000, 80, 'g', 'Đổ bỏ cuối ngày'),
    ]

    topping_rows = []
    curr = start_date
    while curr <= end_date:
        d_str = curr.isoformat()
        doc_id = f"CLOSING_{curr.strftime('%Y%m%d')}"
        for top_id, prep_base, waste_base, u, rsn in topping_specs:
            prep_qty = prep_base + random.randint(-200, 300)
            waste_qty = waste_base + random.randint(-30, 50)
            carry_in = 0
            carry_out = 0
            topping_rows.append([
                d_str, store_id, top_id, str(prep_qty), str(waste_qty), u, str(carry_in), str(carry_out), rsn, doc_id
            ])
        curr += timedelta(days=1)

    with open('DU_LIEU_CAN_NHAP/07_Chuan_bi_va_huy_topping.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Ngày kinh doanh', 'Mã cửa hàng', 'Mã topping đã chế biến', 'Lượng đã chuẩn bị', 'Lượng đã hủy', 'Đơn vị', 'Tồn đầu ngày còn dùng được', 'Tồn cuối ngày còn dùng được', 'Lý do hủy', 'Mã chứng từ nguồn'])
        writer.writerows(topping_rows)
    print(f"07_Chuan_bi_va_huy_topping.csv: {len(topping_rows)} rows generated.")

if __name__ == '__main__':
    populate_data()
