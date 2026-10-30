"""Calendar-day sales views: missing records are not zero or the latest old day."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd


def business_today():
    return datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date()


def daily_window(sales, *, today=None, days=7):
    today = today or business_today()
    dates = [today - timedelta(days=n) for n in reversed(range(days))]
    frame = sales.copy()
    if not frame.empty:
        frame['business_date'] = pd.to_datetime(frame['business_date']).dt.date
        daily = frame.groupby('business_date').agg(revenue=('revenue_vnd', 'sum'), cups=('quantity_sold', 'sum'))
    else:
        daily = pd.DataFrame(columns=['revenue', 'cups'])
    result = daily.reindex(dates)
    result['available'] = result['revenue'].notna() & result['cups'].notna()
    return result
