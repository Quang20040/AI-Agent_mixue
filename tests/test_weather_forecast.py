from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.engine.contextual_forecast import contextual_adjustment
from src.engine.weather import WeatherClient, WeatherSettings, WeatherUnavailable


def weather(rain=0, temperature=30):
    return {'temperature_c': temperature, 'rain_mm': rain, 'peak_rain_mm': rain}


@pytest.fixture
def history():
    rng = np.random.default_rng(42)
    first = date(2026, 5, 1)
    rows, reference, anticipated = [], {}, {}
    for i in range(100):
        day = first + timedelta(days=i)
        rain = 15 if rng.random() < .4 else 0
        temp = 30 + 4 * np.sin(i * .3)
        cups = 600 - 20 * rain + 8 * (temp - 30) + 30 * np.sin(day.weekday() * 2 * np.pi / 7)
        rows.append({'business_date': day, 'quantity_sold': cups, 'revenue_vnd': cups * 25000})
        reference[day] = weather(rain, temp)
        anticipated[day] = weather(rain, temp)
    return pd.DataFrame(rows), {'reference': reference, 'anticipated': anticipated}, first + timedelta(days=100)


@pytest.fixture
def pearl_catalog(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from src.database import Base
    from src.models import Ingredient
    monkeypatch.setenv('STORE_ID', '')
    monkeypatch.setenv('AGENT_CHECKPOINT_PATH', str(tmp_path / 'checkpoints.db'))
    monkeypatch.setenv('AGENT_CONVERSATION_PATH', str(tmp_path / 'conversations.db'))
    database = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(database)
    with Session(database) as db:
        db.add(Ingredient(ingredient_id='TP02', ingredient_name='Trân châu thử nghiệm',
                          ingredient_group='prepared_topping', base_unit='g'))
        db.commit()
        yield db
    database.dispose()


def test_learns_rain_effect_instead_of_fixed_percentage(history):
    sales, observations, target = history
    dry = contextual_adjustment(sales, target, observations, weather(0), 500, lambda _: 500)
    wet = contextual_adjustment(sales, target, observations, weather(15), 500, lambda _: 500)
    assert wet['status'] == dry['status'] == 'WEATHER_VALIDATED'
    assert wet['context_total_cups'] < dry['context_total_cups']
    assert wet['weather_scenario_delta_cups'] < 0
    assert wet['validation']['weather_WAPE_pct'] < wet['validation']['baseline_WAPE_pct']
    assert wet['previous_day']['revenue'] > 0


def test_future_sales_and_revenue_cannot_change_prediction(history):
    sales, observations, target = history
    before = contextual_adjustment(sales, target, observations, weather(15), 500, lambda _: 500)
    future = pd.concat([sales, pd.DataFrame([{'business_date': target, 'quantity_sold': 9999999, 'revenue_vnd': 999999999}])])
    after = contextual_adjustment(future, target, observations, weather(15), 500, lambda _: 500)
    assert after == before


def test_missing_yesterday_is_not_assumed_zero(history):
    sales, observations, target = history
    result = contextual_adjustment(sales.iloc[:-1], target, observations, weather(15), 500, lambda _: 500)
    assert result['status'] == 'MISSING_RECENT_SALES'
    assert result['factor'] == 1


def test_insufficient_history_retains_baseline(history):
    sales, observations, target = history
    result = contextual_adjustment(sales.iloc[-14:], target, observations, weather(15), 500, lambda _: 500)
    assert result['status'] == 'INSUFFICIENT_HISTORY'
    assert result['factor'] == 1


def test_rain_with_no_historical_effect_is_not_forced_down(history):
    sales, observations, target = history
    sales['quantity_sold'] = 500
    sales['revenue_vnd'] = 12500000
    result = contextual_adjustment(sales, target, observations, weather(15), 500, lambda _: 500)
    assert result['status'] == 'BASELINE_RETAINED'
    assert result['factor'] == 1


def test_provider_failure_is_explicit_not_sunny_default():
    class BadSession:
        def get(self, *args, **kwargs):
            import requests
            raise requests.Timeout()
    client = WeatherClient(WeatherSettings(enabled=True, cache_dir='output/qa-weather-no-cache'), BadSession())
    with pytest.raises(WeatherUnavailable, match='PROVIDER_UNAVAILABLE'):
        client.forecast(date(2026, 5, 1), date(2026, 5, 1))


def test_business_hours_only_and_peak_rain():
    client = WeatherClient(WeatherSettings())
    payload = {'hourly': {'time': [f'2026-05-01T{h:02d}:00' for h in range(24)],
                          'temperature_2m': [30] * 24, 'precipitation': [1] * 24}}
    result = client._aggregate(payload, '_previous_day0')[date(2026, 5, 1)]
    assert result['rain_mm'] == 14
    assert result['peak_rain_mm'] == 6
    payload['hourly']['precipitation'][10] = None
    assert client._aggregate(payload) == {}


def test_d1_variables_cannot_fall_back_to_actual_weather():
    client = WeatherClient()
    payload = {'hourly': {'time': ['2026-05-01T08:00'], 'temperature_2m': [30], 'precipitation': [0]}}
    with pytest.raises(WeatherUnavailable, match='MISSING_VARIABLES'):
        client._aggregate(payload, '_previous_day1')


def test_unknown_working_hours_rejected():
    with pytest.raises(ValueError):
        WeatherSettings(opening_hour=23, closing_hour=8)


def test_engine_does_not_use_future_sales_in_auto_selection_or_multi_day_forecast():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from src.database import Base
    from src.engine.forecasting import ForecastingEngine
    from src.models import MenuItem, SalesDaily
    database = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(database)
    with Session(database) as db:
        db.add(MenuItem(sku_id='TEST', sku_name='Test', selling_price_vnd=25000))
        first = date(2026, 1, 1)
        for i in range(45):
            day = first + timedelta(days=i)
            db.add(SalesDaily(store_id='STORE_LOCAL', sku_id='TEST', business_date=day,
                              quantity_sold=100 + i % 7, revenue_vnd=(100 + i % 7) * 25000))
            db.add(SalesDaily(store_id='OTHER_STORE', sku_id='TEST', business_date=day,
                              quantity_sold=99999, revenue_vnd=99999999))
        db.commit()
        forecaster = ForecastingEngine(db, weather_client=WeatherClient(WeatherSettings(enabled=False, store_id='STORE_LOCAL')))
        target = first + timedelta(days=35)
        before = forecaster.forecast_demand(target, horizon_days=2, model='auto')
        for row in db.query(SalesDaily).filter(SalesDaily.business_date >= target):
            row.quantity_sold = 9999999
            row.revenue_vnd = 999999999999
        db.commit()
        after = forecaster.forecast_demand(target, horizon_days=2, model='auto')
        pd.testing.assert_frame_equal(before, after)
        assert before.predicted_qty.max() < 200
    database.dispose()


def test_extreme_unseen_weather_does_not_get_an_unvalidated_multiplier(history):
    sales, observations, target = history
    result = contextual_adjustment(sales, target, observations, weather(500), 500, lambda _: 500)
    assert result['status'] == 'WEATHER_OUT_OF_RANGE'
    assert result['factor'] == 1


def test_pearl_yield_estimate_matches_catalog_and_recalculates_batches(pearl_catalog):
    from src.engine.optimizer import OptimizerEngine
    optimizer = OptimizerEngine(pearl_catalog)
    demand = pd.DataFrame([{'ingredient_id': 'TP02', 'theoretical_qty': 5500}])
    try:
        defaults = optimizer.optimize_topping_preparation(date(2026, 10, 16), demand)
        changed = optimizer.optimize_topping_preparation(date(2026, 10, 16), demand, batch_yield_map={'TP02': 3000})
        pearl = next(row for row in defaults if row['ingredient_id'] == 'TP02')
        other = next(row for row in changed if row['ingredient_id'] == 'TP02')
        assert pearl['unit'] == 'g'
        assert 'Trân châu' in pearl['ingredient_name']
        assert pearl['batch_size'] == 2000
        assert pearl['num_batches'] == 4
        assert pearl['estimated_raw_input_g'] == 4000
        assert pearl['batch_count_range'] == [3, 5]
        assert other['num_batches'] == 3
        assert other['batch_yield_is_estimate']
    finally:
        optimizer.close()


def test_validator_rejects_ml_for_a_gram_ingredient(pearl_catalog):
    from src.engine.validator import IndependentPlanValidator
    validator = IndependentPlanValidator(pearl_catalog)
    try:
        result = validator.verify_topping_prep_plan([{'ingredient_id': 'TP02', 'unit': 'ml',
            'recommended_prep_qty': 2000, 'batch_size': 2000}])
        assert not result['is_valid']
        assert any('không khớp' in violation for violation in result['violations'])
    finally:
        validator.close()


def test_relative_dates_follow_vietnam_calendar_not_demo_dates():
    from src.agent.mixue_agent import _parse_query_date_range
    today = date(2026, 10, 16)
    assert _parse_query_date_range('hôm qua', today) == ('2026-10-15', '2026-10-15')
    assert _parse_query_date_range('hôm nay', today) == ('2026-10-16', '2026-10-16')
    assert _parse_query_date_range('ngày mai', today) == ('2026-10-17', '2026-10-17')
    assert _parse_query_date_range('gần nhất', today, date(2026, 10, 14)) == ('2026-10-14', '2026-10-14')


def test_first_preparation_window_uses_unrounded_demand(monkeypatch, pearl_catalog):
    from src.agent.mixue_agent import MixueOperationsAgent
    service = MixueOperationsAgent(pearl_catalog)
    monkeypatch.setattr('src.agent.mixue_agent.save_plan', lambda plan: None)
    monkeypatch.setattr(service.forecast_engine, 'forecast_demand', lambda *args, **kwargs: pd.DataFrame({'sku_id': ['TEST'], 'predicted_qty': [100]}))
    monkeypatch.setattr(service.optimizer_engine, 'calculate_ingredient_demand', lambda frame: pd.DataFrame([
        {'ingredient_id': 'TP02', 'theoretical_qty': 5500}]))
    try:
        plan = service.tool_optimize_topping_prep('2026-10-16')
        pearl = next(line for line in plan['recommendations'] if line['ingredient_id'] == 'TP02')
        assert pearl['num_batches'] == 4
        assert pearl['initial_batches'] == 1
        assert pearl['initial_raw_input_g'] == 1000
        assert pearl['batch_yield_is_estimate']
    finally:
        service.close()
