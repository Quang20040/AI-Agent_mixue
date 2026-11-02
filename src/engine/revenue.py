"""One revenue figure per day, from what the shop actually recorded.

Two sources can describe the same day:
* approved shift closings (photos read by OCR, checked by staff, approved by a manager) — money collected;
* the POS item export (`sales_daily`) — revenue and cups per menu item.

They are never added together. The day's recorded revenue is the approved shift total when there is one
(it is what was handed over), otherwise the POS item revenue; both are shown side by side with the source,
and the gap between them is the reconciliation figure. Nothing is cached here, so an approval, edit or
deletion shows up on the next page run.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import func

from src.database import SessionLocal
from src.engine.shift_service import get_all_shift_reports, get_daily_closing_summary
from src.models import SalesDaily
from src.runtime_settings import resolve_store_id

SHIFTS = ('CA_SANG', 'CA_CHIEU', 'CA_TOI')
COLUMNS = ['business_date', 'shift_count', 'shift_collected_vnd', 'cash_vnd', 'bank_vnd', 'apps_vnd', 'expenses_vnd',
           'slip_pos_revenue_vnd', 'pos_sku_revenue_vnd', 'quantity_sold', 'effective_revenue_vnd', 'variance_vnd', 'source']


def _pos_by_day(start: date, end: date) -> dict[date, tuple[float, int]]:
    with SessionLocal() as db:
        store_id = resolve_store_id(db)
        rows = (db.query(SalesDaily.business_date, func.sum(SalesDaily.revenue_vnd), func.sum(SalesDaily.quantity_sold))
                .filter(SalesDaily.store_id == store_id, SalesDaily.business_date >= start, SalesDaily.business_date <= end)
                .group_by(SalesDaily.business_date).all())
    return {day: (float(revenue or 0), int(cups or 0)) for day, revenue, cups in rows}


def _shift_days(start: date, end: date) -> set[date]:
    days = set()
    for report in get_all_shift_reports():
        try:
            day = date.fromisoformat(str(report.get('business_date'))[:10])
        except ValueError:
            continue
        if start <= day <= end and report.get('status', 'APPROVED') == 'APPROVED':
            days.add(day)
    return days


def day_revenue(day: date, pos: tuple[float, int] | None = None) -> dict[str, Any]:
    summary = get_daily_closing_summary(day.isoformat())
    if pos is None:
        pos = _pos_by_day(day, day).get(day, (0.0, 0))
    pos_revenue, cups = pos
    shift_total = float(summary['total_collected_vnd'] or 0) if summary['shift_count'] else 0.0
    slip_pos = float(summary['pos_revenue_vnd'] or 0) if summary.get('has_evening') else 0.0
    if summary['shift_count'] and pos_revenue:
        source, effective = 'Đã đối soát cả Chốt ca & POS', shift_total
    elif summary['shift_count']:
        source, effective = 'Chốt ca OCR đã duyệt', shift_total
    elif pos_revenue:
        source, effective = 'Máy POS', pos_revenue
    else:
        source, effective = 'Chưa có dữ liệu', 0.0
    reference = slip_pos or pos_revenue
    return {
        'business_date': day,
        'shift_count': summary['shift_count'],
        'shift_collected_vnd': shift_total,
        'cash_vnd': summary['total_cash_vnd'] if summary['shift_count'] else 0.0,
        'bank_vnd': summary['total_bank_vnd'] if summary['shift_count'] else 0.0,
        'apps_vnd': summary['total_delivery_apps_vnd'] if summary['shift_count'] else 0.0,
        'expenses_vnd': summary['total_expenses_vnd'] if summary['shift_count'] else 0.0,
        'slip_pos_revenue_vnd': slip_pos,
        'pos_sku_revenue_vnd': pos_revenue,
        'quantity_sold': cups,
        'effective_revenue_vnd': effective,
        'variance_vnd': (shift_total - reference) if summary['shift_count'] and reference else 0.0,
        'source': source,
        'shifts': {code: next((s for s in summary['shifts'] if s.get('shift_code') == code), None) for code in SHIFTS},
    }


def daily_revenue(start: date, end: date, *, include_empty: bool = False) -> pd.DataFrame:
    """One row per day in [start, end] that has approved shifts or POS sales (every day if include_empty)."""
    pos = _pos_by_day(start, end)
    days = sorted(set(pos) | _shift_days(start, end))
    if include_empty:
        days = [start + timedelta(days=n) for n in range((end - start).days + 1)]
    rows = [{k: v for k, v in day_revenue(day, pos.get(day, (0.0, 0))).items() if k != 'shifts'} for day in days]
    return pd.DataFrame(rows, columns=COLUMNS)
