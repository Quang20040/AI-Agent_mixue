"""📅 Lịch làm — the manager has the AI draft the week, edits it, approves it; staff see it and report busy days."""
from __future__ import annotations

from datetime import date, timedelta
from html import escape

import pandas as pd
import streamlit as st

from src.engine import staff_schedule as ss

SHIFT_PICK = {'Cả ngày': None, 'Ca sáng': 'CA_SANG', 'Ca chiều': 'CA_CHIEU', 'Ca tối': 'CA_TOI'}


def _today():
    from src.engine.stock_matrix import today_vn
    return today_vn()


def render_week_table(schedule: dict, highlight: str | None = None):
    """Days × shifts with names; the signed-in person's name in bold red."""
    if not schedule:
        return
    names = {e['username']: e['full_name'] for e in ss.employees()}
    head = ''.join(f'<th>{s}</th>' for s in ('Ngày', 'Sáng', 'Chiều', 'Tối'))
    body = []
    today = _today()
    for d in ss.week_days(date.fromisoformat(schedule['week_start'])):
        slots = schedule['assignments'].get(d.isoformat(), {})
        need = schedule.get('needs', {}).get(d.isoformat(), ss.DEFAULT_NEED)
        cells = []
        for s in ss.SHIFTS:
            people = [(f'<b style="color:#E60012">{escape(names.get(u, u))}</b>' if u == highlight else escape(names.get(u, u)))
                      for u in slots.get(s, [])]
            short = len(people) < int(need.get(s, 0))
            cells.append(f"<td>{'<br>'.join(people) or '—'}{' <span title=thiếu người>⚠️</span>' if short else ''}</td>")
        style = ' style="background:#fff4f5"' if d == today else ''
        body.append(f'<tr{style}><td><b>{ss.day_label(d)}</b></td>' + ''.join(cells) + '</tr>')
    st.markdown('<table class="px-sched" style="width:100%;border-collapse:collapse;font-size:14px">'
                f'<thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'
                '<style>.px-sched th,.px-sched td{border:1px solid #f0e2e5;padding:6px 10px;text-align:left;vertical-align:top}'
                '.px-sched th{background:#fbf3f4;font-weight:600}</style>', unsafe_allow_html=True)


def render_my_week(username: str, full_name: str = ''):
    """Small card on the staff home page."""
    start = ss.week_start(_today())
    mine = ss.my_shifts(username, start)
    with st.container(border=True, key='my_week_card'):
        st.markdown('#### 📅 Lịch làm tuần này của bạn')
        if not mine:
            st.caption('Quản lý chưa gửi lịch tuần này.')
            return
        working = [f"**{d['label']}**: " + ' + '.join(ss.SHIFT_VI[s] for s in d['shifts']) for d in mine if d['shifts']]
        st.markdown(' · '.join(working) if working else 'Tuần này bạn không có ca nào.')
        st.caption('Xem cả lịch và báo bận ở trang 📅 Lịch làm.')


def render_staff_reminders(items: list[dict], username: str):
    """Banners on every page for staff: answer the busy-days round, next shift."""
    from src.auth import SCHEDULE_PAGE

    def go():
        st.session_state.main_navigation = SCHEDULE_PAGE
        st.session_state['sched_week_staff'] = 'Tuần sau'
    for i, item in enumerate(items):
        with st.container(key=f'staff_reminder_{i}'):
            if item['kind'] == 'ask_busy':
                msg, a, b = st.columns([4, 1.2, 1.4], vertical_alignment='center')
                msg.warning(f"🗓️ {item['text']}")
                a.button('Báo ngày bận', key='rem_report_busy', on_click=go, use_container_width=True)
                if b.button('Tuần sau tôi rảnh', key='rem_no_busy', type='primary', use_container_width=True):
                    ss.confirm_no_busy(username, item['week'])
                    st.session_state['sched_flash'] = 'Đã ghi nhận: tuần sau bạn rảnh cả tuần.'
                    st.rerun()
            else:
                (st.info if item['kind'] != 'shift_soon' else st.warning)(f"⏰ {item['text']}")


def _pick_week(key: str) -> date:
    today = _today()
    choice = st.segmented_control('Tuần', ['Tuần này', 'Tuần sau', 'Chọn ngày'], default='Tuần sau' if key == 'admin' else 'Tuần này',
                                  key=f'sched_week_{key}') or 'Tuần này'
    if choice == 'Chọn ngày':
        picked = st.date_input('Một ngày trong tuần', value=today, format='DD/MM/YYYY', key=f'sched_day_{key}')
        return ss.week_start(picked)
    return ss.week_start(today + timedelta(days=7 if choice == 'Tuần sau' else 0))


