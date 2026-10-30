from datetime import date, datetime

from src.agent.response_policy import grounded_result_reply
from src.engine.weather import VN, WeatherClient, WeatherSettings, WeatherUnavailable


class Client(WeatherClient):
    def _request(self, *args):
        return {'hourly': {'time': [f'2026-10-16T{h:02d}:00' for h in range(24)],
                           'temperature_2m': [28] * 24,
                           'precipitation': [3 if h == 9 else 0 for h in range(24)]}}, '2026-10-16T14:00:00+07:00'


def test_afternoon_advice_does_not_use_morning_rain():
    result = Client(WeatherSettings(enabled=True)).forecast_for_operations(
        date(2026, 10, 16), now=datetime(2026, 10, 16, 14, 30, tzinfo=VN))
    assert result['status'] == 'SUCCESS'
    assert result['daily_business_hours']['rain_mm'] == 3
    assert result['rainy_hours'] == []
    assert 'chưa có cơ sở giảm' in result['operational_advice']
    reply = grounded_result_reply('Thời tiết hôm nay?', [{'tool': 'get_weather_forecast', 'result': result}])
    assert 'Lấy lúc' in reply['text']
    assert 'https://open-meteo.com' in reply['text']
    assert '25 km' in reply['text']
    assert 'đối chiếu độc lập' in result['limitations'][-1]


def test_weather_failure_never_becomes_rain_advice():
    class Broken(Client):
        def _request(self, *args):
            raise WeatherUnavailable()
    result = Broken().forecast_for_operations(date(2026, 10, 16), now=datetime(2026, 10, 16, tzinfo=VN))
    assert result['status'] == 'WEATHER_UNAVAILABLE'
    assert 'operational_advice' not in result


def test_rejects_historical_date_as_live_forecast():
    result = Client().forecast_for_operations(date(2026, 10, 15), now=datetime(2026, 10, 16, tzinfo=VN))
    assert result['status'] == 'INVALID_DATE'


def test_compound_reply_uses_both_tools_and_keeps_baseline_warning():
    weather = Client(WeatherSettings(enabled=True)).forecast_for_operations(
        date(2026, 10, 16), now=datetime(2026, 10, 16, 14, 30, tzinfo=VN))
    forecast = {'status': 'SUCCESS', 'target_date': '2026-10-16', 'total_forecasted_cups': 500,
                'daily_forecasts': [{}], 'source_refs': ['table:sales_daily'],
                'forecast_context': {'warnings': ['Chưa điều chỉnh số ly theo thời tiết.']}}
    reply = grounded_result_reply('Dự báo số ly và thời tiết hôm nay', [
        {'tool': 'forecast_demand', 'result': forecast}, {'tool': 'get_weather_forecast', 'result': weather}])
    assert '500 ly' in reply['text']
    assert 'chưa có cơ sở giảm' in reply['text']
    assert 'Chưa điều chỉnh số ly' in reply['text']
    assert reply['evidence_refs'] == ['table:sales_daily', weather['source_url']]
    repeated = grounded_result_reply('Dự báo số ly và thời tiết hôm nay', [
        {'tool': 'forecast_demand', 'result': forecast},
        {'tool': 'forecast_demand', 'result': forecast},
        {'tool': 'get_weather_forecast', 'result': weather}])
    assert repeated == reply


def test_compound_reply_does_not_merge_different_days():
    weather = Client(WeatherSettings(enabled=True)).forecast_for_operations(
        date(2026, 10, 16), now=datetime(2026, 10, 16, 14, 30, tzinfo=VN))
    assert grounded_result_reply('Dự báo số ly và thời tiết', [
        {'tool': 'forecast_demand', 'result': {'status': 'SUCCESS', 'target_date': '2026-10-17'}},
        {'tool': 'get_weather_forecast', 'result': weather}]) is None
