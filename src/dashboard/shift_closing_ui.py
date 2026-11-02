"""Giao diện Quản lý & Trích xuất Báo Cáo Chốt Ca Bằng Ảnh (Shift Closing UI).

Hỗ trợ:
- Nhân viên tải ảnh chụp sổ giao ca viết tay hoặc hóa đơn POS.
- AI OCR tự động trích xuất các trường, tách rõ nguồn POS vs sổ viết tay, kiểm tra tính nhất quán.
- Giữ giá trị đọc thô, giá trị chuẩn hóa và lý do cần kiểm tra; để trống các ô thiếu/mơ hồ/mâu thuẫn.
- Cho phép chỉnh sửa số liệu trước khi lưu (Human-in-the-Loop) và ghi nhận chỉnh sửa để đánh giá.
- Bảng tổng kết 3 ca và đối soát doanh thu cuối ngày với máy POS.
"""

import hashlib
import json
from datetime import date
import time
from pathlib import Path

import pandas as pd

from src.engine.image_upload import UploadError, save_photo, thumbnail

import streamlit as st

from html import escape

from src.auth import normalize_role
from src.dashboard.sales_view import business_today
from src.engine.day_sheet import SHIFT_LABELS
from src.dashboard import ocr_components as vocr
from src.engine.shift_service import (
    SHIFT_PHOTOS_DIR,
    SHIFT_UPLOADS_DIR,
    delete_shift_report,
    extract_shift_data_from_image,
    get_all_shift_reports,
    get_daily_closing_summary,
    latest_shift_report_date,
)


def _workspace_file() -> Path:
    return SHIFT_UPLOADS_DIR / 'workspace.json'


def _load_workspace(username: str) -> dict:
    """Photos a user added per day, kept on disk so a page reload does not lose them."""
    try:
        data = json.loads(_workspace_file().read_text(encoding='utf-8')).get(username, {})
    except (OSError, ValueError):
        return {}
    return {day: [p for p in paths if Path(p).is_file()] for day, paths in data.items()}


def _save_workspace(username: str, images: dict) -> None:
    try:
        path = _workspace_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = {}
        keep = {day: list(paths) for day, paths in sorted(images.items())[-14:] if paths}  # last two weeks
        if data.get(username) != keep:
            data[username] = keep
            tmp = path.with_suffix('.tmp')
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            tmp.replace(path)
    except OSError:
        pass


def _render_shift_chips(approved, read_shifts, shift_code):
    """Where each shift of this day stands, so the user never wonders which shift is done."""
    chips = []
    for code, label in SHIFT_SHORT.items():
        if code in approved:
            state, text = 'ok', 'đã duyệt, đã ghi sổ'
        elif code in read_shifts:
            state, text = 'pos', 'có trong ảnh đã đọc'
        else:
            state, text = 'unk', 'chưa có số'
        current = ' px-shift-current' if code == shift_code else ''
        chips.append(f'<span class="px-shift-chip{current}"><b>{label}</b> <span class="vocr-badge vocr-{state}">{text}</span></span>')
    st.markdown('<div class="px-shift-row" aria-label="Trạng thái các ca trong ngày">' + ''.join(chips) + '</div>',
                unsafe_allow_html=True)


def _render_day_images(day_images, chosen_d_str, chosen_date, shift_code, coverage):
    """Photos of the day, each tagged with the shifts it contains; photos without the selected shift are dimmed."""
    def remove_image(path):
        images = st.session_state['ocr_day_images'].get(chosen_d_str, [])
        if path in images:
            images.remove(path)

    if day_images:
        st.markdown(f'<div class="px-mini-head">Ảnh của ngày {chosen_date:%d/%m/%Y} · {len(day_images)}</div>',
                    unsafe_allow_html=True)
    for idx, p in enumerate(day_images):
        sha = hashlib.sha256(Path(p).read_bytes()).hexdigest()
        info = coverage.get(sha)
        has_shift = info is None or shift_code in info.get('shifts', []) or (
            shift_code == 'CA_TOI' and info.get('has_pos_slip'))
        with st.container(key=f"ocr_img_{'on' if has_shift else 'off'}_{idx}"):
            st.image(thumbnail(p), use_container_width=True)
            if info is None:
                tags = '<span class="vocr-badge vocr-unk">Chưa đọc</span>'
            else:
                tags = ' '.join(f'<span class="vocr-badge {"vocr-ok" if s == shift_code else "vocr-unk"}">'
                                f'{SHIFT_SHORT[s]}</span>' for s in info.get('shifts', []))
                if info.get('has_pos_slip'):
                    tags += ' <span class="vocr-badge vocr-pos">Phiếu POS</span>'
                if not has_shift:
                    tags += f' <small>· không có {SHIFT_SHORT[shift_code]}</small>'
            name_col, rm_col = st.columns([4, 1], vertical_alignment='center')
            name_col.markdown(f'<small>Ảnh {idx + 1} · {escape(Path(p).name[:28])}</small><br>{tags or "—"}',
                              unsafe_allow_html=True)
            rm_col.button('✕', key=f'ocr_rm_{idx}_{sha[:8]}', help='Bỏ ảnh này khỏi ngày',
                          on_click=remove_image, args=(p,))



SHIFT_SHORT = {'CA_SANG': 'Ca sáng', 'CA_CHIEU': 'Ca chiều', 'CA_TOI': 'Ca tối'}