def _busy_form(people, key, fixed_user=None, by=''):
    with st.form(f'busy_form_{key}', clear_on_submit=True, border=True):
        st.markdown('**Báo bận**')
        cols = st.columns([1.6, 1.2, 1.2, 1.1])
        if fixed_user:
            username = fixed_user
            cols[0].text_input('Nhân viên', value=next((p['full_name'] for p in people if p['username'] == fixed_user), fixed_user), disabled=True)
        else:
            labels = {p['username']: f"{p['full_name']} ({p['role_vi'].lower()})" for p in people}
            username = cols[0].selectbox('Nhân viên', list(labels), format_func=labels.get) if labels else None
        first = cols[1].date_input('Từ ngày', value=_today() + timedelta(days=1), min_value=_today(), format='DD/MM/YYYY')
        last = cols[2].date_input('Đến ngày', value=None, min_value=_today(), format='DD/MM/YYYY', help='Bỏ trống nếu chỉ một ngày')
        shift = cols[3].selectbox('Ca', list(SHIFT_PICK))
        reason = st.text_input('Lý do (không bắt buộc)', max_chars=200)
        if st.form_submit_button('Lưu ngày bận', type='primary') and username:
            last = last or first
            if last < first:
                st.error('Ngày kết thúc trước ngày bắt đầu.')
                return
            days = [first + timedelta(days=i) for i in range((last - first).days + 1)][:31]
            n = ss.add_busy(username, days, SHIFT_PICK[shift], reason, by)
            st.session_state['sched_flash'] = f'Đã ghi {n} ngày bận.' if n else 'Những ngày này đã được ghi từ trước.'
            st.rerun()


def _busy_table(start, end, key, only=None, can_delete=True):
    rows = [b for b in ss.busy_list(start, end) if only is None or b['username'] == only]
    if not rows:
        st.caption('Không có ai báo bận trong tuần này.')
        return
    for b in rows:
        c = st.columns([3, 1])
        c[0].markdown(f"**{escape(b['full_name'])}** · {ss.day_label(b['date'])} · "
                      f"{('ca ' + ss.SHIFT_VI[b['shift']].lower()) if b['shift'] else 'cả ngày'}"
                      + (f" · _{escape(b['reason'])}_" if b['reason'] else ''))
        if can_delete and c[1].button('Xóa', key=f"busy_del_{key}_{b['id']}"):
            ss.remove_busy(b['id'])
            st.rerun()


def _staff_schedule(people, username, user_name):
    start = _pick_week('staff')
    plan = ss.published(start)
    st.markdown(f"### Lịch làm tuần {start:%d/%m} – {start + timedelta(days=6):%d/%m/%Y}")
    if plan:
        render_week_table(plan['schedule'], highlight=username)
        st.caption(f"Đã duyệt bởi {plan.get('approved_by', '')} · tên của bạn tô đỏ.")
    else:
        st.info('Quản lý chưa gửi lịch tuần này.')
    st.divider()
    if any(p['username'] == username for p in people):
        c = ss.cycle()
        if c['open'] and start == c['target_week']:
            mine = next((r['response'] for r in ss.responses(start) if r['username'] == username), None)
            col = st.columns([3, 1.3], vertical_alignment='center')
            col[0].info(f"Hạn báo bận tuần này: **{c['deadline']:%H:%M %d/%m}**. "
                        + ('Bạn đã trả lời ✅' if mine else 'Bạn chưa trả lời — không báo thì coi như rảnh cả tuần.'))
            if col[1].button('Tuần này tôi rảnh', key='sched_no_busy', disabled=bool(mine)):
                ss.confirm_no_busy(username, start)
                st.session_state['sched_flash'] = 'Đã ghi nhận.'
                st.rerun()
        _busy_form(people, 'staff', fixed_user=username, by=user_name)
        st.markdown('**Ngày bạn đã báo bận (tuần đang xem)**')
        _busy_table(start, start + timedelta(days=6), 'staff', only=username)


