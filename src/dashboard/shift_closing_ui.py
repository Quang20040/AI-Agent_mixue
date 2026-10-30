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
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from src.engine.shift_service import (
    SHIFT_DEFINITIONS,
    SHIFT_PHOTOS_DIR,
    delete_shift_report,
    extract_shift_data_from_image,
    get_all_shift_reports,
    get_daily_closing_summary,
    record_ocr_user_edits,
    save_or_update_shift_report,
)


def render_shift_closing_view(user_role: str, user_name: str, is_admin: bool = False):
    """Hiển thị toàn bộ phân hệ Chốt Ca Bằng Ảnh & Đối Soát Doanh Thu."""
    st.subheader("📸 Quản Lý Chốt Ca Bằng Ảnh & Đối Soát Doanh Thu (AI OCR)")
    st.caption("Chi nhánh Mixue 39 Tôn Quang Phiệt · Tiếp nhận ảnh sổ chốt ca bàn giao thực tế và tự động đối soát tổng thu cuối ngày.")

    st.markdown("""
    <div style="background:#fef2f2; border-left:4px solid #ef4444; padding:12px 16px; border-radius:6px; margin-bottom:18px;">
        <div style="font-weight:600; color:#991b1b; margin-bottom:4px;">📋 Quy chế Chốt ca & Bàn giao doanh thu Mixue 39 Tôn Quang Phiệt</div>
        <div style="font-size:13px; color:#7f1d1d; line-height:1.5;">
            • <b>Ca sáng (8h - 13h):</b> Bàn giao tiền mặt quầy, doanh thu chuyển khoản, app Shopee/Grab/Be và két cố định 1,000,000 đ.<br>
            • <b>Ca chiều (13h - 18h):</b> Bàn giao tương tự ca sáng, ghi rõ số tiền mặt chênh lệch (dư/thiếu) nếu có.<br>
            • <b>Ca tối (18h - 23h):</b> Tổng hợp toàn bộ doanh thu trong ngày, trừ các khoản chi phát sinh (ship hàng, sạc hotline) và chốt số cầm tiền mặt.<br>
            • <b>Agent AI:</b> Tự động đọc ảnh sổ chốt ca viết tay hoặc hóa đơn máy POS, tách rõ nguồn chứng từ, kiểm tra chênh lệch và chờ xác nhận.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 1. BỘ CHỌN NGÀY LÀM VIỆC
    col_d1, col_d2 = st.columns([1, 2.5])
    with col_d1:
        default_d = date(2026, 10, 14)
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
                if extracted.get('status') == 'NEEDS_REVIEW':
                    doc_type_map = {
                        'pos_receipt': 'Hóa đơn POS in nhiệt',
                        'handwritten_ledger': 'Sổ chốt ca viết tay',
                        'composite': 'Ảnh ghép / Nhiều chứng từ (POS + Sổ viết tay)',
                        'non_financial': 'Không phải chứng từ tài chính',
                        'unreadable': 'Ảnh không đọc được',
                        'unknown': 'Chưa xác định rõ loại chứng từ',
                    }
                    doc_label = doc_type_map.get(extracted.get('document_type', 'unknown'), 'Chứng từ')
                    count_txt = f" từ {extracted.get('image_count')} ảnh chứng từ" if extracted.get('image_count', 1) > 1 else ""
                    st.info(f'Đã có bản đọc nháp ({doc_label}){count_txt}. Kiểm tra từng ô trước khi lưu; trường trống chưa có nghĩa là 0.')
                    field_labels = {'cash_vnd': 'Tiền mặt', 'cash_diff_vnd': 'Tiền mặt dư/thiếu',
                                    'bank_transfer_vnd': 'Chuyển khoản', 'shopee_food_vnd': 'ShopeeFood',
                                    'grab_food_vnd': 'GrabFood', 'be_food_vnd': 'BeFood / Miniapp',
                                    'petty_cash_kept_vnd': 'Cố định két', 'expenses_vnd': 'Khoản chi',
                                    'total_collected_vnd': 'Tổng thu về', 'pos_revenue_vnd': 'Doanh thu trên POS',
                                    'pos_collected_vnd': 'Thực thu trên POS'}
                    st.write('**Nội dung đọc được — các số chưa chắc vẫn cần bạn xác nhận**')
                    st.dataframe([{'Khoản mục': field_labels.get(name, name),
                                   'Chữ/số trên ảnh': item.get('raw_text') or item.get('evidence') or 'Chưa đọc được',
                                   'Đã xác định (đ)': item.get('normalized_value') if item.get('status') == 'read' else None,
                                   'Trạng thái': 'Cần kiểm tra' if item.get('status') == 'uncertain' else 'Đã đọc' if item.get('status') == 'read' else 'Chưa có số',
                                   'Lý do cần kiểm tra': item.get('review_reason', '')}
                                  for name, item in extracted.get('field_readings', {}).items()], hide_index=True)
                    consistency = extracted.get('consistency', {})
                    if consistency and not consistency.get('is_consistent', True):
                        for disc in consistency.get('discrepancies', []):
                            st.error(f"⚠️ {disc.get('message')}")
                    for warning in extracted.get('warnings', []):
                        st.warning(warning)
                    with st.expander('Xem nội dung đọc được, nguồn chứng từ và lý do cần kiểm tra'):
                        for index, image_result in enumerate(extracted.get('image_results', []), 1):
                            st.markdown(f'**Ảnh {index}**')
                            if image_result.get('status') != 'NEEDS_REVIEW':
                                st.caption('Ảnh này chưa đọc được; các ảnh còn lại vẫn được giữ.')
                            else:
                                st.dataframe([{'Khoản mục': field_labels.get(name, name),
                                               'Chữ/số đọc riêng trên ảnh': item.get('raw_text', ''),
                                               'Lý do cần kiểm tra': item.get('review_reason', '')}
                                              for name, item in image_result.get('field_readings', {}).items()], hide_index=True)
                        regions = extracted.get('regions', {})
                        if regions.get('pos_receipt', {}).get('raw_text'):
                            st.markdown('**Vùng Hóa đơn POS:**')
                            st.text(regions['pos_receipt']['raw_text'])
                        if regions.get('handwritten_ledger', {}).get('raw_text'):
                            st.markdown('**Vùng Sổ viết tay:**')
                            st.text(regions['handwritten_ledger']['raw_text'])
                        if extracted.get('raw_text_extracted'):
                            st.markdown('**Toàn văn trích xuất:**')
                            st.text(extracted.get('raw_text_extracted', ''))
                        st.dataframe([
                            {
                                'Trường': name,
                                'Nguồn': item.get('source', 'unknown'),
                                'Đọc thô': item.get('raw_text', ''),
                                'Giá trị đọc': item.get('value'),
                                'Giá trị chuẩn hóa': item.get('normalized_value'),
                                'Trạng thái': item['status'],
                                'Lý do kiểm tra': item.get('review_reason', ''),
                                'Nội dung trên ảnh': item.get('evidence', ''),
                            }
                            for name, item in extracted.get('field_readings', {}).items()
                        ], hide_index=True)
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

                    confirmed = st.checkbox('Tôi đã đối chiếu ảnh, ngày, ca và toàn bộ số liệu trước khi lưu.')
                    btn_save_shift = st.form_submit_button(
                        "💾 Xác Nhận & Lưu Báo Cáo Chốt Ca",
                        type="primary",
                        use_container_width=True
                    )

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

                        report_id = f"SHIFT_{chosen_d_str.replace('-', '')}_{curr_shift_code}"
                        review_secs = (
                            round(time.time() - st.session_state.ocr_review_started, 1)
                            if st.session_state.get('ocr_review_started') else None
                        )
                        ocr_review_record = record_ocr_user_edits(
                            report_id=report_id,
                            business_date=chosen_d_str,
                            shift_code=curr_shift_code,
                            confirmed_by=st.session_state.get('username', user_name),
                            extracted={**extracted, 'image_sha256': image_digest},
                            confirmed_values=reviewed_values,
                            review_seconds=review_secs,
                        )
                        payload = {
                            "id": report_id,
                            "business_date": chosen_d_str,
                            "shift_code": curr_shift_code,
                            "shift_name": SHIFT_DEFINITIONS.get(curr_shift_code, {}).get("title", curr_shift_code),
                            "cash_vnd": in_cash,
                            "cash_diff_vnd": in_cash_diff,
                            "bank_transfer_vnd": in_bank,
                            "bank_transfer_formula": in_bank_formula,
                            "shopee_food_vnd": in_shopee,
                            "grab_food_vnd": in_grab,
                            "be_food_vnd": in_be,
                            "petty_cash_kept_vnd": in_petty,
                            "expenses_vnd": in_expenses,
                            "total_collected_vnd": in_total,
                            "signed_by": in_signer,
                            "notes": in_notes,
                            "image_path": st.session_state.get("preview_image_path", ""),
                            "status": "APPROVED",
                            "created_by": user_name,
                            "ocr_review": ocr_review_record,
                        }
                        if in_pos_rev is not None:
                            payload["pos_revenue_vnd"] = in_pos_rev
                        if in_pos_coll is not None:
                            payload["pos_collected_vnd"] = in_pos_coll
                            payload["variance_pos_vnd"] = in_total - in_pos_coll
                        ok, msg, _ = save_or_update_shift_report(payload, actor_role=user_role, actor_username=st.session_state.get('username'))
                        if ok:
                            st.success(f"🎉 {msg}")
                            st.rerun()
                        else:
                            st.error(f"⚠️ {msg}")

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