def render_shift_closing_view(user_role: str, user_name: str, is_admin: bool = False):
    """Hiển thị toàn bộ phân hệ Chốt Ca Bằng Ảnh & Đối Soát Doanh Thu."""
    vocr.install_css()
    shift_options = [
        ("CA_SANG", "Ca sáng"),
        ("CA_CHIEU", "Ca chiều"),
        ("CA_TOI", "Ca tối"),
    ]
    if st.session_state.get('shift_ocr_selection') not in shift_options:
        st.session_state.shift_ocr_selection = shift_options[0]
    if 'shift_chosen_date_picker' not in st.session_state:
        st.session_state.shift_chosen_date_picker = business_today()  # realtime: open on today
    if jump := st.session_state.pop('ocr_jump_to_date', None):
        try:
            st.session_state.shift_chosen_date_picker = date.fromisoformat(jump)
        except ValueError:
            pass
    username = st.session_state.get('username', user_name)
    if 'ocr_day_images' not in st.session_state:
        st.session_state.ocr_day_images = _load_workspace(username)

    def choose_sample(filenames, ca):
        # Sample photos go into the day being closed (today by default); a photo from another day is
        # flagged after reading, exactly as a real photo would be.
        day = st.session_state.shift_chosen_date_picker.isoformat()
        day_images = st.session_state.setdefault('ocr_day_images', {}).setdefault(day, [])
        for filename in filenames:
            p_str = str(SHIFT_PHOTOS_DIR / filename)
            if p_str not in day_images:
                day_images.append(p_str)
        if ca:
            st.session_state.shift_ocr_selection = next(item for item in shift_options if item[0] == ca)


    def move_to_day(target_iso):
        """Photo says another day: carry the photos and their reading over and open that day."""
        source = st.session_state.shift_chosen_date_picker.isoformat()
        images = st.session_state.setdefault('ocr_day_images', {})
        moved = images.pop(source, [])
        target = images.setdefault(target_iso, [])
        target.extend(p for p in moved if p not in target)
        for key in ('ocr_day_read', 'ocr_day_reading'):
            bucket = st.session_state.setdefault(key, {})
            if source in bucket:
                bucket[target_iso] = bucket.pop(source)
        st.session_state.shift_chosen_date_picker = date.fromisoformat(target_iso)

    def back_to_today():
        st.session_state.shift_chosen_date_picker = business_today()

    with st.container(key='ocr_page_head'):
        head, date_col, shift_col = st.columns([3.2, 1, 1.5], gap='medium', vertical_alignment='bottom')
        head.markdown(
            '<div class="px-page-head"><span class="px-eyebrow">Trụ cột 1 · Verifiable Vision OCR</span>'
            '<h2>Chốt ca &amp; Đối soát OCR</h2>'
            '<p>Mô hình chỉ đọc; quy tắc kiểm chứng quyết định số nào được vào biểu mẫu. '
            'Một lần đọc lấy số của mọi ca trên ảnh; số chưa chắc được điền gợi ý và tô vàng để bạn kiểm tra.</p></div>',
            unsafe_allow_html=True)
        chosen_date = date_col.date_input("Ngày làm việc", key="shift_chosen_date_picker")
        with shift_col:
            selected_shift_type = st.segmented_control(
                "Chọn ca", shift_options, format_func=lambda x: x[1], key='shift_ocr_selection',
                selection_mode='single', label_visibility='collapsed',
            ) or shift_options[0]
    shift_code = selected_shift_type[0]
    if chosen_date != business_today():
        past, back = st.columns([5, 1.2], vertical_alignment='center')
        past.info(f'Đang xem ngày **{chosen_date:%d/%m/%Y}** (không phải hôm nay). Dữ liệu ngày này để tra cứu hoặc chốt bù.')
        back.button('Về hôm nay', key='ocr_back_today', use_container_width=True, on_click=back_to_today)
    steps_slot = st.empty()

    chosen_d_str = chosen_date.isoformat()

    # 2. BẢNG THỐNG KÊ TỔNG KẾT NGÀY (KPI CARDS)
    summary = get_daily_closing_summary(chosen_d_str)
    var_pos = summary["variance_pos_vnd"]
    money = lambda v: f'{v:,.0f}'.replace(',', '.')
    cards = [
        (f"Tổng thu về · {chosen_date:%d/%m}", f"{money(summary['total_collected_vnd'])} đ", 'Sau khi trừ khoản chi', ''),
        ("Tiền mặt gom ca", f"{money(summary['total_cash_vnd'])} đ", 'Đã để lại két cố định', ''),
        ("Chuyển khoản", f"{money(summary['total_bank_vnd'])} đ", 'QR / chuyển khoản', ''),
        ("App giao hàng", f"{money(summary['total_delivery_apps_vnd'])} đ", 'ShopeeFood · GrabFood · BeFood', ''),
        ("Lệch so với thực thu POS", f"{money(var_pos).replace('-', '−')} đ", f"POS {money(summary['pos_revenue_vnd'])} đ",
         'ok' if abs(var_pos) <= 50000 else 'bad'),
    ] if get_all_shift_reports(chosen_d_str) else [
        (f"Tổng thu về · {chosen_date:%d/%m}", 'Chưa chốt', 'Chưa có ca nào được duyệt', 'muted'),
        ("Tiền mặt gom ca", '—', 'Sau khi chốt ca', 'muted'),
        ("Chuyển khoản", '—', 'Sau khi chốt ca', 'muted'),
        ("App giao hàng", '—', 'Sau khi chốt ca', 'muted'),
        ("Lệch so với thực thu POS", '—', 'Có khi ca tối chốt cùng phiếu POS', 'muted'),
    ]
    st.markdown('<section class="px-kpis" aria-label="Tổng kết ngày">' + ''.join(
        f'<div class="px-kpi"><small>{label}</small><b class="px-num {tone}">{value}</b><span>{note}</span></div>'
        for label, value, note, tone in cards) + '</section>', unsafe_allow_html=True)

    approved = {r.get('shift_code') for r in get_all_shift_reports(chosen_d_str)}
    chips_slot = st.container()  # filled after the reading, so the status is current
    if shift_code in approved:
        st.info(f'{SHIFT_LABELS[shift_code]} ngày {chosen_date:%d/%m/%Y} đã được duyệt và ghi sổ. '
                'Gửi lại sẽ tạo bản cập nhật và vẫn phải được Quản lý phê duyệt.')

    # 3. KHU VỰC TẢI ẢNH CHỐT CA & AI OCR EXTRACTOR
    with st.container(key='ocr_workspace'):
        col_upload, col_result = st.columns([1, 2.1], gap="medium")

        with col_upload:
            with st.container(border=True, key='ocr_image_card'):
                st.markdown('<div class="px-card-title">Ảnh chứng từ</div>', unsafe_allow_html=True)
                day_images = st.session_state.setdefault('ocr_day_images', {}).setdefault(chosen_d_str, [])
                day_images[:] = [p for p in day_images if p and Path(p).is_file()]
                st.session_state.setdefault('ocr_day_reading', {})

                st.markdown(f'<div class="px-mini-head">Ảnh mẫu (chụp ngày {latest_shift_report_date():%d/%m/%Y})</div>', unsafe_allow_html=True)
                samples = [("📷 Sổ Ca Sáng", ['20261014_ca_sang_chieu.jpg'], 'CA_SANG'),
                           ("📷 Sổ Ca Chiều", ['20261014_ca_sang_chieu.jpg'], 'CA_CHIEU'),
                           ("📷 Sổ Ca Tối", ['20261014_ca_toi_tong_ket.jpg'], 'CA_TOI'),
                           ("🧾 Hóa đơn POS", ['20261014_pos_slip.jpg'], 'CA_TOI')]
                for row in (samples[:2], samples[2:]):
                    for column, (label, filenames, ca) in zip(st.columns(2, gap='small'), row):
                        column.button(label, use_container_width=True, on_click=choose_sample, args=(filenames, ca))
                st.button('🗂️ Cả 3 ảnh mẫu của ngày', key='ocr_sample_all', use_container_width=True, on_click=choose_sample,
                          args=(['20261014_ca_sang_chieu.jpg', '20261014_ca_toi_tong_ket.jpg', '20261014_pos_slip.jpg'], None))

                uploaded_files = st.file_uploader(
                    "Thêm ảnh của ngày này (sổ chốt ca, phiếu POS) — một ảnh có thể chứa nhiều ca",
                    type=None,  # any photo the phone offers (HEIC, JPEG, PNG, WebP…); checked by content below
                    accept_multiple_files=True,
                    key="shift_photo_uploader",
                    help="Chọn ảnh bất kỳ từ thư viện hoặc chụp mới; ảnh được tự xoay đúng chiều và nén nhẹ trước khi đọc.",
                )
                if uploaded_files:
                    seen = st.session_state.setdefault('ocr_uploaded_seen', set())
                    SHIFT_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
                    for uf in uploaded_files:
                        contents = uf.getvalue()
                        digest = hashlib.sha256(contents).hexdigest()
                        if (chosen_d_str, digest) in seen:
                            continue  # already added (or removed on purpose) for this day
                        seen.add((chosen_d_str, digest))
                        try:
                            save_path = save_photo(contents, uf.name, SHIFT_UPLOADS_DIR)
                        except UploadError as exc:
                            st.error(str(exc))
                            continue
                        if str(save_path) not in day_images:
                            day_images.append(str(save_path))

                images_slot = st.container()  # filled after the reading below, so tags are current

        with col_result:
            with st.container(border=True, key='ocr_evidence_card'):
                st.markdown('<div class="px-card-title">Bằng chứng từng trường</div>', unsafe_allow_html=True)

                curr_shift_code = shift_code
                cur_paths = list(day_images)
                if cur_paths:
                    digests = [hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in cur_paths]
                    image_digest = hashlib.sha256(''.join(digests).encode()).hexdigest()
                else:
                    image_digest = 'none'
                cache_key = ('ocr_day_v3', image_digest, curr_shift_code, chosen_d_str, st.session_state.get('username'))
                results = st.session_state.setdefault('ocr_shift_results', {})

                def read_shift(shift):
                    return extract_shift_data_from_image(
                        image_paths=cur_paths if len(cur_paths) > 1 else None,
                        image_path=cur_paths[0] if len(cur_paths) == 1 else None,
                        shift_hint=shift, target_date=chosen_d_str)

                num_imgs = len(cur_paths)
                btn_ocr_title = f"Đọc {num_imgs} ảnh bằng AI" if num_imgs > 1 else "Đọc ảnh bằng AI"
                st.caption('Mỗi ảnh chỉ gửi cho AI một lần; một lần đọc lấy số của mọi ca có trong ảnh, '
                           'đổi ca ở trên sẽ hiện số của ca đó mà không đọc lại.')
                if st.button(btn_ocr_title, key='run_shift_ocr', disabled=image_digest == 'none'):
                    with st.spinner(f"Đang đọc {num_imgs} ảnh chứng từ…" if num_imgs > 1 else 'Đang đọc nội dung ảnh…'):
                        results[cache_key] = read_shift(curr_shift_code)
                    if (results[cache_key] or {}).get('status') == 'NEEDS_REVIEW':
                        st.session_state.setdefault('ocr_day_read', {})[chosen_d_str] = image_digest
                    st.session_state.ocr_review_started = time.time()

                elif cache_key not in results and st.session_state.get('ocr_day_read', {}).get(chosen_d_str) == image_digest:
                    # Same photos already read for this day: show the newly selected shift from that reading.
                    results[cache_key] = read_shift(curr_shift_code)
                st.session_state.extracted_cache = results.get(cache_key)
                current_sheet = (st.session_state.extracted_cache or {}).get('day_sheet')
                if current_sheet:
                    st.session_state['ocr_day_reading'][chosen_d_str] = current_sheet
                # Evidence attached to this shift's report: only photos that contain this shift.
                sheet_imgs = {img['sha256']: img for img in (current_sheet or {}).get('images', [])}
                shift_paths = [p for p, d in zip(cur_paths, digests if cur_paths else [])
                               if (img := sheet_imgs.get(d)) is None or curr_shift_code in img['shifts']
                               or (curr_shift_code == 'CA_TOI' and img.get('has_pos_slip'))]
                with chips_slot:
                    _render_shift_chips(approved, set(((st.session_state.get('ocr_day_reading') or {}).get(chosen_d_str) or {})
                                                      .get('detected_shifts', [])), shift_code)
                with images_slot:
                    day_cover = (st.session_state.get('ocr_day_reading') or {}).get(chosen_d_str) or {}
                    _render_day_images(day_images, chosen_d_str, chosen_date, shift_code,
                                       {img['sha256']: img for img in day_cover.get('images', [])})
                extracted = st.session_state.get('extracted_cache') or {}
                vocr.render_pipeline_steps(extracted, slot=steps_slot)
                photo_date = extracted.get('document_date')
                if extracted.get('status') == 'NEEDS_REVIEW' and photo_date and photo_date != chosen_d_str:
                    warn, move = st.columns([3.2, 1.3], vertical_alignment='center')
                    warn.error(f'Ảnh ghi ngày **{date.fromisoformat(photo_date):%d/%m/%Y}** nhưng bạn đang chốt ngày '
                               f'**{chosen_date:%d/%m/%Y}**. Kiểm tra lại ảnh, hoặc chuyển sang đúng ngày trên ảnh.')
                    move.button(f'Chốt cho ngày {date.fromisoformat(photo_date):%d/%m}', key='ocr_move_day',
                                use_container_width=True, on_click=move_to_day, args=(photo_date,))
                sheet_info = extracted.get('day_sheet') or {}
                if extracted.get('status') == 'NEEDS_REVIEW' and sheet_info and not sheet_info.get('shift_present', True):
                    found = ', '.join(SHIFT_SHORT[x] for x in sheet_info.get('detected_shifts', [])) or 'không có ca nào'
                    st.warning(f'Các ảnh của ngày này chưa có mục **{SHIFT_SHORT[shift_code]}** (ảnh đang có: {found}). '
                               'Thêm ảnh có ca này, hoặc nhập tay.')
                if extracted.get('status') == 'NEEDS_REVIEW':
                    count_txt = f" · {extracted.get('image_count')} ảnh" if extracted.get('image_count', 1) > 1 else ""
                    st.markdown(f"**Loại chứng từ:** {vocr.document_badge(extracted.get('document_type'))}{count_txt}",
                                unsafe_allow_html=True)
                    vocr.render_image_quality(extracted.get('image_quality'))
                    regions = extracted.get('regions', {})
                    present = [vocr.badge(*vocr.DOCUMENT_BADGES[key]) for key in ('pos_receipt', 'handwritten_ledger')
                               if regions.get(key, {}).get('present')]
                    if present:
                        st.markdown('**Vùng phát hiện:** ' + ' '.join(present), unsafe_allow_html=True)
                    st.info('Bản đọc nháp đã điền sẵn vào biểu mẫu. Ô **tô vàng** là số gợi ý cần kiểm tra; ô trống là chưa đọc được, không phải 0.')
                    form_values = {name: extracted.get(name) for name in vocr.FIELD_LABELS}
                    vocr.render_field_table(extracted.get('field_readings', {}), form_values, extracted.get('suggestions'))
                    consistency = extracted.get('consistency', {})
                    cash_note = (consistency.get('shift_check') or {}).get('cash_explanation')
                    if cash_note:
                        st.info('💵 ' + cash_note)
                    if consistency and not consistency.get('is_consistent', True):
                        st.markdown('**⚖️ Đối soát số học (giữ nguyên số đọc, không tự sửa):**')
                        for disc in consistency.get('discrepancies', []):
                            st.error(f"⚠️ {disc.get('message')}")
                    elif consistency:
                        st.success('⚖️ Đối soát số học: các khoản đã đọc khớp nhau.')
                    for warning in extracted.get('warnings', []):
                        if not any(warning == d.get('message') for d in consistency.get('discrepancies', [])):
                            st.warning(warning)
                    with st.expander('Xem chuỗi đọc thô theo từng ảnh và từng vùng chứng từ'):
                        for index, image_result in enumerate(extracted.get('image_results', []), 1):
                            st.markdown(f'**Ảnh {index}**')
                            if image_result.get('status') != 'NEEDS_REVIEW':
                                st.caption('Ảnh này chưa đọc được; các ảnh còn lại vẫn được giữ.')
                            else:
                                vocr.render_field_table(image_result.get('field_readings', {}))
                        if regions.get('pos_receipt', {}).get('raw_text'):
                            st.markdown('**🧾 Vùng hóa đơn POS:**')
                            st.text(regions['pos_receipt']['raw_text'])
                        if regions.get('handwritten_ledger', {}).get('raw_text'):
                            st.markdown('**✍️ Vùng sổ viết tay:**')
                            st.text(regions['handwritten_ledger']['raw_text'])
                        if extracted.get('raw_text_extracted'):
                            st.markdown('**Toàn văn trích xuất:**')
                            st.text(extracted.get('raw_text_extracted', ''))
                elif extracted:
                    st.warning(extracted.get('message', 'Chưa đọc được ảnh; hãy nhập số liệu thủ công.'))
                    if extracted.get('attempts'):
                        with st.expander('Chi tiết kỹ thuật', expanded=is_admin):
                            st.code('\n'.join(extracted['attempts']), language=None)
                            st.caption('Nội dung lỗi đầy đủ của nhà cung cấp nằm trong log máy chủ (Render → Logs).')

                suggestions = extracted.get('suggestions') or {}
                # New reading -> new widget keys, so the form shows the new values instead of stale widget state.
                form_tag = hashlib.sha256(f"{cache_key}|{extracted.get('extracted_at')}|{extracted.get('status')}".encode()).hexdigest()[:10]

                def prefill(name):
                    """Verified value if read; otherwise the highlighted suggestion (checked by staff, approved by a manager)."""
                    value = extracted.get(name)
                    return value if value is not None else (suggestions.get(name) or {}).get('value')

                def field_key(name):
                    return f"ocr_{'sugg' if name in suggestions and extracted.get(name) is None else 'in'}_{name}_{form_tag}"

                if suggestions:
                    st.markdown(
                        '<div class="px-suggest-note"><b>Ô tô vàng là số điền sẵn theo gợi ý</b> (quy đổi số viết tắt ×1.000, '
                        'cộng biểu thức). Đối chiếu với ảnh và sửa nếu sai trước khi gửi.</div>', unsafe_allow_html=True)
                with st.form('confirm_shift_report_' + hashlib.sha256(str(cache_key).encode()).hexdigest()[:16]):
                    f_col1, f_col2 = st.columns(2)
                    with f_col1:
                        in_cash = st.number_input(
                            "Tiền mặt thu tại quầy (đ)",
                            value=prefill("cash_vnd"),
                            key=field_key("cash_vnd"),
                            help=(suggestions.get("cash_vnd") or {}).get("basis") or None,
                            step=10000,
                            format="%d"
                        )
                        in_cash_diff = st.number_input(
                            "Chênh lệch tiền mặt dư/thiếu (đ)",
                            value=prefill("cash_diff_vnd"),
                            key=field_key("cash_diff_vnd"),
                            help=((suggestions.get("cash_diff_vnd") or {}).get("basis") or "")
                            + " Tiền mặt ở trên là số thực nhận; dư nhập dương, thiếu nhập âm. Tiền mặt đáng lẽ = thực nhận − dư.",
                            step=5000,
                            format="%d"
                        )
                        in_bank = st.number_input(
                            "Chuyển khoản ngân hàng (đ)",
                            value=prefill("bank_transfer_vnd"),
                            key=field_key("bank_transfer_vnd"),
                            help=(suggestions.get("bank_transfer_vnd") or {}).get("basis") or None,
                            step=10000,
                            format="%d"
                        )
                        in_bank_formula = st.text_input(
                            "Ghi chú công thức CK (nếu có)",
                            value=str(extracted.get("bank_transfer_formula", ""))
                        )
                        in_petty = st.number_input(
                            "Tiền cố định két (đ)",
                            value=prefill("petty_cash_kept_vnd"),
                            key=field_key("petty_cash_kept_vnd"),
                            help=(suggestions.get("petty_cash_kept_vnd") or {}).get("basis") or None,
                            step=100000,
                            format="%d"
                        )
                        in_pos_rev = st.number_input(
                            "Tổng doanh thu POS (đ, nếu có)",
                            value=prefill("pos_revenue_vnd"),
                            key=field_key("pos_revenue_vnd"),
                            help=(suggestions.get("pos_revenue_vnd") or {}).get("basis") or None,
                            step=10000,
                            format="%d"
                        )

                    with f_col2:
                        in_shopee = st.number_input(
                            "ShopeeFood (đ)",
                            value=prefill("shopee_food_vnd"),
                            key=field_key("shopee_food_vnd"),
                            help=(suggestions.get("shopee_food_vnd") or {}).get("basis") or None,
                            step=5000,
                            format="%d"
                        )
                        in_grab = st.number_input(
                            "GrabFood (đ)",
                            value=prefill("grab_food_vnd"),
                            key=field_key("grab_food_vnd"),
                            help=(suggestions.get("grab_food_vnd") or {}).get("basis") or None,
                            step=5000,
                            format="%d"
                        )
                        in_be = st.number_input(
                            "BeFood (đ)",
                            value=prefill("be_food_vnd"),
                            key=field_key("be_food_vnd"),
                            help=(suggestions.get("be_food_vnd") or {}).get("basis") or None,
                            step=5000,
                            format="%d"
                        )
                        in_expenses = st.number_input(
                            "Khoản chi trong ca (đ)",
                            value=prefill("expenses_vnd"),
                            key=field_key("expenses_vnd"),
                            help=(suggestions.get("expenses_vnd") or {}).get("basis") or "Tiền ship sạc pin, ship đơn hoặc mua đá ngoài",
                            step=5000,
                            format="%d"
                        )
                        in_signer = st.text_input(
                            "Người ký xác nhận / Giao ca",
                            value=str(extracted.get("signed_by", user_name))
                        )
                        in_pos_coll = st.number_input(
                            "Thực thu POS (đ, nếu có)",
                            value=prefill("pos_collected_vnd"),
                            key=field_key("pos_collected_vnd"),
                            help=(suggestions.get("pos_collected_vnd") or {}).get("basis") or None,
                            step=10000,
                            format="%d"
                        )

                    in_total = st.number_input(
                        "Tổng thu về thực tế (đ)",
                        value=prefill("total_collected_vnd"),
                        key=field_key("total_collected_vnd"),
                        help=(suggestions.get("total_collected_vnd") or {}).get("basis") or None,
                        step=10000,
                        format="%d"
                    )

                    in_notes = st.text_area(
                        "Ghi chú ca",
                        value=str(extracted.get("notes", ""))
                    )

                    confirmed = st.checkbox('Tôi đã đối chiếu ảnh, ngày, ca và toàn bộ số liệu trước khi gửi.')
                    suggested_open = [n for n in suggestions if extracted.get(n) is None]
                    checked_suggestions = (st.checkbox(f'Tôi đã kiểm tra {len(suggested_open)} ô tô vàng (số điền sẵn theo gợi ý).',
                                                       key=f'ocr_checksugg_{form_tag}')
                                           if suggested_open else True)
                    can_submit = is_admin or normalize_role(user_role) == 'STAFF_OFFICIAL'
                    btn_save_shift = st.form_submit_button(
                        "📨 Gửi phê duyệt lưu báo cáo (LangGraph interrupt)" if is_admin else "📨 Gửi Quản lý duyệt",
                        type="primary",
                        use_container_width=True,
                        disabled=not can_submit,
                        help=("Tạo dự thảo DRAFT_OCR_… rồi gọi request_shift_draft_confirmation; chỉ ghi sổ khi Quản lý bấm Phê duyệt."
                              if is_admin else "Gửi bản đã kiểm tra cho Quản lý; chỉ ghi sổ khi Quản lý phê duyệt."),
                    )
                    if not is_admin:
                        st.caption("Nhân viên kiểm tra số điền sẵn rồi gửi; Quản lý/Chủ quán xem lại và phê duyệt mới ghi sổ doanh thu.")

                    if btn_save_shift:
                        amounts = [in_cash, in_cash_diff, in_bank, in_shopee, in_grab, in_be, in_petty, in_expenses, in_total]
                        if not confirmed or not checked_suggestions or any(value is None for value in amounts):
                            st.error('Cần điền đầy đủ các ô tiền, kiểm tra các ô tô vàng và tick xác nhận. Nếu thực tế không phát sinh, nhập 0.')
                            return
                        if any(value < 0 for value in [in_cash, in_bank, in_shopee, in_grab, in_be, in_petty, in_expenses, in_total]):
                            st.error('Số tiền phải không âm, ngoại trừ chênh lệch tiền mặt.')
                            return
                        reviewed_values = dict(zip(
                            ['cash_vnd', 'cash_diff_vnd', 'bank_transfer_vnd', 'shopee_food_vnd', 'grab_food_vnd',
                             'be_food_vnd', 'petty_cash_kept_vnd', 'expenses_vnd', 'total_collected_vnd'], amounts))
                        if in_pos_rev is not None:
                            reviewed_values['pos_revenue_vnd'] = in_pos_rev
                        if in_pos_coll is not None:
                            reviewed_values['pos_collected_vnd'] = in_pos_coll

                        review_secs = (
                            round(time.time() - st.session_state.ocr_review_started, 1)
                            if st.session_state.get('ocr_review_started') else None
                        )
                        agent = st.session_state.get('operations_agent')
                        if agent is None:
                            st.error('Chưa khởi tạo được Agent để gửi phê duyệt.')
                            return
                        # One governed write path: same draft -> request_shift_draft_confirmation -> interrupt()
                        # as the chat; nothing is written to shift_reports before a manager approves.
                        result = agent.submit_shift_review_for_approval(
                            extracted={**extracted, 'image_sha256': image_digest},
                            reviewed_values=reviewed_values,
                            report_date=chosen_d_str,
                            shift_code=curr_shift_code,
                            signed_by=in_signer,
                            notes=in_notes,
                            bank_transfer_formula=in_bank_formula,
                            image_paths=shift_paths,
                            review_seconds=review_secs,
                            review_meta={
                                'suggested_fields': suggested_open,
                                'suggestions_edited': [n for n in suggested_open
                                                       if reviewed_values.get(n) != suggestions[n]['value']],
                            },
                            user_role=user_role,
                            user_name=user_name,
                            user_id=st.session_state.get('username', user_name),
                        )
                        st.session_state['agent_pending_approval'] = result.get('pending_approval')
                        st.session_state['approval_notice'] = result['text']
                        st.rerun()

    _save_workspace(username, st.session_state.get('ocr_day_images', {}))
    if is_admin:
        render_staff_submissions(user_role, user_name)
    render_page_approval(user_role, user_name, is_admin)
    render_ocr_benchmark_panel()

    day_reports = get_all_shift_reports(chosen_d_str)
    with st.container(border=True, key='ocr_day_card'):
        render_day_reports(day_reports, chosen_date, is_admin)

    with st.expander("Quy chế chốt ca & bàn giao doanh thu", expanded=False):
        st.markdown(
            "- **Ca sáng (8h–13h):** bàn giao tiền mặt quầy, chuyển khoản, app Shopee/Grab/Be và két cố định 1.000.000 đ.\n"
            "- **Ca chiều (13h–18h):** như ca sáng, ghi rõ tiền mặt dư/thiếu nếu có.\n"
            "- **Ca tối (18h–23h):** tổng hợp doanh thu cả ngày, trừ khoản chi phát sinh và chốt số cầm tiền mặt.")