def render_schedule_page(agent, user_role: str, user_name: str, username: str, is_admin: bool):
    if flash := st.session_state.pop('sched_flash', None):
        st.success(flash)
    people = ss.employees()
    if not is_admin:
        from src.dashboard.attendance_ui import render_attendance_staff
        tab_sched, tab_att = st.tabs(['🗓️ Lịch làm', '⏱️ Chấm công'])
        with tab_sched:
            _staff_schedule(people, username, user_name)
        with tab_att:
            render_attendance_staff(username)
        return

    tab_week, tab_people, tab_att = st.tabs(['🗓️ Lịch tuần', '👤 Ca chính & ngày bận', '⏱️ Chấm công'])
    with tab_att:
        from src.dashboard.attendance_ui import render_attendance_admin
        render_attendance_admin(user_name)
    with tab_week:
        start = _pick_week('admin')
        end = start + timedelta(days=6)
        st.markdown(f"### Tuần {start:%d/%m} – {end:%d/%m/%Y}")
        if not people:
            st.warning('Chưa có nhân viên chính thức / thử việc nào đang làm.')
            return
        published = ss.published(start)
        draft = ss.pending(start)
        _render_collection(start)
        if published and not draft:
            st.success(f"✅ Đã gửi cho nhân viên · duyệt bởi {published.get('approved_by', '')}")
            render_week_table(published['schedule'])
        if draft:
            _render_draft(agent, draft, user_role, user_name)
        st.markdown('#### Số người mỗi ca' + (' (cho lần xếp tiếp theo)' if draft or published else ''))
        st.caption('Mặc định sáng 1 · chiều 2 · tối 2. Sửa trực tiếp những ngày cần đông hơn.')
        needs_key = f'sched_needs_{start}'
        base = (draft or published or {}).get('schedule', {}).get('needs') or ss.default_needs(start)
        frame = pd.DataFrame([{'Ngày': ss.day_label(date.fromisoformat(d)), 'Sáng': v['CA_SANG'], 'Chiều': v['CA_CHIEU'], 'Tối': v['CA_TOI']}
                              for d, v in sorted(base.items())])
        edited = st.data_editor(frame, hide_index=True, width='stretch', key=needs_key, disabled=['Ngày'],
                                column_config={s: st.column_config.NumberColumn(s, min_value=0, max_value=6, step=1) for s in ('Sáng', 'Chiều', 'Tối')})
        needs = {d.isoformat(): {'CA_SANG': int(r['Sáng']), 'CA_CHIEU': int(r['Chiều']), 'CA_TOI': int(r['Tối'])}
                 for d, (_, r) in zip(ss.week_days(start), edited.iterrows())}
        label = '🔀 AI xếp lại phương án khác' if draft else ('🤖 AI xếp lịch mới cho tuần này' if published else '🤖 AI xếp lịch tuần')
        if st.button(label, key='sched_generate', type='secondary' if draft else 'primary'):
            if end < _today():
                st.error('Tuần này đã qua.')
            else:
                ss.create_draft(start, needs, by=user_name)
                st.session_state['sched_flash'] = 'AI đã xếp xong bản nháp — kiểm tra rồi bấm Duyệt & gửi.'
                st.rerun()
        with st.expander(f'Ngày bận trong tuần ({len(ss.busy_list(start, end))})'):
            _busy_table(start, end, 'week')

    with tab_people:
        st.markdown('#### Ca chính')
        st.caption('AI ưu tiên xếp mỗi người vào ca chính, rồi chia đều số ca trong tuần.')
        names = {'—': None, 'Sáng': 'CA_SANG', 'Chiều': 'CA_CHIEU', 'Tối': 'CA_TOI'}
        frame = pd.DataFrame([{'username': p['username'], 'Nhân viên': p['full_name'], 'Loại': p['role_vi'],
                               'Ca chính': ss.SHIFT_VI.get(p['main_shift'], '—')} for p in people])
        if frame.empty:
            st.caption('Chưa có nhân viên.')
        else:
            edited = st.data_editor(frame, hide_index=True, width='stretch', key='sched_main_shift', disabled=['Nhân viên', 'Loại'],
                                    column_config={'username': None, 'Ca chính': st.column_config.SelectboxColumn('Ca chính', options=list(names), required=True)})
            if st.button('Lưu ca chính', key='sched_save_main'):
                for _, r in edited.iterrows():
                    ss.set_main_shift(r['username'], names[r['Ca chính']], user_name)
                st.session_state['sched_flash'] = 'Đã lưu ca chính.'
                st.rerun()
        st.divider()
        _busy_form(people, 'admin', by=user_name)
        st.markdown('**Ngày bận sắp tới (4 tuần)**')
        _busy_table(_today(), _today() + timedelta(days=28), 'people')


