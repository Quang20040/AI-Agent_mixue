"""Kiểm tra sơ bộ mẫu CSV tiếng Việt hoặc tiếng Anh; chưa duyệt hoặc ghi vào cơ sở dữ liệu."""
import argparse
import csv
import json
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tieng_viet import TEP, COT, chuan_hoa

ROOT = Path(__file__).resolve().parents[1]
KEYS = {
    'menu_items': ['sku_id', 'effective_from'],
    'ingredients': ['ingredient_id'],
    'recipe_bom': ['recipe_id', 'ingredient_id'],
    'sales_daily': ['store_id', 'business_date', 'sku_id'],
    'purchases': ['purchase_id', 'ingredient_id'],
    'stock_counts': ['count_id', 'ingredient_id'],
    'topping_daily': ['store_id', 'business_date', 'prepared_ingredient_id'],
}
OPTIONAL = {'variant', 'selling_price_vnd', 'effective_to', 'unit_cost_vnd',
            'shelf_life_rule_id', 'revenue_vnd', 'order_date', 'received_date',
            'carry_in_qty', 'carry_out_qty', 'reason'}
NUMBERS = {'selling_price_vnd', 'unit_cost_vnd', 'revenue_vnd', 'quantity_sold',
           'quantity_per_item', 'quantity_received', 'quantity_counted',
           'prepared_qty', 'wasted_qty', 'carry_in_qty', 'carry_out_qty'}


