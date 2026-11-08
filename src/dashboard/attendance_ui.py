"""⏱️ Chấm công tab (inside 📅 Lịch làm): staff check in / out with a selfie on the shop WiFi; the manager
registers the shop network, approves face photos, reviews what the AI flagged and reads the timesheet."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from src.engine import attendance as att
from src.engine import staff_schedule as ss


def _ip() -> str | None:
    try:
        return att.client_ip(dict(st.context.headers), st.context.ip_address)
    except Exception:  # noqa: BLE001 - outside a browser session (tests)
        return None


def _network_line(ip):
    if att.on_shop_network(ip):
        st.success('📶 Đang dùng WiFi của quán — chấm công được.')
    else:
        st.error('📵 Không phải WiFi của quán (có thể đang dùng 4G). Kết nối WiFi quán để chấm công.')
        st.caption(f'Địa chỉ mạng hiện tại: {ip or "không xác định"}')


def render_attendance_staff(username: str):
    if flash := st.session_state.pop('att_flash', None):
        (st.success if flash[0] == 'ok' else st.error)(flash[1])
    ip = _ip()
    profile = att.face_profile(username)
    if not profile or profile['status'] == 'REJECTED':
        st.markdown('#### Đăng ký khuôn mặt')
        if profile:
            st.warning('Ảnh trước chưa được duyệt — chụp lại rõ mặt, đủ sáng.')
        st.caption('Chụp một ảnh chính diện, rõ mặt. Quản lý duyệt xong bạn mới chấm công được.')
        consent = st.checkbox('Tôi đồng ý cho cửa hàng lưu ảnh khuôn mặt của tôi và dùng AI (Google Gemini) so ảnh '
                              'khi chấm công. Tôi có thể xin xóa bất cứ lúc nào.', key='att_consent')
        shot = st.camera_input('Ảnh khuôn mặt mẫu', key='att_enroll_cam', disabled=not consent)
        if shot and st.button('Gửi ảnh cho Quản lý duyệt', key='att_enroll', type='primary'):
            att.enroll(username, shot.getvalue(), consent)
            st.session_state['att_flash'] = ('ok', 'Đã gửi ảnh — chờ Quản lý duyệt.')
            st.rerun()
        return
    if profile['status'] == 'PENDING':
        st.info('Ảnh khuôn mặt của bạn đang chờ Quản lý duyệt.')
        return

    now = ss.now_vn()
    info = att.state(username, now)
    block = info['block']
    st.markdown(f"#### Hôm nay {ss.day_label(now.date())}: " + (block['label'] if block else 'bạn không có ca trong lịch'))
    _network_line(ip)
    action = info['next']
    label = '✅ Check-in' if action == 'IN' else '🏁 Check-out'
    shot = st.camera_input(f'Chụp mặt để {label[2:].lower()}', key=f'att_cam_{action}', disabled=not att.on_shop_network(ip))
    if st.button(label, key='att_check', type='primary', disabled=not (shot and att.on_shop_network(ip))):
        with st.spinner('AI đang so khuôn mặt…'):
            try:
                rec = att.check(action, username, shot.getvalue(), ip)
            except ValueError as exc:
                st.session_state['att_flash'] = ('err', str(exc))
            else:
                when = att.TIMING_VI[rec['timing']] + (f" {rec['minutes']} phút" if rec['timing'] in ('LATE', 'EARLY') else '')
                verdict = 'AI đã xác nhận khuôn mặt.' if rec['status'] == 'AUTO_OK' else 'Quản lý sẽ xem lại lượt này.'
                st.session_state['att_flash'] = ('ok', f"{'Check-in' if action == 'IN' else 'Check-out'} lúc {rec['at']:%H:%M} · {when}. {verdict}")
        st.rerun()
    if info['records']:
        st.markdown('**Hôm nay**')
        st.dataframe(pd.DataFrame([{'Lượt': 'Vào' if r['kind'] == 'IN' else 'Ra', 'Giờ': f"{r['at']:%H:%M}",
                                    'Giờ giấc': att.TIMING_VI[r['timing']] + (f" {r['minutes']}′" if r['minutes'] else ''),
                                    'Khuôn mặt': att.FACE_VI[r['face']], 'Duyệt': att.STATUS_VI[r['status']]} for r in info['records']]),
                     hide_index=True, width='stretch')
    with st.expander('Xóa ảnh khuôn mặt của tôi'):
        st.caption('Xóa ảnh mẫu thì bạn không chấm công được nữa cho tới khi đăng ký lại.')
        if st.button('Xóa ảnh mẫu', key='att_delete_face'):
            att.delete_face(username)
            st.rerun()


def render_attendance_admin(user_name: str):
    if flash := st.session_state.pop('att_flash', None):
        (st.success if flash[0] == 'ok' else st.error)(flash[1])
    ip = _ip()
    with st.expander(f"📶 WiFi của quán ({len(att.networks())} mạng)", expanded=not att.networks()):
        st.caption('Đứng ở quán, bắt WiFi quán rồi bấm nút dưới. Chỉ thiết bị dùng mạng này mới chấm công được '
                   '(4G bị chặn). Nếu nhà mạng đổi IP của quán, bấm lại để cập nhật.')
        st.write(f'Mạng bạn đang dùng: `{ip or "không xác định"}`')
        if ip and not att.on_shop_network(ip) and st.button('Dùng mạng hiện tại làm WiFi quán', key='att_add_net', type='primary'):
            att.add_network(ip, 'WiFi quán', user_name)
            st.session_state['att_flash'] = ('ok', f'Đã thêm {ip}.')
            st.rerun()
        for n in att.networks():
            c = st.columns([3, 1])
            c[0].write(f"`{n['ip']}` · {n['label']} · thêm bởi {n['added_by']} {n['added_at']:%d/%m %H:%M}")
            if c[1].button('Xóa', key=f"att_rm_{n['ip']}"):
                att.remove_network(n['ip'])
                st.rerun()

    faces = att.pending_faces()
    if faces:
        st.markdown(f'#### 🙂 Ảnh khuôn mặt chờ duyệt ({len(faces)})')
        for f in faces:
            c = st.columns([1, 2, 1, 1], vertical_alignment='center')
            if data := att.read_photo(f['photo']):
                c[0].image(data, width=120)
            c[1].write(f"**{f['full_name']}** — kiểm tra đúng người, rõ mặt.")
            if c[2].button('Duyệt', key=f"face_ok_{f['username']}", type='primary'):
                att.review_face(f['username'], True, user_name)
                st.rerun()
            if c[3].button('Từ chối', key=f"face_no_{f['username']}"):
                att.review_face(f['username'], False, user_name)
                st.rerun()

    queue = att.needs_review()
    st.markdown(f'#### 🔎 Lượt cần Quản lý xem ({len(queue)})')
    if not queue:
        st.caption('AI đã duyệt hết, không có lượt nào cần xem.')
    names = {e['username']: e['full_name'] for e in ss.employees()}
    for r in queue[:20]:
        with st.container(border=True):
            c = st.columns([1, 1, 2.4, 1, 1], vertical_alignment='center')
            ref = att.face_profile(r['username'])
            if ref and (data := att.read_photo(ref['photo'])):
                c[0].image(data, caption='Ảnh mẫu', width=110)
            if data := att.read_photo(r['photo']):
                c[1].image(data, caption='Lúc chấm công', width=110)
            c[2].markdown(f"**{names.get(r['username'], r['username'])}** · {'Vào' if r['kind'] == 'IN' else 'Ra'} "
                          f"{r['at']:%H:%M %d/%m} · {att.TIMING_VI[r['timing']]}"
                          + (f" {r['minutes']} phút" if r['minutes'] else '')
                          + f"  \nAI: **{att.FACE_VI[r['face']]}**" + (f" ({r['confidence']:.0%})" if r['confidence'] is not None else '')
                          + (f" — {r['reason']}" if r['reason'] else ''))
            if c[3].button('Tính công', key=f"att_ok_{r['id']}", type='primary'):
                att.review(r['id'], True, user_name)
                st.rerun()
            if c[4].button('Không tính', key=f"att_no_{r['id']}"):
                att.review(r['id'], False, user_name)
                st.rerun()

    st.markdown('#### 📋 Bảng công')
    today = ss.now_vn().date()
    start = st.date_input('Từ ngày', value=ss.week_start(today), format='DD/MM/YYYY', key='att_from')
    end = start + timedelta(days=6)
    rows = att.timesheet(start, end)
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, width='stretch')
        late = df.groupby('Nhân viên')[['Muộn (phút)', 'Về sớm (phút)']].sum()
        late['Số lần muộn'] = df[df['Muộn (phút)'] > 0].groupby('Nhân viên').size()
        st.caption('Tổng tuần: ' + ' · '.join(f"{n}: muộn {int(r['Muộn (phút)'])}′, về sớm {int(r['Về sớm (phút)'])}′"
                                              for n, r in late.iterrows()))
    else:
        st.caption('Chưa có ca hoặc lượt chấm công nào trong tuần này.')
    st.caption(f"Quy tắc: vào muộn hơn {att.CHECKIN_GRACE_MIN} phút sau giờ bắt đầu ca là đi muộn (tính từ giờ bắt đầu); "
               'ra sớm hơn 5 phút (ca tối 10 phút) trước giờ kết thúc là về sớm.')
