from datetime import date

import pandas as pd

from src.dashboard.sales_view import daily_window


def sales(rows):
    return pd.DataFrame(rows, columns=['business_date', 'revenue_vnd', 'quantity_sold'])


def test_stale_sales_are_not_todays_results():
    window = daily_window(sales([(date(2026, 10, 15), 36455000, 1574)]), today=date(2026, 10, 22))
    assert list(window.index)[0] == date(2026, 10, 16)
    assert list(window.index)[-1] == date(2026, 10, 22)
    assert not window['available'].any()


def test_missing_days_differ_from_recorded_zero_and_future_is_excluded():
    window = daily_window(sales([(date(2026, 10, 22), 0, 0), (date(2026, 10, 23), 9999, 99)]), today=date(2026, 10, 22))
    assert window.iloc[-1]['available']
    assert window.iloc[-1].revenue == 0
    assert not window.iloc[-2]['available']
    assert window['available'].sum() == 1


def test_calendar_yesterday_is_not_last_available_day():
    window = daily_window(sales([(date(2026, 10, 20), 100, 1), (date(2026, 10, 22), 200, 2)]), today=date(2026, 10, 22), days=2)
    assert not window.iloc[0]['available']
    assert window.iloc[-1].revenue == 200


def test_empty_database_still_has_seven_explicit_missing_days():
    window = daily_window(sales([]), today=date(2026, 10, 22))
    assert len(window) == 7
    assert not window['available'].any()
