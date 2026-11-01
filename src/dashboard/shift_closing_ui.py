"""Giao diện Quản lý & Trích xuất Báo Cáo Chốt Ca Bằng Ảnh (Shift Closing UI).

Hỗ trợ:
- Nhân viên tải ảnh chụp sổ giao ca viết tay hoặc hóa đơn POS.
- AI OCR tự động trích xuất các trường, tách rõ nguồn POS vs sổ viết tay, kiểm tra tính nhất quán.
- Giữ giá trị đọc thô, giá trị chuẩn hóa và lý do cần kiểm tra; để trống các ô thiếu/mơ hồ/mâu thuẫn.
- Cho phép chỉnh sửa số liệu trước khi lưu (Human-in-the-Loop) và ghi nhận chỉnh sửa để đánh giá.
- Bảng tổng kết 3 ca và đối soát doanh thu cuối ngày với máy POS.
"""

import hashlib
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from src.dashboard import ocr_components as vocr
from src.engine.shift_service import (
    SHIFT_PHOTOS_DIR,
    delete_shift_report,
    extract_shift_data_from_image,
    get_all_shift_reports,
    get_daily_closing_summary,
    latest_shift_report_date,
)


def render_shift_closing_view(user_role: str, user_name: str, is_admin: bool = False):
    """Hiển thị toàn bộ phân hệ Chốt Ca Bằng Ảnh & Đối Soát Doanh Thu."""
    vocr.install_css()
    st.markdown(
        '<div class="px-page-head" style="margin:2px 0 6px"><span class="px-eyebrow">Trụ cột 1 · Verifiable Vision OCR</span>'
        '<h2 style="margin:2px 0 4px;padding:0;font-size:26px;font-weight:800;color:#1f2430">Chốt ca &amp; Đối soát OCR</h2>'
        '<p style="margin:0;font-size:14px;color:#4b5563">Mô hình chỉ đọc; quy tắc kiểm chứng quyết định số nào được vào biểu mẫu. '
        'Số chưa chắc để trống chờ bạn xác nhận, và chỉ ghi sổ khi Quản lý phê duyệt.</p></div>',
        unsafe_allow_html=True)
    steps_slot = st.empty()

    with st.expander("📋 Quy chế chốt ca & bàn giao doanh thu", expanded=False):
        st.markdown(
            "- **Ca sáng (8h–13h):** bàn giao tiền mặt quầy, chuyển khoản, app Shopee/Grab/Be và két cố định 1.000.000 đ.\n"
            "- **Ca chiều (13h–18h):** như ca sáng, ghi rõ tiền mặt dư/thiếu nếu có.\n"
            "- **Ca tối (18h–23h):** tổng hợp doanh thu cả ngày, trừ khoản chi phát sinh và chốt số cầm tiền mặt.")

    # 1. BỘ CHỌN NGÀY LÀM VIỆC
    col_d1, col_d2 = st.columns([1, 2.5])
    with col_d1:
        default_d = latest_shift_report_date()
        chosen_date = st.date_input(
            "📅 Chọn ngày làm việc cần kiểm tra / chốt ca",
            value=default_d,
            key="shift_chosen_date_picker"
        )
    with col_d2:
        st.write("")
        st.write("")
        st.caption(f"Đang hiển thị dữ liệu sổ chốt ca ngày **{chosen_date.strftime('%d/%m/%Y')}**.")

    chosen_d_str = chosen_date.isoformat()

    # 2. BẢNG THỐNG KÊ TỔNG KẾT NGÀY (KPI CARDS)
    summary = get_daily_closing_summary(chosen_d_str)

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric(
            label="💎 Tổng Thực Thu Về",
            value=f"{summary['total_collected_vnd']:,.0f} đ",
            help="Tổng số tiền thực tế thu về sau khi đã trừ chi phí phát sinh"
        )
    with m2:
        st.metric(
            label="💵 Tiền Mặt Gom Ca",
            value=f"{summary['total_cash_vnd']:,.0f} đ",
            help="Tổng tiền mặt kiểm đếm trong ca (đã để lại két 1 triệu)"
        )
    with m3:
        st.metric(
            label="📱 Chuyển Khoản Ngân Hàng",
            value=f"{summary['total_bank_vnd']:,.0f} đ",
            help="Doanh thu khách thanh toán quét mã QR/chuyển khoản"
        )
    with m4:
        st.metric(
            label="🛵 App Giao Hàng",
            value=f"{summary['total_delivery_apps_vnd']:,.0f} đ",
            help="Tổng doanh thu từ ShopeeFood, GrabFood và BeFood"
        )
    with m5:
        var_pos = summary["variance_pos_vnd"]
        pos_rev = summary["pos_revenue_vnd"]
        st.metric(
            label="🏷️ Đối Soát POS",
            value=f"{pos_rev:,.0f} đ",
            delta=f"{var_pos:+,.0f} đ" if abs(var_pos) > 100 else "Khớp 99.99%",
            delta_color="normal" if abs(var_pos) <= 50000 else "inverse",
            help="So sánh Thực thu sổ chốt với Thực thu máy in POS cuối ngày"
        )

    st.divider()

    # 3. KHU VỰC TẢI ẢNH CHỐT CA & AI OCR EXTRACTOR
    with st.expander("📸 **Tải Ảnh Chốt Ca & Trích Xuất Dữ Liệu Tự Động Bằng AI (OCR)**", expanded=True):
        st.write("##### 📤 Tải ảnh chụp sổ bàn giao hoặc hóa đơn POS")
        st.caption("Hệ thống hỗ trợ ảnh chụp sổ chốt viết tay của nhân viên (Ca sáng, Ca chiều, Ca tối) hoặc hóa đơn in từ máy POS.")

        col_upload, col_result = st.columns([1.1, 1.4], gap="large")

        with col_upload:
            with st.container(border=True):
                st.write("**1. Chọn Ca & Tải Ảnh Lên**")

                def choose_sample(filename, ca):
                    p_str = str(SHIFT_PHOTOS_DIR / filename)
                    st.session_state.preview_image_path = p_str
                    st.session_state.preview_image_paths = [p_str]
                    st.session_state.shift_ocr_selection = next(item for item in shift_options if item[0] == ca)
                    st.session_state.extracted_cache = None

                shift_options = [
                    ("CA_SANG", "🌅 1. Ca sáng bàn giao (8h - 13h)"),
                    ("CA_CHIEU", "☀️ 2. Ca chiều bàn giao (13h - 18h)"),
                    ("CA_TOI", "🌙 3. Ca tối & Chốt tổng cả ngày (18h - 23h)"),
                ]
                selected_shift_type = st.selectbox(
                    "Chọn ca làm việc đang chốt",
                    shift_options,
                    format_func=lambda x: x[1], key='shift_ocr_selection'
                )
                shift_code = selected_shift_type[0]

                st.write("**Hoặc sử dụng ảnh chụp thực tế có sẵn:**")
                btn_c1, btn_c2, btn_c3, btn_c4 = st.columns(4)

                if "preview_image_path" not in st.session_state:
                    st.session_state.preview_image_path = None
                if "preview_image_paths" not in st.session_state:
                    st.session_state.preview_image_paths = []

                with btn_c1:
                    st.button("📷 Sổ Ca Sáng", use_container_width=True, on_click=choose_sample,
                              args=('20261014_ca_sang_chieu.jpg', 'CA_SANG'))

                with btn_c2:
                    st.button("📷 Sổ Ca Chiều", use_container_width=True, on_click=choose_sample,
                              args=('20261014_ca_sang_chieu.jpg', 'CA_CHIEU'))

                with btn_c3:
                    st.button("📷 Sổ Ca Tối", use_container_width=True, on_click=choose_sample,
                              args=('20261014_ca_toi_tong_ket.jpg', 'CA_TOI'))

                with btn_c4:
                    st.button("🧾 Hóa đơn POS", use_container_width=True, on_click=choose_sample,
                              args=('20261014_pos_slip.jpg', 'CA_TOI'))

                uploaded_files = st.file_uploader(
                    "Kéo thả hoặc duyệt ảnh từ thiết bị (có thể chọn nhiều ảnh cùng lúc: Hóa đơn POS, Sổ ca, Phiếu chi...):",
                    type=["jpg", "jpeg", "png", "webp"],
                    accept_multiple_files=True,
                    key="shift_photo_uploader"
                )

                if uploaded_files:
                    saved_paths = []
                    upload_dir = SHIFT_PHOTOS_DIR / 'uploads'
                    upload_dir.mkdir(parents=True, exist_ok=True)
                    has_oversized = False
                    for uf in uploaded_files:
                        contents = uf.getvalue()
                        if len(contents) > 10 * 1024 * 1024:
                            st.error(f"Ảnh '{uf.name}' vượt 10 MB. Hãy chọn ảnh nhỏ hơn.")
                            has_oversized = True
                            continue
                        digest = hashlib.sha256(contents).hexdigest()
                        save_path = upload_dir / (digest + Path(uf.name).suffix.lower())
                        if not save_path.exists():
                            save_path.write_bytes(contents)
                        saved_paths.append(str(save_path))

                    if not has_oversized and saved_paths:
                        if st.session_state.get('preview_image_paths') != saved_paths:
                            st.session_state.preview_image_paths = saved_paths
                            st.session_state.preview_image_path = saved_paths[0]
                            st.session_state.extracted_cache = None

                cur_paths = st.session_state.get("preview_image_paths") or ([st.session_state.get("preview_image_path")] if st.session_state.get("preview_image_path") else [])
                cur_paths = [p for p in cur_paths if p and Path(p).is_file()]

                if len(cur_paths) == 1:
                    p = cur_paths[0]
                    st.image(p, caption=f"Ảnh chốt ca: {Path(p).name}", use_container_width=True)
                elif len(cur_paths) > 1:
                    st.markdown(f"**📸 Đã tải lên {len(cur_paths)} ảnh chứng từ / hóa đơn:**")
                    cols = st.columns(min(len(cur_paths), 3))
                    for idx, p in enumerate(cur_paths):
                        with cols[idx % min(len(cur_paths), 3)]:
                            st.image(p, caption=f"Ảnh #{idx+1}: {Path(p).name}", use_container_width=True)

        with col_result:
            with st.container(border=True):
                st.write("**2. Kết Quả Trích Xuất AI & Xác Nhận Số Liệu**")
                st.caption("AI tách vùng chứng từ (POS vs sổ viết tay), giữ giá trị đọc thô, kiểm tra tính nhất quán và để trống các ô mơ hồ/mâu thuẫn.")

                curr_shift_code = shift_code
                cur_paths = st.session_state.get("preview_image_paths") or ([st.session_state.get("preview_image_path")] if st.session_state.get("preview_image_path") else [])
                cur_paths = [p for p in cur_paths if p and Path(p).is_file()]

                if cur_paths:
                    digests = [hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in cur_paths]
                    image_digest = hashlib.sha256(''.join(digests).encode()).hexdigest()
                else:
                    image_digest = 'none'

                cache_key = ('ocr_per_image_v2', image_digest, curr_shift_code, chosen_d_str, st.session_state.get('username'))
                if st.session_state.get('ocr_cache_key') != cache_key:
                    st.session_state.extracted_cache = None
                    st.session_state.pop('ocr_review_started', None)
                    st.session_state.ocr_cache_key = cache_key

                num_imgs = len(cur_paths)
                btn_ocr_title = f"Đọc {num_imgs} ảnh bằng AI" if num_imgs > 1 else "Đọc ảnh bằng AI"
                st.caption(f"Bấm '{btn_ocr_title}' sẽ gửi ảnh đến nhà cung cấp AI đã cấu hình để phân tích và đối soát. Bạn cũng có thể nhập tay.")

                if st.button(btn_ocr_title, key='run_shift_ocr', disabled=image_digest == 'none'):
                    with st.spinner(f"Đang đọc và đối soát {num_imgs} ảnh chứng từ…" if num_imgs > 1 else 'Đang đọc nội dung ảnh…'):
                        st.session_state.extracted_cache = extract_shift_data_from_image(
                            image_paths=cur_paths if num_imgs > 1 else None,
                            image_path=cur_paths[0] if num_imgs == 1 else None,
                            shift_hint=curr_shift_code,
                            target_date=chosen_d_str,
                        )
                    st.session_state.ocr_review_started = time.time()
                extracted = st.session_state.get('extracted_cache') or {}
                vocr.render_pipeline_steps(extracted, slot=steps_slot)
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
                    st.info('Bản đọc nháp — kiểm tra từng ô trước khi lưu. Ô trống nghĩa là **chưa xác nhận**, không phải 0.')
                    form_values = {name: extracted.get(name) for name in vocr.FIELD_LABELS}
                    vocr.render_field_table(extracted.get('field_readings', {}), form_values)
                    consistency = extracted.get('consistency', {})
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

                with st.form('confirm_shift_report_' + hashlib.sha256(str(cache_key).encode()).hexdigest()[:16]):
                    f_col1, f_col2 = st.columns(2)
                    with f_col1:
                        in_cash = st.number_input(
                            "Tiền mặt thu tại quầy (đ)",
                            value=extracted.get("cash_vnd"),
                            step=10000,
                            format="%d"
                        )
                        in_cash_diff = st.number_input(
                            "Chênh lệch tiền mặt dư/thiếu (đ)",
                            value=extracted.get("cash_diff_vnd"),
                            step=5000,
                            format="%d",
                            help="Nhập dương nếu dư (VD 20000), nhập âm nếu thiếu"
                        )
                        in_bank = st.number_input(
                            "Chuyển khoản ngân hàng (đ)",
                            value=extracted.get("bank_transfer_vnd"),
                            step=10000,
                            format="%d"
                        )
                        in_bank_formula = st.text_input(
                            "Ghi chú công thức CK (nếu có)",
                            value=str(extracted.get("bank_transfer_formula", ""))
                        )
                        in_petty = st.number_input(
                            "Tiền cố định két (đ)",
                            value=extracted.get("petty_cash_kept_vnd"),
                            step=100000,
                            format="%d"
                        )
                        in_pos_rev = st.number_input(
                            "Tổng doanh thu POS (đ, nếu có)",
                            value=extracted.get("pos_revenue_vnd"),
                            step=10000,
                            format="%d"
                        )

                    with f_col2:
                        in_shopee = st.number_input(
                            "ShopeeFood (đ)",
                            value=extracted.get("shopee_food_vnd"),
                            step=5000,
                            format="%d"
                        )
                        in_grab = st.number_input(
                            "GrabFood (đ)",
                            value=extracted.get("grab_food_vnd"),
                            step=5000,
                            format="%d"
                        )
                        in_be = st.number_input(
                            "BeFood (đ)",
                            value=extracted.get("be_food_vnd"),
                            step=5000,
                            format="%d"
                        )
                        in_expenses = st.number_input(
                            "Khoản chi trong ca (đ)",
                            value=extracted.get("expenses_vnd"),
                            step=5000,
                            format="%d",
                            help="Tiền ship sạc pin, ship đơn hoặc mua đá ngoài"
                        )
                        in_signer = st.text_input(
                            "Người ký xác nhận / Giao ca",
                            value=str(extracted.get("signed_by", user_name))
                        )
                        in_pos_coll = st.number_input(
                            "Thực thu POS (đ, nếu có)",
                            value=extracted.get("pos_collected_vnd"),
                            step=10000,
                            format="%d"
                        )

                    in_total = st.number_input(
                        "Tổng thu về thực tế (đ)",
                        value=extracted.get("total_collected_vnd"),
                        step=10000,
                        format="%d"
                    )

                    in_notes = st.text_area(
                        "Ghi chú ca",
                        value=str(extracted.get("notes", ""))
                    )

                    confirmed = st.checkbox('Tôi đã đối chiếu ảnh, ngày, ca và toàn bộ số liệu trước khi gửi.')
                    btn_save_shift = st.form_submit_button(
                        "📨 Gửi phê duyệt lưu báo cáo (LangGraph interrupt)",
                        type="primary",
                        use_container_width=True,
                        disabled=not is_admin,
                        help="Tạo dự thảo DRAFT_OCR_… rồi gọi request_shift_draft_confirmation; chỉ ghi sổ khi Quản lý bấm Phê duyệt.",
                    )
                    if not is_admin:
                        st.caption("🔒 Nhân viên dùng trang này để đọc và đối chiếu ảnh; chỉ Quản lý/Chủ quán gửi phê duyệt và ghi sổ doanh thu.")

                    if btn_save_shift:
                        amounts = [in_cash, in_cash_diff, in_bank, in_shopee, in_grab, in_be, in_petty, in_expenses, in_total]
                        if not confirmed or any(value is None for value in amounts):
                            st.error('Cần điền đầy đủ các ô tiền và xác nhận đã kiểm tra. Nếu thực tế không phát sinh, nhập 0.')
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
                            image_paths=cur_paths,
                            review_seconds=review_secs,
                            user_role=user_role,
                            user_name=user_name,
                            user_id=st.session_state.get('username', user_name),
                        )
                        st.session_state['agent_pending_approval'] = result.get('pending_approval')
                        st.session_state['approval_notice'] = result['text']
                        st.rerun()

    render_page_approval(user_role, user_name, is_admin)
    render_ocr_benchmark_panel()

    st.write("")
    st.write("### 📋 Danh Sách Các Ca Đã Chốt Trong Ngày " + chosen_date.strftime("%d/%m/%Y"))

    day_reports = get_all_shift_reports(chosen_d_str)

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

        st.write("##### 🔍 Kiểm Tra Ảnh Gốc Chốt Ca Từng Nhân Viên")
        detail_cols = st.columns(len(day_reports))
        for idx, rep in enumerate(day_reports):
            with detail_cols[idx]:
                with st.container(border=True):
                    st.markdown(f"**{rep.get('shift_name')}**")
                    st.caption(f"Ký bởi: **{rep.get('signed_by')}** | Thu về: **{rep.get('total_collected_vnd', 0):,.0f} đ**")
                    img_p = rep.get("image_path")
                    if img_p and Path(img_p).exists():
                        st.image(img_p, use_container_width=True)
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

    with st.expander("🧪 Kiểm định & Phân loại lỗi OCR (Error Taxonomy Benchmark)", expanded=False):
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
