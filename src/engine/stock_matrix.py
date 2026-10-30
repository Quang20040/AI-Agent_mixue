"""Calendar-based stock ledger, using two batched reads regardless of row count."""

import calendar
from datetime import date, timedelta

import pandas as pd

from src.models import DailyStockMovement, Ingredient


def day_label(day):
    return f"{'CN' if day.weekday() == 6 else 'T' + str(day.weekday() + 2)} {day.day}/{day.month}"


def column_map_for_period(year, month):
    days = [date(year, month, n) for n in range(1, calendar.monthrange(year, month)[1] + 1)]
    result = {}
    for day in days:
        result[f"Nhập {day.day}/{month}"] = (day.isoformat(), "IN")
        result[day_label(day)] = (day.isoformat(), "OUT")
    result["Tồn thực tế"] = (days[-1].isoformat(), "ACTUAL_COUNT")
    return result


def matrix_views(year, month):
    previous = date(year, month, 1) - timedelta(days=1)
    opening = "Tồn T9" if month == 10 else f"Tồn cuối {previous.month}/{previous.year}"
    base = ["STT", "Tên mặt hàng (Quy cách)"]
    weeks = calendar.monthcalendar(year, month)
    result = {f"Toàn bộ tháng {month}/{year}": None}
    for index, week in enumerate(weeks, 1):
        days = [date(year, month, day) for day in week if day]
        label = f"Tuần {index} ({days[0]:%d/%m} - {days[-1]:%d/%m})"
        columns = [opening if index == 1 else f"Tồn T{index - 1}"]
        for day in days:
            columns.extend([f"Nhập {day.day}/{month}", day_label(day)])
        result[label] = [*base, *columns, f"Tồn T{index}"]
    result["Tổng hợp cuối kỳ"] = [*base, opening, "Tổng nhập", "Tổng xuất", "Tồn sổ sách", "Tồn thực tế", "Ngày kiểm kê", "Chênh lệch"]
    return result


def build_stock_matrix(db, year, month):
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    previous = first - timedelta(days=1)
    catalog = db.query(Ingredient).order_by(Ingredient.ingredient_id).all()
    movements = (
        db.query(DailyStockMovement)
        .filter(DailyStockMovement.status == "APPROVED", DailyStockMovement.business_date <= last)
        .order_by(DailyStockMovement.business_date, DailyStockMovement.id)
        .all()
    )
    grouped = {}
    for movement in movements:
        grouped.setdefault(movement.ingredient_id, []).append(movement)
    rows = []
    for index, ingredient in enumerate(catalog, 1):
        items = grouped.get(ingredient.ingredient_id, [])
        initial = next((m for m in reversed(items) if m.movement_type == "INITIAL" and m.business_date <= first), None)

        def after_initial(m):
            return initial is None or (m.business_date, m.id) > (initial.business_date, initial.id)

        opening = float(initial.quantity) if initial else 0.0
        for movement in items:
            if movement.business_date < first and after_initial(movement):
                if movement.movement_type == "IN":
                    opening += float(movement.quantity)
                elif movement.movement_type == "OUT":
                    opening -= float(movement.quantity)
        period = [m for m in items if first <= m.business_date <= last and after_initial(m)]
        ins, outs = {}, {}
        for movement in period:
            bucket = ins if movement.movement_type == "IN" else outs if movement.movement_type == "OUT" else None
            if bucket is not None:
                bucket[movement.business_date] = bucket.get(movement.business_date, 0.0) + float(movement.quantity)
        opening_label = "Tồn T9" if month == 10 else f"Tồn cuối {previous.month}/{previous.year}"
        row = {
            "STT": index,
            "Mã NL": ingredient.ingredient_id,
            "Tên mặt hàng (Quy cách)": ingredient.ingredient_name,
            opening_label: opening if initial else "—",
        }
        balance = opening
        week = 1
        for number in range(1, last.day + 1):
            day = date(year, month, number)
            incoming, outgoing = ins.get(day, 0.0), outs.get(day, 0.0)
            row[f"Nhập {number}/{month}"] = incoming or ""
            row[day_label(day)] = outgoing or ""
            balance += incoming - outgoing
            if day.weekday() == 6 or day == last:
                row[f"Tồn T{week}"] = balance if initial else "—"
                week += 1
        actual = next((m for m in reversed(period) if m.movement_type == "ACTUAL_COUNT"), None)
        expected_at_count = (
            opening
            + sum(q for d, q in ins.items() if actual and d <= actual.business_date)
            - sum(q for d, q in outs.items() if actual and d <= actual.business_date)
        )
        row.update(
            {
                "Tổng nhập": sum(ins.values()),
                "Tổng xuất": sum(outs.values()),
                "Tồn sổ sách": balance if initial else "—",
                "Tồn thực tế": float(actual.quantity) if actual else "—",
                "Ngày kiểm kê": actual.business_date.isoformat() if actual else "—",
                "Chênh lệch": float(actual.quantity) - expected_at_count if actual and initial else "—",
            }
        )
        rows.append(row)
    if not rows:
        return pd.DataFrame(
            columns=[
                "STT",
                "Mã NL",
                "Tên mặt hàng (Quy cách)",
                "Tồn T9" if month == 10 else f"Tồn cuối {previous.month}/{previous.year}",
                *column_map_for_period(year, month),
                "Tổng nhập",
                "Tổng xuất",
                "Tồn sổ sách",
                "Ngày kiểm kê",
                "Chênh lệch",
            ]
        )
    return pd.DataFrame(rows)
