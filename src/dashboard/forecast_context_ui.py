"""Show what went into a forecast without overstating unavailable weather."""
import streamlit as st

from src.engine.weather_advice import previous_sales_text, weather_preparation_advice


def render_forecast_context(context):
    if not context:
        return
    advice = weather_preparation_advice(context)
    if advice:
        st.info('**Gợi ý chuẩn bị theo thời tiết**\n\n' + advice)
    for note in context.get('notes', []):
        st.info(note)
    for warning in context.get('warnings', []):
        st.warning(warning)
    st.caption(f"Thời tiết khu vực: {context.get('location', 'chưa xác định')} · Giờ bán: {context.get('opening_hours', 'chưa xác định')}")
    previous_sales = context.get('previous_sales')
    if previous_sales:
        st.write(previous_sales_text(previous_sales, bold=True))
    comparison = context.get('comparison', {})
    previous = comparison.get('previous_weather_estimate')
    target = comparison.get('target_weather_forecast')
    if previous and target:
        left, right = st.columns(2)
        left.info(f"**Ngày trước ({comparison['previous_date']}) · ước tính thời tiết**\n\n"
                  f"{previous['temperature_c']:.1f}°C · Mưa trong giờ bán {previous['rain_mm']:.1f} mm")
        right.info(f"**Ngày cần bán ({context['target_date']}) · dự báo thời tiết**\n\n"
                   f"{target['temperature_c']:.1f}°C · Mưa trong giờ bán {target['rain_mm']:.1f} mm")
    for day in context.get('days', []):
        sales = day.get('previous_day')
        if sales and not previous_sales:
            st.write(f"Ngày trước bán **{sales['cups']:,.0f} ly**, doanh thu **{sales['revenue']:,.0f} đ**.")
        if day.get('status') == 'WEATHER_VALIDATED':
            st.success(f"Đã xét thời tiết và sức bán: dự báo nền {day['baseline_total_cups']:,.0f} ly → "
                       f"{day['context_total_cups']:,.0f} ly.")
            st.caption(f"Riêng kịch bản thời tiết ngày cần bán so với ngày trước làm dự báo đổi "
                       f"{day['weather_scenario_delta_cups']:+,.0f} ly trong mô hình. Đây không phải kết luận quan hệ nhân quả.")
        elif day.get('status') == 'SALES_CONTEXT_ONLY':
            st.info(f"Đã điều chỉnh theo sức bán gần đây: {day['baseline_total_cups']:,.0f} → {day['context_total_cups']:,.0f} ly. Chưa áp dụng tác động thời tiết.")
        validation = day.get('validation')
        if validation:
            with st.expander('Xem kiểm chứng và dữ liệu sử dụng'):
                st.write(f"Kiểm chứng theo thời gian trên {validation['days']} ngày "
                         f"({validation['first_date']} – {validation['last_date']}).")
                st.write(f"WAPE: nền {validation['baseline_WAPE_pct']}% · sức bán {validation['sales_context_WAPE_pct']}% · "
                         f"sức bán + thời tiết {validation['weather_WAPE_pct']}%.")
                st.caption('Sai số tổng số ly toàn cửa hàng; khác với sai số từng món. Mưa, nhiệt độ được lấy từ bản dự báo lưu trước ngày bán, không dùng thời tiết thực tế tương lai.')
    if context.get('retrieved_at'):
        st.caption(f"Nguồn: Open-Meteo / ECMWF IFS · Lấy lúc {context['retrieved_at']}. Lượng mưa chỉ cộng trong giờ bán; khung cao điểm mặc định 14–20h.")
