"""Qualitative preparation advice, separate from numerical demand adjustment."""
import math


def weather_preparation_advice(context):
    comparison = context.get('comparison', {})
    target = comparison.get('target_weather_forecast')
    if not target:
        return None
    rain = target.get('rain_mm')
    if not isinstance(rain, (int, float)) or not math.isfinite(rain) or rain < 0:
        return None
    if rain == 0:
        return None
    previous = comparison.get('previous_weather_estimate') or {}
    prefix = f"Ngày {context.get('target_date', 'cần bán')} dự báo có mưa trong giờ bán ({rain:g} mm)."
    if previous.get('rain_mm') == 0:
        prefix += ' Ngày trước ước tính không mưa trong khung giờ này.'
    peak = target.get('peak_rain_mm')
    if isinstance(peak, (int, float)) and math.isfinite(peak) and peak > 0:
        prefix += ' Có mưa trong cả khung giờ cao điểm.'
    return (prefix + ' Nên cân nhắc chuẩn bị ít hơn ở đợt đầu đối với topping hạn dùng ngắn, '
            'chia thành nhiều mẻ nhỏ và nấu bổ sung theo lượng khách thực tế. '
            'Đối chiếu số ly bán, đơn giao hàng và tồn còn dùng được trước mỗi mẻ; '
            'nếu khách vẫn đông thì giữ nhịp bổ sung. '
            'Đây là gợi ý thận trọng theo thời tiết, chưa quy đổi thành % giảm hoặc tự giảm định lượng kế hoạch.')
