"""Public weather inputs. No sales or recipes are sent to the weather provider."""
import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
VN = timezone(timedelta(hours=7))


@dataclass(frozen=True)
class WeatherSettings:
    enabled: bool = False
    store_id: str = ''
    latitude: float = 21.0285
    longitude: float = 105.8542
    location_label: str = 'Hà Nội · điểm tham chiếu thành phố'
    opening_hour: int = 8
    closing_hour: int = 22
    peak_start: int = 14
    peak_end: int = 20
    timeout: float = 10
    cache_dir: str = str(ROOT / 'data' / 'weather_private')

    def __post_init__(self):
        if not (-90 <= self.latitude <= 90 and -180 <= self.longitude <= 180):
            raise ValueError('Invalid weather coordinates')
        if not (0 <= self.opening_hour <= self.peak_start < self.peak_end <= self.closing_hour <= 24):
            raise ValueError('Invalid opening/peak hours')

    @classmethod
    def from_env(cls):
        values = {**dotenv_values(ROOT / '.env'), **os.environ}
        opening = int(values.get('STORE_OPENING_HOUR') or 8)
        closing = int(values.get('STORE_CLOSING_HOUR') or 22)
        peak_start = min(max(14, opening), closing - 1)
        peak_end = max(peak_start + 1, min(20, closing))
        return cls(enabled=str(values.get('WEATHER_ENABLED', 'false')).lower() == 'true',
                   store_id=values.get('STORE_ID') or '',
                   latitude=float(values.get('WEATHER_LATITUDE') or 21.0285),
                   longitude=float(values.get('WEATHER_LONGITUDE') or 105.8542),
                   location_label=values.get('WEATHER_LOCATION_LABEL') or cls.location_label,
                   opening_hour=opening, closing_hour=closing, peak_start=peak_start, peak_end=peak_end)


class WeatherUnavailable(Exception):
    pass


