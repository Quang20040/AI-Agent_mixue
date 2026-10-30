"""Weather can inform cautious prep even when it has no validated cup effect."""
import copy

import pytest

from src.agent.response_policy import forecast_context_note, required_evidence_tools
from src.engine.weather_advice import weather_preparation_advice


def context(rain=5, peak=2):
    return {'status': 'BASELINE_RETAINED', 'target_date': '2026-10-17',
            'comparison': {'previous_weather_estimate': {'rain_mm': 0, 'temperature_c': 30},
                           'target_weather_forecast': {'rain_mm': rain, 'peak_rain_mm': peak, 'temperature_c': 26}}}


def test_rain_advice_is_independent_of_numerical_forecast():
    data = context()
    before = copy.deepcopy(data)
    advice = weather_preparation_advice(data)
    assert 'dự báo có mưa' in advice
    assert 'ít hơn ở đợt đầu' in advice
    assert 'cao điểm' in advice
    assert 'đơn giao hàng' in advice
    assert 'chưa quy đổi thành % giảm' in advice
    assert data == before
    assert advice in forecast_context_note(data)


@pytest.mark.parametrize('rain', [0, None, -1, float('nan'), float('inf'), '5'])
def test_no_rain_claim_for_dry_missing_or_invalid_weather(rain):
    assert weather_preparation_advice(context(rain)) is None
    assert weather_preparation_advice({}) is None


def test_rain_outside_peak_does_not_claim_peak_rain():
    assert 'cao điểm' not in weather_preparation_advice(context(2, 0))


def test_rain_related_preparation_advice_requires_weather_evidence():
    assert required_evidence_tools('Hôm nay mưa nên chuẩn bị nguyên liệu thế nào?') == {'get_weather_forecast'}
    assert required_evidence_tools('Dự báo thời tiết hôm nay') == {'get_weather_forecast'}
    assert required_evidence_tools('Dự báo số ly ngày mai') == {'forecast_demand'}
    assert required_evidence_tools('Hôm nay có mưa không?') == {'get_weather_forecast'}


def test_actual_sales_and_weather_does_not_require_a_cup_prediction():
    from src.agent.response_policy import required_evidence_groups
    groups = required_evidence_groups('Số ly bán được hôm nay và thời tiết hôm nay?')
    assert {'forecast_demand'} not in groups
    assert {'get_weather_forecast'} in groups