def _render_collection(start: date):
    """Who has answered the busy-days round for this week; when the AI will draft it."""
    c = ss.cycle()
    rows = ss.responses(start)
    done = [r for r in rows if r['response']]
    missing = [r['full_name'] for r in rows if not r['response']]
    if start == c['target_week']:
        when = (f"Đang hỏi lịch bận — hạn **{c['deadline']:%H:%M %d/%m}**, sau đó Tuyết Vương tự xếp và gửi bản nháp cho bạn duyệt."
                if c['open'] else
                f"Đợt hỏi lịch bận mở từ **{c['opens']:%d/%m}**, hạn **{c['deadline']:%H:%M %d/%m}**." if not c['closed'] else
                'Đã hết hạn báo bận — ai chưa báo được coi là rảnh cả tuần.')
        st.info(f"🗓️ {when}  \n✅ Đã trả lời **{len(done)}/{len(rows)}**" + (f" · chưa trả lời: {', '.join(missing)}" if missing else ''))


def _render_draft(agent, plan, user_role, user_name):
    check = plan['verification']
    with st.container(border=True, key='sched_draft'):
        st.markdown(f"#### 📝 Bản nháp AI xếp · `{plan['plan_id']}` — nhân viên chưa thấy")
        if plan.get('auto'):
            silent = plan['auto'].get('no_answer') or []
            st.caption(f"🤖 Tuyết Vương tự xếp lúc {plan['auto']['at'].replace('T', ' ')} sau hạn báo bận"
                       + (f" · không báo (coi như rảnh): {', '.join(silent)}" if silent else ' · mọi người đều đã trả lời'))
        st.caption('Sửa ô nếu cần (chọn ca cho từng người từng ngày), bấm **Lưu chỉnh sửa**, rồi **Duyệt & gửi**.')
        rows = ss.to_grid(plan['schedule'])
        frame = pd.DataFrame(rows)
        days = [c for c in frame.columns if c not in ('username', 'Nhân viên', 'Loại', 'Ca chính')]
        edited = st.data_editor(frame, hide_index=True, width='stretch', key=f"sched_grid_{plan['plan_id']}",
                                disabled=['Nhân viên', 'Loại', 'Ca chính'],
                                column_config={'username': None, **{d: st.column_config.SelectboxColumn(d, options=list(ss.CELL_OPTIONS), required=True) for d in days}})
        render_week_table(plan['schedule'])
        for v in check['violations']:
            st.error(v)
        if check['warnings']:
            short = [w for w in check['warnings'] if 'thiếu' in w]
            st.warning(f"⚠️ {len(check['warnings'])} lưu ý" + (f" — {len(short)} ca thiếu người" if short else '')
                       + '\n\n' + '\n'.join(f'- {w}' for w in check['warnings'][:12])
                       + (f"\n- … và {len(check['warnings']) - 12} lưu ý khác" if len(check['warnings']) > 12 else ''))
        if check['shifts_per_person']:
            st.caption('Số ca trong tuần: ' + ' · '.join(f'{n}: {c}' for n, c in check['shifts_per_person'].items()))
        c = st.columns([1, 1, 1])
        changed = edited.drop(columns=['username']).to_dict('records') != frame.drop(columns=['username']).to_dict('records')
        if c[0].button('💾 Lưu chỉnh sửa', key='sched_save_grid', disabled=not changed):
            try:
                ss.update_draft(plan['plan_id'], edited.to_dict('records'), user_name)
                st.session_state['sched_flash'] = 'Đã lưu chỉnh sửa.'
            except ValueError as exc:
                st.session_state['sched_flash'] = f'Không lưu được: {exc}'
            st.rerun()
        if c[1].button('✅ Duyệt & gửi cho nhân viên', key='sched_approve', type='primary',
                       disabled=changed or not check['is_valid'], help='Lưu chỉnh sửa trước' if changed else None):
            res = agent.tool_approve_plan(plan['plan_id'], user_role, user_name)
            st.session_state['sched_flash'] = res.get('message', res.get('status'))
            st.rerun()
        if c[2].button('🗑️ Hủy bản nháp', key='sched_reject'):
            from src.engine.plan_service import reject_plan
            reject_plan(plan['plan_id'], user_name, 'Quản lý hủy bản nháp lịch')
            st.rerun()