def render_staff_submissions(user_role: str, user_name: str):
    """Manager inbox: reports staff checked and sent. Opening one starts the LangGraph approval."""
    agent = st.session_state.get('operations_agent')
    if agent is None:
        return
    user_id = st.session_state.get('username', user_name)
    submissions = agent.list_staff_submissions(user_role, user_name, user_id=user_id)
    if not submissions:
        return
    with st.container(border=True, key='ocr_staff_inbox'):
        st.markdown(f'<div class="px-card-title">📥 Nhân viên gửi chờ duyệt · {len(submissions)}</div>', unsafe_allow_html=True)
        for sub in submissions:
            meta = sub.get('meta') or {}
            fields = sub.get('fields') or {}
            total = fields.get('total_collected_vnd')
            edited = meta.get('suggestions_edited') or []
            suggested = meta.get('suggested_fields') or []
            info, action = st.columns([4, 1.2], vertical_alignment='center')
            info.markdown(
                f"**{sub.get('shift_code') or '—'} · {sub.get('business_date') or '—'}** — gửi bởi "
                f"{meta.get('submitted_by_name') or sub.get('user_id')} · tổng thu "
                f"{'{:,.0f} đ'.format(total).replace(',', '.') if total is not None else '—'}  \n"
                f"<small>{sub['draft_id']} · {len(suggested)} ô điền theo gợi ý"
                f"{f', nhân viên đã sửa {len(edited)} ô' if edited else ''}</small>", unsafe_allow_html=True)
            if action.button('Mở & duyệt', key=f"open_sub_{sub['draft_id']}", type='primary', use_container_width=True):
                result = agent.open_staff_submission(sub['draft_id'], user_role, user_name, user_id=user_id)
                st.session_state['agent_pending_approval'] = result.get('pending_approval')
                st.session_state['approval_notice'] = result.get('text')
                st.rerun()


