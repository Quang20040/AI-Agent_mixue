"""Forecast and prep plans must use approved shift closings for days the POS item export does not cover yet."""
from datetime import date, timedelta

import pandas as pd

from src.engine.forecasting import ForecastingEngine


def _engine_with_history():
    engine = ForecastingEngine.__new__(ForecastingEngine)
    days = [date(2026, 10, 1) + timedelta(days=n) for n in range(15)]
    engine.df = pd.DataFrame({'business_date': days, 'quantity_sold': [100] * 15, 'revenue_vnd': [2_000_000] * 15})
    return engine


def _frame(target):
    return pd.DataFrame({'target_date': [target, target], 'predicted_qty': [60.0, 40.0], 'lower_bound': [50.0, 30.0],
                         'upper_bound': [70.0, 50.0], 'baseline_qty': [60.0, 40.0], 'model_used': ['m', 'm'],
                         'confidence': ['MEDIUM', 'MEDIUM']})


def test_approved_shift_revenue_counts_as_latest_data(monkeypatch):
    engine = _engine_with_history()
    latest, cutoff, target = date(2026, 10, 15), date(2026, 11, 2), date(2026, 11, 3)
    shifts = pd.DataFrame({'business_date': [date(2026, 11, 1), cutoff], 'shift_count': [3, 3],
                           'shift_collected_vnd': [2_400_000.0, 2_400_000.0]})
    monkeypatch.setattr('src.engine.revenue.daily_revenue', lambda start, end: shifts)
    frame, metadata = _frame(target), {'warnings': [], 'notes': [], 'source_refs': ['table:sales_daily']}
    engine._use_shift_revenue(frame, target, latest, cutoff, engine.df, metadata)

    assert not any('ngày gần nhất' in w for w in metadata['warnings'])
    assert '01/11/2026, 02/11/2026' in metadata['notes'][0]
    # 2.4M at 20k/cup = 120 cups vs 100/day in the POS weeks -> x1.2
    assert metadata['shift_revenue_adjustment']['factor'] == 1.2
    assert frame['predicted_qty'].sum() == 120
    assert metadata['previous_sales'] == {'date': '2026-11-02', 'cups': 120, 'cups_estimated': True,
                                          'source': 'Chốt ca đã duyệt', 'revenue': 2_400_000.0}


def test_missing_day_without_shift_says_what_is_missing(monkeypatch):
    engine = _engine_with_history()
    monkeypatch.setattr('src.engine.revenue.daily_revenue', lambda start, end: pd.DataFrame(
        columns=['business_date', 'shift_count', 'shift_collected_vnd']))
    frame, metadata = _frame(date(2026, 11, 3)), {'warnings': [], 'notes': [], 'source_refs': []}
    engine._use_shift_revenue(frame, date(2026, 11, 3), date(2026, 10, 15), date(2026, 11, 2), engine.df, metadata)
    assert metadata['warnings'] == ['Chưa có doanh thu ngày 02/11/2026 (chưa có chốt ca được duyệt hay dữ liệu máy POS); '
                                    'dữ liệu bán gần nhất là ngày 15/10/2026.']
    assert frame['predicted_qty'].sum() == 100


def test_previous_sales_text_handles_revenue_only_days():
    from src.engine.weather_advice import previous_sales_text
    assert previous_sales_text({'date': '2026-11-02', 'cups': None, 'revenue': 2_400_000, 'source': 'Chốt ca đã duyệt'}) == \
        'Ngày 02/11/2026: doanh thu 2,400,000 đ (Chốt ca đã duyệt).'
    assert 'khoảng 120 ly' in previous_sales_text({'date': '2026-11-02', 'cups': 120, 'cups_estimated': True,
                                                     'revenue': 2_400_000})