class WeatherClient:
    def __init__(self, settings=None, session=None):
        self.settings = settings or WeatherSettings.from_env()
        self.session = session or requests.Session()

    def _request(self, kind, start, end, variables):
        cfg = self.settings
        if not cfg.enabled:
            raise WeatherUnavailable('DISABLED')
        params = {'latitude': cfg.latitude, 'longitude': cfg.longitude, 'timezone': 'Asia/Ho_Chi_Minh',
                  'start_date': start.isoformat(), 'end_date': end.isoformat(), 'hourly': ','.join(variables),
                  'models': 'ecmwf_ifs025'}
        endpoint = ('https://previous-runs-api.open-meteo.com/v1/forecast' if kind == 'history'
                    else 'https://api.open-meteo.com/v1/forecast')
        key = hashlib.sha256(json.dumps([endpoint, params], sort_keys=True).encode()).hexdigest()
        path = Path(cfg.cache_dir) / (key + '.json')
        ttl = 3600 if kind == 'forecast' else 86400
        try:
            cached = json.loads(path.read_text(encoding='utf-8'))
            if time.time() - cached['saved_at'] < ttl:
                return cached['payload'], cached['fetched_at']
        except (OSError, ValueError, KeyError):
            pass
        try:
            response = self.session.get(endpoint, params=params, timeout=cfg.timeout)
            response.raise_for_status()
            payload = response.json()
            if payload.get('error') or 'hourly' not in payload:
                raise WeatherUnavailable('INVALID_RESPONSE')
        except (requests.RequestException, ValueError) as exc:
            raise WeatherUnavailable('PROVIDER_UNAVAILABLE') from exc
        fetched_at = datetime.now(VN).isoformat(timespec='seconds')
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'saved_at': time.time(), 'fetched_at': fetched_at, 'payload': payload}), encoding='utf-8')
        except OSError:
            pass
        return payload, fetched_at

    def _aggregate(self, payload, suffix=''):
        hourly = payload['hourly']
        # The API accepts _previous_day0 but returns its keys unsuffixed.
        if suffix == '_previous_day0' and 'temperature_2m_previous_day0' not in hourly:
            suffix = ''
        temp = hourly.get('temperature_2m' + suffix, [])
        rain = hourly.get('precipitation' + suffix, [])
        if len(temp) != len(hourly['time']) or len(rain) != len(temp):
            raise WeatherUnavailable('MISSING_VARIABLES')
        days = {}
        for stamp, t, r in zip(hourly['time'], temp, rain):
            moment = datetime.fromisoformat(stamp)
            if not self.settings.opening_hour <= moment.hour < self.settings.closing_hour:
                continue
            if t is None or r is None or not np.isfinite(float(t)) or not np.isfinite(float(r)) or r < 0:
                continue
            days.setdefault(moment.date(), []).append((moment.hour, float(t), float(r)))
        expected = self.settings.closing_hour - self.settings.opening_hour
        return {day: {'temperature_c': round(float(np.mean([v[1] for v in rows])), 2),
                      'rain_mm': round(sum(v[2] for v in rows), 2),
                      'peak_rain_mm': round(sum(v[2] for v in rows if self.settings.peak_start <= v[0] < self.settings.peak_end), 2)}
                for day, rows in days.items() if len({v[0] for v in rows}) == expected}

    def history(self, start, end):
        variables = [name + suffix for suffix in ('_previous_day0', '_previous_day1')
                     for name in ('temperature_2m', 'precipitation')]
        payload, stamp = self._request('history', start, end, variables)
        return {'reference': self._aggregate(payload, '_previous_day0'),
                'anticipated': self._aggregate(payload, '_previous_day1'), 'fetched_at': stamp,
                'source': 'Open-Meteo ECMWF IFS: archived day0 estimates and day1 forecasts'}

    def forecast(self, start, end):
        payload, stamp = self._request('forecast', start, end, ['temperature_2m', 'precipitation'])
        return {'days': self._aggregate(payload), 'fetched_at': stamp, 'source': 'Open-Meteo ECMWF IFS forecast'}

    def forecast_for_operations(self, target, *, now=None):
        """Fetch forecast evidence independently of sales history or model training."""
        now = now or datetime.now(VN)
        if not now.tzinfo:
            raise ValueError('Timezone-aware current time required')
        now = now.astimezone(VN)
        if not now.date() <= target <= now.date() + timedelta(days=6):
            return {'status': 'INVALID_DATE', 'message': 'Chọn hôm nay hoặc tối đa 6 ngày tới để tra dự báo mới.'}
        try:
            payload, stamp = self._request('forecast', target, target, ['temperature_2m', 'precipitation'])
            daily = self._aggregate(payload).get(target)
            if daily is None:
                raise WeatherUnavailable('INCOMPLETE_DAY')
            hourly = payload['hourly']
            rows = []
            for time_text, temp, rain in zip(hourly['time'], hourly['temperature_2m'], hourly['precipitation']):
                moment = datetime.fromisoformat(time_text).replace(tzinfo=VN)
                if moment.date() != target or not self.settings.opening_hour <= moment.hour < self.settings.closing_hour:
                    continue
                # Keep this hour and future hours; past rain must not drive advice for the rest of today.
                if moment < now.replace(minute=0, second=0, microsecond=0):
                    continue
                rows.append({'time': moment.isoformat(timespec='minutes'), 'temperature_c': temp, 'rain_mm': rain})
            remaining_rain = round(sum(float(row['rain_mm']) for row in rows), 2)
            remaining_peak = round(sum(float(row['rain_mm']) for row in rows
                if self.settings.peak_start <= datetime.fromisoformat(row['time']).hour < self.settings.peak_end), 2)
            from src.engine.weather_advice import weather_preparation_advice
            context = {'target_date': str(target), 'comparison': {'target_weather_forecast': {
                **daily, 'rain_mm': remaining_rain, 'peak_rain_mm': remaining_peak}}}
            advice = weather_preparation_advice(context) if rows else None
            if rows and not advice:
                advice = ('Các giờ bán còn lại trong dự báo chưa có mưa; chưa có cơ sở giảm chuẩn bị vì mưa. '
                          'Tiếp tục chia mẻ theo sức bán, đơn giao hàng và tồn còn dùng được.')
            return {'status': 'SUCCESS', 'target_date': str(target), 'location': self.settings.location_label,
                    'coordinates': {'latitude': self.settings.latitude, 'longitude': self.settings.longitude},
                    'fetched_at': stamp, 'cache_max_age_minutes': 60, 'timezone': 'Asia/Ho_Chi_Minh',
                    'source': 'Open-Meteo / ECMWF IFS 0.25°',
                    'source_url': 'https://open-meteo.com/en/docs/ecmwf-api',
                    'daily_business_hours': daily, 'upcoming_business_hours': rows,
                    'rainy_hours': [row for row in rows if row['rain_mm'] > 0],
                    'operational_advice': advice or 'Đã hết giờ bán theo cấu hình; không đề xuất nấu thêm cho hôm nay.',
                    'limitations': ['Đây là dự báo khu vực theo tọa độ cấu hình, không phải quan trắc ngay tại cửa hàng.',
                                    'Mô hình có lưới khoảng 25 km; ghim địa chỉ không đảm bảo dự báo chính xác tới từng số nhà.',
                                    'Một nguồn API, một mô hình ECMWF; chưa có đối chiếu độc lập nhiều nguồn.'],
                    'source_refs': ['https://open-meteo.com/en/docs/ecmwf-api']}
        except (WeatherUnavailable, ValueError, KeyError, TypeError):
            return {'status': 'WEATHER_UNAVAILABLE',
                    'message': 'Chưa lấy được dự báo hợp lệ; chưa thể khuyên tăng/giảm sơ chế theo thời tiết.'}
