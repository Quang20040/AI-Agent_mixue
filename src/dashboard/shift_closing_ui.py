"""Giao diện Quản lý & Trích xuất Báo Cáo Chốt Ca Bằng Ảnh (Shift Closing UI).

Hỗ trợ:
- Nhân viên tải ảnh chụp sổ giao ca viết tay hoặc hóa đơn POS.
- AI OCR tự động trích xuất các trường: Tiền mặt, Chuyển khoản, Shopee, Grab, BeFood, Chi phí, Tổng thu về, Người ký.
- Cho phép chỉnh sửa số liệu trước khi lưu (Human-in-the-Loop).
- Bảng tổng kết 3 ca và đối soát doanh thu cuối ngày với máy POS.
"""

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
            • <b>Agent AI:</b> Tự động đọc ảnh sổ chốt ca viết tay hoặc hóa đơn máy POS để điền số liệu và đối soát chênh lệch cuối ngày.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 1. BỘ CHỌN NGÀY LÀM VIỆC
    col_d1, col_d2 = st.columns([1, 2.5])
    with col_d1:
        # Mặc định ngày 14/10/2026 (ngày có ảnh chụp thực tế mẫu) hoặc ngày hiện tại
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

                selected_shift_type = st.selectbox(
                    "Chọn ca làm việc đang chốt",
                    [
                        ("CA_SANG", "🌅 1. Ca sáng bàn giao (8h - 13h)"),
                        ("CA_CHIEU", "☀️ 2. Ca chiều bàn giao (13h - 18h)"),
                        ("CA_TOI", "🌙 3. Ca tối & Chốt tổng cả ngày (18h - 23h)"),
                    ],
                    format_func=lambda x: x[1]
                )
                shift_code = selected_shift_type[0]

                # Nút chọn nhanh ảnh mẫu thực tế của quán
                st.write("**Hoặc sử dụng ảnh chụp thực tế có sẵn:**")
                btn_c1, btn_c2, btn_c3 = st.columns(3)
                
                if "preview_image_path" not in st.session_state:
                    st.session_state.preview_image_path = str(SHIFT_PHOTOS_DIR / "20261014_ca_sang_chieu.jpg")

                with btn_c1:
                    if st.button("📷 Sổ Ca Sáng", use_container_width=True):
                        st.session_state.preview_image_path = str(SHIFT_PHOTOS_DIR / "20261014_ca_sang_chieu.jpg")
                        st.session_state.ocr_shift_code = "CA_SANG"
                        st.session_state.extracted_cache = None

                with btn_c2:
                    if st.button("📷 Sổ Ca Chiều", use_container_width=True):
                        st.session_state.preview_image_path = str(SHIFT_PHOTOS_DIR / "20261014_ca_sang_chieu.jpg")
                        st.session_state.ocr_shift_code = "CA_CHIEU"
                        st.session_state.extracted_cache = None

                with btn_c3:
                    if st.button("📷 Sổ Ca Tối", use_container_width=True):
                        st.session_state.preview_image_path = str(SHIFT_PHOTOS_DIR / "20261014_ca_toi_tong_ket.jpg")
                        st.session_state.ocr_shift_code = "CA_TOI"
                        st.session_state.extracted_cache = None

                uploaded_file = st.file_uploader(
                    "Kéo thả hoặc duyệt ảnh từ thiết bị:",
                    type=["jpg", "jpeg", "png"],
                    key="shift_photo_uploader"
                )

                if uploaded_file is not None:
                    # Lưu file tải lên vào thư mục shift_photos
                    save_path = SHIFT_PHOTOS_DIR / f"{chosen_d_str}_{shift_code}_{uploaded_file.name}"
                    with open(save_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    st.session_state.preview_image_path = str(save_path)
                    st.session_state.extracted_cache = None

                # Hiển thị ảnh đang chọn
                img_path = st.session_state.get("preview_image_path")
                if img_path and Path(img_path).exists():
                    st.image(img_path, caption=f"Ảnh chốt ca: {Path(img_path).name}", use_container_width=True)

        with col_result:
            with st.container(border=True):
                st.write("**2. Kết Quả Trích Xuất AI & Xác Nhận Số Liệu**")
                st.caption("AI sẽ phân tích các dòng viết tay và trích xuất thành số liệu có cấu trúc. Bạn có thể chỉnh sửa nếu cần.")

                # Thực hiện trích xuất nếu chưa trích xuất
                curr_shift_code = st.session_state.get("ocr_shift_code", shift_code)
                if st.session_state.get("extracted_cache") is None:
                    with st.spinner("🤖 AI Tuyết Vương đang phân tích và bóc tách dữ liệu từ ảnh..."):
                        extracted = extract_shift_data_from_image(
                            image_path=st.session_state.get("preview_image_path"),
                            shift_hint=curr_shift_code,
                            target_date=chosen_d_str
                        )
                        st.session_state.extracted_cache = extracted
                else:
                    extracted = st.session_state.extracted_cache

                st.success(f"✅ AI đã nhận diện thành công: **{extracted.get('shift_name')}** (Độ tin cậy: **{extracted.get('confidence_score', 0.95)*100:.0f}%**)")

                with st.form("confirm_shift_report_form"):
                    f_col1, f_col2 = st.columns(2)
                    with f_col1:
                        in_cash = st.number_input(
                            "Tiền mặt thu tại quầy (đ)",
                            value=int(extracted.get("cash_vnd", 0)),
                            step=10000,
                            format="%d"
                        )
                        in_cash_diff = st.number_input(
                            "Chênh lệch tiền mặt dư/thiếu (đ)",
                            value=int(extracted.get("cash_diff_vnd", 0)),
                            step=5000,
                            format="%d",
                            help="Nhập dương nếu dư (VD 20000), nhập âm nếu thiếu"
                        )
                        in_bank = st.number_input(
                            "Chuyển khoản ngân hàng (đ)",
                            value=int(extracted.get("bank_transfer_vnd", 0)),
                            step=10000,
                            format="%d"
                        )
                        in_bank_formula = st.text_input(
                            "Ghi chú công thức CK (nếu có)",
                            value=str(extracted.get("bank_transfer_formula", ""))
                        )
                        in_petty = st.number_input(
                            "Tiền cố định két (đ)",
                            value=int(extracted.get("petty_cash_kept_vnd", 1000000)),
                            step=100000,
                            format="%d"
                        )

                    with f_col2:
                        in_shopee = st.number_input(
                            "ShopeeFood (đ)",
                            value=int(extracted.get("shopee_food_vnd", 0)),
                            step=5000,
                            format="%d"
                        )
                        in_grab = st.number_input(
                            "GrabFood (đ)",
                            value=int(extracted.get("grab_food_vnd", 0)),
                            step=5000,
                            format="%d"
                        )
                        in_be = st.number_input(
                            "BeFood (đ)",
                            value=int(extracted.get("be_food_vnd", 0)),
                            step=5000,
                            format="%d"
                        )
                        in_expenses = st.number_input(
                            "Khoản chi trong ca (đ)",
                            value=int(extracted.get("expenses_vnd", 0)),
                            step=5000,
                            format="%d",
                            help="Tiền ship sạc pin, ship đơn hoặc mua đá ngoài"
                        )
                        in_signer = st.text_input(
                            "Người ký xác nhận / Giao ca",
                            value=str(extracted.get("signed_by", user_name))
                        )

                    in_total = st.number_input(
                        "Tổng thu về thực tế (đ)",
                        value=int(extracted.get("total_collected_vnd", 0)),
                        step=10000,
                        format="%d"
                    )

                    in_notes = st.text_area(
                        "Ghi chú ca",
                        value=str(extracted.get("notes", ""))
                    )

                    btn_save_shift = st.form_submit_button(
                        "💾 Xác Nhận & Lưu Báo Cáo Chốt Ca",
                        type="primary",
                        use_container_width=True
                    )

                    if btn_save_shift:
                        payload = {
                            "id": f"SHIFT_{chosen_d_str.replace('-', '')}_{curr_shift_code}",
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
                            "created_by": user_name
                        }
                        ok, msg, _ = save_or_update_shift_report(payload)
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
        # Chuẩn bị bảng so sánh
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

        # Xem chi tiết từng ca kèm ảnh chứng từ
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
                            ok, d_msg = delete_shift_report(rep.get("id"))
                            if ok:
                                st.success(d_msg)
                                st.rerun()
                            else:
                                st.error(d_msg)