def validate(folder, start=None, end=None):
    issues, tables = [], {}
    def issue(table, row, message, severity='error'):
        issues.append(dict(dataset=table, row=row, severity=severity, message=message))
    for table, keys in KEYS.items():
        path = folder / (table + '.csv')
        vietnamese_path = folder / (TEP[table] + '.csv')
        if vietnamese_path.exists():
            path = vietnamese_path
        tables[table] = []
        if not path.exists():
            issue(table, 0, 'Chưa có file dữ liệu')
            continue
        with (ROOT / 'data/templates' / (table + '.csv')).open(encoding='utf-8-sig') as f:
            required = next(csv.reader(f))
        with path.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            translated = {v: k for k, v in COT.items()}
            reader.fieldnames = [translated.get(c, c) for c in (reader.fieldnames or [])]
            if len(set(reader.fieldnames)) != len(reader.fieldnames):
                issue(table, 1, 'Tên cột bị trùng')
                continue
            if not set(required).issubset(reader.fieldnames or []):
                issue(table, 1, 'Thiếu cột bắt buộc; dùng đúng mẫu đã cung cấp')
                continue
            seen = set()
            for i, raw in enumerate(reader, 2):
                if None in raw or any(v is None for v in raw.values()):
                    issue(table, i, 'Số ô không khớp số cột; kiểm tra dấu phẩy và cách lưu CSV')
                    continue
                row = {k: chuan_hoa(k, v.strip()) for k, v in raw.items()}
                tables[table].append(row)
                key = tuple(row[k] for k in keys)
                if key in seen:
                    issue(table, i, 'Bản ghi bị trùng mã/ngày; cần đối chiếu trước khi nhập')
                seen.add(key)
                for field in required:
                    value = row[field]
                    if not value:
                        if field not in OPTIONAL:
                            issue(table, i, f'{COT.get(field, field)}: bắt buộc điền')
                        continue
                    try:
                        if field in NUMBERS:
                            number = Decimal(value)
                            if not number.is_finite() or number < 0:
                                raise ValueError()
                            if field in {'quantity_sold', 'revenue_vnd', 'selling_price_vnd'} and number != number.to_integral_value():
                                raise ValueError()
                        if field.endswith('_date') or field in {'effective_from', 'effective_to'}:
                            date.fromisoformat(value)
                        if field == 'counted_at':
                            if datetime.fromisoformat(value).utcoffset() is None:
                                raise ValueError()
                        if field in {'is_active', 'is_optional'} and value not in {'true', 'false'}:
                            raise ValueError()
                        if field in {'unit', 'base_unit'} and value not in {'g', 'ml', 'pcs'}:
                            raise ValueError()
                        if field == 'verification_status' and value not in {'pending', 'verified', 'rejected'}:
                            raise ValueError()
                    except (ValueError, InvalidOperation):
                        issue(table, i, f'{COT.get(field, field)}: giá trị không hợp lệ (kiểm tra số âm, ngày hoặc lựa chọn)')
                if row.get('effective_to') and row['effective_to'] < row['effective_from']:
                    issue(table, i, 'Ngày hết hiệu lực sớm hơn ngày bắt đầu')
                if table == 'sales_daily' and row['verification_status'] != 'verified':
                    issue(table, i, 'Số bán chưa được người quản lý xác nhận', 'warning')
                if table == 'purchases' and not row['received_date']:
                    issue(table, i, 'Chưa có ngày thực nhận: chưa được cộng vào tồn kho', 'warning')
        if not tables[table]:
            issue(table, 0, 'Chưa nhập dòng dữ liệu nào; cần bổ sung')
    skus = {r['sku_id'] for r in tables['menu_items']}
    ingredients = {r['ingredient_id']: r for r in tables['ingredients']}
    for table, rows in tables.items():
        for i, row in enumerate(rows, 2):
            if 'sku_id' in row and row['sku_id'] not in skus:
                issue(table, i, 'Mã món chưa có trong danh mục món')
            field = 'prepared_ingredient_id' if table == 'topping_daily' else 'ingredient_id'
            if field not in row or table == 'ingredients':
                continue
            ing = ingredients.get(row[field])
            if not ing:
                issue(table, i, 'Mã nguyên liệu chưa có trong danh mục nguyên liệu')
            elif row.get('unit') != ing['base_unit']:
                issue(table, i, 'Đơn vị không khớp đơn vị cơ sở của nguyên liệu')
            if table == 'topping_daily':
                if ing and ing['ingredient_group'] != 'prepared_topping':
                    issue(table, i, 'Topping phải dùng mã nguyên liệu đã chế biến')
                if not row['carry_in_qty']:
                    issue(table, i, 'Chưa biết tồn đầu ngày; cần đối chiếu phạm vi lượng hủy', 'warning')
                else:
                    try:
                        if Decimal(row['wasted_qty']) > Decimal(row['prepared_qty']) + Decimal(row['carry_in_qty']):
                            issue(table, i, 'Lượng hủy vượt lượng chuẩn bị cộng tồn đầu ngày; cần đối chiếu')
                    except (InvalidOperation, ValueError):
                        pass
    missing = []
    if start and end:
        observed = {(r['store_id'], r['business_date'], r['sku_id']) for r in tables['sales_daily']}
        stores = {r['store_id'] for r in tables['sales_daily']}
        day = start
        while day <= end:
            for store in stores:
                for sku in skus:
                    active = any(r['sku_id'] == sku and r['effective_from'] <= day.isoformat()
                                 and (not r['effective_to'] or r['effective_to'] >= day.isoformat())
                                 for r in tables['menu_items'])
                    if active and (store, day.isoformat(), sku) not in observed:
                        missing.append([store, day.isoformat(), sku])
            day += timedelta(days=1)
        if missing:
            issue('sales_daily', 0, f'Thiếu {len(missing)} cặp món/ngày; không tự điền số 0', 'warning')
    return {'status': 'ERROR' if any(x['severity'] == 'error' for x in issues) else 'REQUIRES_HUMAN_REVIEW',
            'scope': 'Chỉ kiểm tra CSV sơ bộ; chưa xác nhận đủ điều kiện dự báo hoặc tối ưu.',
            'row_counts': {k: len(v) for k, v in tables.items()},
            'issues': issues, 'missing_sales_pairs': missing}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--start', type=date.fromisoformat)
    parser.add_argument('--end', type=date.fromisoformat)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if bool(args.start) != bool(args.end) or (args.start and args.start > args.end):
        parser.error('Cần điền cả ngày bắt đầu và kết thúc; ngày bắt đầu không được sau ngày kết thúc')
    result = validate(args.folder, args.start, args.end)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Kết quả: ' + ('CÓ LỖI CẦN SỬA' if result['status'] == 'ERROR' else 'CẦN NGƯỜI QUẢN LÝ ĐỐI CHIẾU VÀ XÁC NHẬN'))
    for table, count in result['row_counts'].items():
        print(f'  {TEP[table]}: {count} dòng dữ liệu')
    for item in result['issues']:
        level = 'LỖI' if item['severity'] == 'error' else 'LƯU Ý'
        print(f"{level} - {TEP[item['dataset']]} - dòng {item['row']}: {item['message']}")
    return 1 if result['status'] == 'ERROR' else 0


if __name__ == '__main__':
    raise SystemExit(main())
