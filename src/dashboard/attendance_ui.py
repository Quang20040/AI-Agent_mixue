"""⏱️ Chấm công tab (inside 📅 Lịch làm): staff get their GPS position, take a photo and check in / out;
the manager sets the shop location and radius, reviews what the AI flagged and reads the timesheet."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from src.engine import attendance as att
from src.engine import staff_schedule as ss

_GEO_HTML = '<button type="button" class="geo-btn">📍 Lấy vị trí của tôi</button><span class="geo-msg"></span>'
_GEO_CSS = """.geo-btn{background:#E60012;color:#fff;border:0;border-radius:10px;padding:9px 16px;font:600 14px sans-serif;cursor:pointer}
.geo-msg{margin-left:10px;font:13px sans-serif;color:#6b5560}"""
_GEO_JS = """export default function(component) {
  const { parentElement, setStateValue } = component;
  const btn = parentElement.querySelector('.geo-btn'), msg = parentElement.querySelector('.geo-msg');
  btn.onclick = () => {
    if (!navigator.geolocation) { msg.textContent = 'Trình duyệt không hỗ trợ định vị.'; return; }
    msg.textContent = 'Đang lấy vị trí…';
    navigator.geolocation.getCurrentPosition(
      p => { msg.textContent = 'Đã lấy vị trí.';
             setStateValue('position', {lat: p.coords.latitude, lon: p.coords.longitude,
                                        accuracy: p.coords.accuracy, at: Date.now()}); },
      e => { msg.textContent = e.code === 1 ? 'Bạn đã chặn quyền vị trí — mở cài đặt trình duyệt để cho phép.'
                                            : 'Không lấy được vị trí, thử lại.';
             setStateValue('position', {error: e.code, at: Date.now()}); },
      {enableHighAccuracy: true, timeout: 15000, maximumAge: 0});
  };
}"""


def get_position(key: str) -> dict | None:
    """Browser GPS position {'lat','lon','accuracy'} after the user presses the button (None before)."""
    import streamlit.components.v2 as components
    geo = components.component('mixue_geolocation', html=_GEO_HTML, css=_GEO_CSS, js=_GEO_JS)
    result = geo(key=key, on_position_change=lambda: None)
    pos = getattr(result, 'position', None)
    return dict(pos) if pos else None


def _ip() -> str | None:
    try:
        return att.client_ip(dict(st.context.headers), st.context.ip_address)
    except Exception:  # noqa: BLE001 - outside a browser session (tests)
        return None


def render_attendance_staff(username: str):
    if flash := st.session_state.pop('att_flash', None):
        (st.success if flash[0] == 'ok' else st.error)(flash[1])
    if att.shop_location() is None:
        st.info('Quản lý chưa đặt vị trí quán nên chưa chấm công được.')
        return
    now = ss.now_vn()
    info = att.state(username, now)
    block = info['block']
    action = info['next']
    st.markdown(f"#### Hôm nay {ss.day_label(now.date())}: " + (block['label'] if block else 'bạn không có ca trong lịch'))
    shop = att.shop_location()
    ip = _ip()
    wifi_ok = not shop['require_wifi'] or att.on_shop_network(ip)
    if shop['require_wifi']:
        st.markdown('**1. WiFi quán**')
        if wifi_ok:
            st.success('📶 Đang dùng WiFi của quán.')
        else:
            st.error('📵 Chưa bắt WiFi của quán (có thể đang dùng 4G). Tắt 4G, kết nối WiFi quán rồi tải lại trang.')
            st.caption(f'Địa chỉ mạng hiện tại: {ip or "không xác định"}')
    st.markdown(f"**{2 if shop['require_wifi'] else 1}. Vị trí**")
    position = get_position('att_geo_staff')
    place = att.where(position)
    place = {**place, 'ok': place['ok'] and wifi_ok}
    (st.success if place['ok'] else st.warning)(('📍 ' if place['ok'] else '⚠️ ') + place['message'])
    st.markdown(f"**{3 if shop['require_wifi'] else 2}. Chụp ảnh**")
    shot = st.camera_input('Chụp ảnh chấm công', key=f'att_cam_{action}', disabled=not place['ok'], label_visibility='collapsed')
    label = '✅ Check-in' if action == 'IN' else '🏁 Check-out'
    if st.button(label, key='att_check', type='primary', disabled=not (shot and place['ok'])):
        with st.spinner('AI đang xem ảnh…'):
            try:
                rec = att.check(action, username, shot.getvalue(), position, _ip())
            except ValueError as exc:
                st.session_state['att_flash'] = ('err', str(exc))
            else:
                when = att.TIMING_VI[rec['timing']] + (f" {rec['minutes']} phút" if rec['timing'] in ('LATE', 'EARLY') else '')
                verdict = 'AI đã duyệt.' if rec['status'] == 'AUTO_OK' else 'Quản lý sẽ xem lại lượt này.'
                st.session_state['att_flash'] = ('ok', f"{'Check-in' if action == 'IN' else 'Check-out'} lúc {rec['at']:%H:%M} · {when}. {verdict}")
        st.rerun()
    if info['records']:
        st.markdown('**Hôm nay**')
        st.dataframe(pd.DataFrame([{'Lượt': 'Vào' if r['kind'] == 'IN' else 'Ra', 'Giờ': f"{r['at']:%H:%M}",
                                    'Giờ giấc': att.TIMING_VI[r['timing']] + (f" {r['minutes']}′" if r['minutes'] else ''),
                                    'Cách quán': f"{r['distance_m']} m" if r['distance_m'] is not None else '—',
                                    'Ảnh': att.AI_VI[r['ai']], 'Duyệt': att.STATUS_VI[r['status']]} for r in info['records']]),
                     hide_index=True, width='stretch')
        cols = st.columns(4)
        for i, r in enumerate(info['records'][-4:]):
            if data := att.read_photo(r['photo']):
                cols[i].image(data, caption=f"{'Vào' if r['kind'] == 'IN' else 'Ra'} {r['at']:%H:%M}", width='stretch')


def render_attendance_admin(user_name: str):
    if flash := st.session_state.pop('att_flash', None):
        (st.success if flash[0] == 'ok' else st.error)(flash[1])
    shop = att.shop_location()
    with st.expander('📍 Vị trí quán & bán kính chấm công' + (f" · {shop['radius_m']} m" if shop else ' · chưa đặt'), expanded=shop is None):
        st.caption('Đứng trong quán, bấm “Lấy vị trí của tôi”, rồi “Dùng làm vị trí quán”. Nhân viên chỉ chấm công được '
                   'khi điện thoại ở trong bán kính này.')
        if shop:
            st.write(f"Hiện tại: `{shop['lat']:.6f}, {shop['lon']:.6f}` · bán kính **{shop['radius_m']} m**")
        position = get_position('att_geo_admin')
        radius = st.number_input('Bán kính (m)', 20, 1000, value=shop['radius_m'] if shop else 100, step=10, key='att_radius')
        c = st.columns(2)
        if c[0].button('Dùng vị trí vừa lấy làm vị trí quán', key='att_set_loc', type='primary',
                       disabled=not (position and position.get('lat') is not None)):
            att.set_shop_location(float(position['lat']), float(position['lon']), int(radius), user_name)
            st.session_state['att_flash'] = ('ok', f"Đã đặt vị trí quán (sai số GPS lúc lấy ~{position.get('accuracy', 0):.0f} m).")
            st.rerun()
        if shop and c[1].button('Chỉ đổi bán kính', key='att_set_radius'):
            att.set_shop_location(shop['lat'], shop['lon'], int(radius), user_name)
            st.rerun()

    ip = _ip()
    nets = att.networks()
    require = shop['require_wifi'] if shop else True
    with st.expander(f"📶 WiFi của quán · {'bắt buộc' if require else 'không bắt buộc'} · {len(nets)} mạng đã lưu",
                     expanded=require and not nets):
        st.caption('Đứng ở quán, bắt WiFi quán (tắt 4G), bấm nút dưới. Nếu nhà mạng đổi IP của quán (thường sau khi '
                   'khởi động lại modem), nhân viên sẽ bị báo không phải WiFi quán — bấm lại để thêm IP mới.')
        st.markdown(f'Mạng bạn đang dùng: **`{ip or "không xác định"}`** — '
                    + ('✅ là WiFi quán' if att.on_shop_network(ip) else '❌ chưa có trong danh sách'))
        if ip and not att.on_shop_network(ip) and st.button('Dùng mạng hiện tại làm WiFi quán', key='att_add_net', type='primary'):
            att.add_network(ip, 'WiFi quán', user_name)
            st.session_state['att_flash'] = ('ok', f'Đã thêm {ip}.')
            st.rerun()
        for n in nets:
            c = st.columns([3, 1])
            c[0].write(f"`{n['ip']}` · thêm bởi {n['added_by']} {n['added_at']:%d/%m %H:%M}")
            if c[1].button('Xóa', key=f"att_rm_{n['ip']}"):
                att.remove_network(n['ip'])
                st.rerun()
        wifi = st.toggle('Bắt buộc WiFi của quán khi chấm công (chặn 4G)', value=require, key='att_wifi_toggle')
        if wifi != require:
            att.set_require_wifi(wifi, user_name)
            st.rerun()

    queue = att.needs_review()
    st.markdown(f'#### 🔎 Lượt cần Quản lý xem ({len(queue)})')
    if not queue:
        st.caption('AI đã duyệt hết, không có lượt nào cần xem.')
    names = {e['username']: e['full_name'] for e in ss.employees()}
    for r in queue[:20]:
        with st.container(border=True):
            c = st.columns([1, 3, 1, 1, 1], vertical_alignment='center')
            if data := att.read_photo(r['photo']):
                c[0].image(data, width=120)
            c[1].markdown(f"**{names.get(r['username'], r['username'])}** · {'Vào' if r['kind'] == 'IN' else 'Ra'} "
                          f"{r['at']:%H:%M %d/%m} · {att.TIMING_VI[r['timing']]}" + (f" {r['minutes']} phút" if r['minutes'] else '')
                          + (f" · cách quán {r['distance_m']} m" if r['distance_m'] is not None else '')
                          + f"  \nAI: **{att.AI_VI[r['ai']]}**" + (f" — {r['reason']}" if r['reason'] else ''))
            if c[2].button('Tính công', key=f"att_ok_{r['id']}", type='primary'):
                att.review(r['id'], True, user_name)
                st.rerun()
            if c[3].button('Không tính', key=f"att_no_{r['id']}"):
                att.review(r['id'], False, user_name)
                st.rerun()
            if r['ai'] == 'UNAVAILABLE' and c[4].button('🤖 AI xem lại', key=f"att_ai_{r['id']}"):
                with st.spinner('AI đang xem ảnh…'):
                    res = att.rereview(r['id'])
                st.session_state['att_flash'] = ('ok' if res['ai'] != 'UNAVAILABLE' else 'err',
                                                 f"AI: {att.AI_VI[res['ai']]}" + (f" — {res['reason']}" if res['reason'] else ''))
                st.rerun()

    st.markdown('#### 📋 Bảng công')
    today = ss.now_vn().date()
    start = st.date_input('Từ ngày', value=ss.week_start(today), format='DD/MM/YYYY', key='att_from')
    rows = att.timesheet(start, start + timedelta(days=6))
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, width='stretch')
        total = df.groupby('Nhân viên')[['Muộn (phút)', 'Về sớm (phút)']].sum()
        st.caption('Tổng tuần: ' + ' · '.join(f"{n}: muộn {int(r['Muộn (phút)'])}′, về sớm {int(r['Về sớm (phút)'])}′"
                                              for n, r in total.iterrows()))
    else:
        st.caption('Chưa có ca hoặc lượt chấm công nào trong tuần này.')
    with st.expander('🖼️ Ảnh chấm công theo ngày'):
        day = st.date_input('Ngày', value=today, format='DD/MM/YYYY', key='att_photo_day')
        recs = att.day_records(day)
        if not recs:
            st.caption('Không có lượt chấm công nào.')
        cols = st.columns(4)
        for i, r in enumerate(recs):
            if data := att.read_photo(r['photo']):
                cols[i % 4].image(data, width='stretch', caption=f"{names.get(r['username'], r['username'])} · "
                                  f"{'Vào' if r['kind'] == 'IN' else 'Ra'} {r['at']:%H:%M} · {att.STATUS_VI[r['status']]}")
    st.caption(f"Quy tắc: vào muộn hơn {att.CHECKIN_GRACE_MIN} phút sau giờ bắt đầu ca là đi muộn (tính từ giờ bắt đầu); "
               'ra sớm hơn 5 phút (ca tối 10 phút) trước giờ kết thúc là về sớm.')