def render_day_reports(day_reports, chosen_date, is_admin):
    """Approved shifts of the chosen day, with the original evidence photos on demand."""
    st.markdown(f'<div class="px-card-title">Các ca trong ngày {chosen_date:%d/%m/%Y}</div>', unsafe_allow_html=True)

    if not day_reports:
        st.info(f"Chưa có báo cáo ca nào được ghi nhận cho ngày **{chosen_date.strftime('%d/%m/%Y')}**. Hãy tải ảnh và lưu ca đầu tiên ở trên!")
    else:
        table_rows = []
        for r in day_reports:
            diff_str = f" (+{r.get('cash_diff_vnd')/1000:.0f}k)" if r.get('cash_diff_vnd', 0) > 0 else ""
            table_rows.append({
                "Ca làm việc": r.get("shift_name", r.get("shift_code")),
                "Tiền mặt (đ)": f"{r.get('cash_vnd', 0):,.0f}{diff_str}",
                "Chuyển khoản (đ)": f"{r.get('bank_transfer_vnd', 0):,.0f}" + (f" ({r.get('bank_transfer_formula')})" if r.get('bank_transfer_formula') else ""),
                "Shopee (đ)": f"{r.get('shopee_food_vnd', 0):,.0f}",
                "Grab (đ)": f"{r.get('grab_food_vnd', 0):,.0f}",
                "Be (đ)": f"{r.get('be_food_vnd', 0):,.0f}",
                "Chi phí (đ)": f"{r.get('expenses_vnd', 0):,.0f}",
                "Thực thu về (đ)": f"{r.get('total_collected_vnd', 0):,.0f}",
                "Người ký": r.get("signed_by", "—"),
                "Ảnh sổ chốt": "🖼️ Có ảnh" if r.get("image_path") else "—",
                "Trạng thái": "✅ Đã duyệt"
            })

        df_shifts = pd.DataFrame(table_rows)
        st.dataframe(df_shifts, use_container_width=True, hide_index=True)

        st.caption('Ảnh gốc từng ca (bằng chứng đã lưu cùng báo cáo):')
        detail_cols = st.columns(len(day_reports))
        for idx, rep in enumerate(day_reports):
            with detail_cols[idx]:
                with st.container(border=True):
                    st.markdown(f"**{rep.get('shift_name')}**")
                    st.caption(f"Ký bởi: **{rep.get('signed_by')}** | Thu về: **{rep.get('total_collected_vnd', 0):,.0f} đ**")
                    img_p = rep.get("image_path")
                    if img_p and Path(img_p).exists():
                        st.image(thumbnail(img_p), use_container_width=True)
                    else:
                        st.caption("*(Không có ảnh chứng từ)*")

                    if is_admin:
                        if st.button("🗑️ Xóa ca này", key=f"del_shift_{rep.get('id')}", use_container_width=True):
                            ok, d_msg = delete_shift_report(rep.get('id'), actor_username=st.session_state.get('username'))
                            if ok:
                                st.success(d_msg)
                                st.rerun()
                            else:
                                st.error(d_msg)


@st.cache_data(show_spinner=False)
def _default_benchmark():
    from src.engine.ocr_evaluation import run_ocr_benchmark
    return run_ocr_benchmark("scripted")


def render_ocr_benchmark_panel():
    """Error-taxonomy benchmark: 4 synthetic images or the labelled real store photos."""
    from src.agent.config import AgentSettings
    from src.engine.ocr_evaluation import (
        dataset_image_path,
        load_ocr_dataset,
        make_synthetic_test_images,
        run_dataset_benchmark,
        run_ocr_benchmark,
    )

    with st.container(border=True, key='ocr_benchmark_card'):
        st.markdown('<div class="px-card-title">Kiểm định &amp; phân loại lỗi OCR</div>', unsafe_allow_html=True)
        dataset = st.radio(
            "Bộ dữ liệu kiểm định",
            ["synthetic", "real"],
            format_func=lambda k: {"synthetic": "4 ảnh tổng hợp có đáp án (bản đọc mô phỏng)",
                                   "real": "Ảnh thật của cửa hàng có đáp án (data/ocr_eval)"}[k],
            horizontal=True, key="ocr_benchmark_dataset",
        )
        st.caption("So sánh bản đọc thô (tin thẳng số mô hình trả về) với pipeline có kiểm chứng theo 7 nhóm lỗi. "
                   + ("Ảnh tổng hợp: `printed_pos`, `handwritten_ledger`, `blurry_image`, `composite_multi_doc`."
                      if dataset == "synthetic" else
                      "Ảnh thật: đáp án lấy từ báo cáo chốt ca đã duyệt. *Phát lại* chấm lại bản đọc đã lưu bằng pipeline hiện tại, không cần mạng."))
        settings = AgentSettings.from_env()
        live_ready = bool(settings.llm_enabled and settings.allow_external_transfer)
        c1, c2 = st.columns(2)
        offline_label = "▶️ Chạy kiểm định (bản đọc mô phỏng)" if dataset == "synthetic" else "▶️ Phát lại bản đọc đã lưu (offline)"
        if c1.button(offline_label, key="run_ocr_benchmark", use_container_width=True):
            st.session_state["ocr_benchmark_report"] = (run_ocr_benchmark("scripted") if dataset == "synthetic"
                                                        else run_dataset_benchmark(mode="replay"))
        if c2.button("🌐 Chạy với mô hình Vision thật", key="run_ocr_benchmark_live", use_container_width=True,
                     disabled=not live_ready,
                     help=None if live_ready else "Cần bật LLM_ENABLED và ALLOW_EXTERNAL_DATA_TRANSFER."):
            with st.spinner("Đang gửi ảnh kiểm định tới mô hình Vision…"):
                st.session_state["ocr_benchmark_report"] = (run_ocr_benchmark("live", settings=settings) if dataset == "synthetic"
                                                            else run_dataset_benchmark(mode="live", settings=settings))
        report = st.session_state.get("ocr_benchmark_report")
        if report is None and dataset == "synthetic":
            report = _default_benchmark()  # deterministic and offline, so the numbers are visible on arrival
        if report:
            st.markdown(f"**Chế độ:** `{report['mode']}`")
            runtime = report.get("runtime") or {}
            if runtime.get("calls"):
                st.caption(f"Mô hình được gọi {runtime['calls']} lần · độ trễ TB {runtime['avg_latency_s']} s · "
                           f"token vào/ra {runtime['input_tokens']:,}/{runtime['output_tokens']:,}")
            if str(report["mode"]).startswith("real"):
                images = {c["case_id"]: dataset_image_path(c["image"]).read_bytes()
                          for c in load_ocr_dataset()["cases"] if dataset_image_path(c["image"]).is_file()}
            else:
                images = make_synthetic_test_images()
            vocr.render_benchmark(report, images=images)


def render_page_approval(user_role: str, user_name: str, is_admin: bool):
    """Show the pending LangGraph interrupt for a shift draft right on the OCR page."""
    from src.dashboard.brand_ui import render_approval_card

    if notice := st.session_state.pop('approval_notice', None):
        st.info(notice)
    agent = st.session_state.get('operations_agent')
    if agent is None:
        return
    history = agent.conversation_history(user_role, user_name, user_id=st.session_state.get('username', user_name))
    pending = history.get('pending_approval')
    st.session_state['agent_pending_approval'] = pending
    if pending and pending.get('plan_type') == 'SHIFT_OCR_DRAFT':
        render_approval_card(agent, pending, (user_role or '').strip().upper(), user_name, is_admin, key_suffix='_page')
