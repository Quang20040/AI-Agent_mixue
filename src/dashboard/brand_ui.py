"""Mixue presentation components; business data comes from the existing engines."""
import base64
import json
import unicodedata
from datetime import datetime
from functools import lru_cache
from html import escape
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent

_FALLBACK_SVG = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' width='80' height='80' viewBox='0 0 80 80'>"
    "<rect width='80' height='80' rx='16' fill='%23fff1f2'/>"
    "<text x='50%25' y='54%25' dominant-baseline='middle' text-anchor='middle' font-size='36'>🍦</text>"
    "</svg>"
)


def snow_king_image(size=52, mode="default"):
    """Use the user's authentic Snow King artwork everywhere in the app."""
    mode_class = " mascot-thinking" if mode == "thinking" else ""
    return (f'<span class="snowking-authentic{mode_class}" style="width:{size}px;height:{size}px;" title="Tuyết Vương Mixue">'
            f'<img src="{asset("snow-king-reference.png")}" width="{size}" height="{size}" alt="Tuyết Vương Mixue"></span>')


@lru_cache(maxsize=64)
def asset(name):
    if name in ('snow-king.png', 'chat-avatar.png'):
        name = 'snow-king-reference.png'
    asset_path = HERE / 'assets' / name
    if asset_path.is_file():
        mime = {'.webp': 'image/webp', '.svg': 'image/svg+xml'}.get(asset_path.suffix, 'image/png')
        return f'data:{mime};base64,' + base64.b64encode(asset_path.read_bytes()).decode('ascii')
    return _FALLBACK_SVG


def install_brand():
    css_path = HERE / 'brand.css'
    if css_path.is_file():
        css = css_path.read_text(encoding='utf-8').replace('__MIXUE_BACKGROUND_PATTERN__', asset('brand-pattern.svg')).replace('__MIXUE_LOGIN_SCENE__', asset('login-snow-world-v1.png')).replace('__MIXUE_LOGIN_MOBILE_SCENE__', asset('login-snow-world-mobile-v1.png'))
        st.markdown('<style>' + css + '</style>', unsafe_allow_html=True)
    st.markdown(f'''<div class="brandbar" role="banner"><div class="brandword">
    <img class="brand-logo" src="{asset('snow-king-reference.png')}" alt="Tuyết Vương Mixue"><div><strong>MIXUE</strong>
    <small>ICE CREAM &amp; TEA · BEVERAGEOPS</small></div></div>
    <div class="brand-location"><b>39 Tôn Quang Phiệt</b>Không gian vận hành · Cửa hàng 2132</div></div>''', unsafe_allow_html=True)
    _motion_component()(key='mixue_motion_controller')


def _motion_component():
    """Use the native v2 component runtime for deterministic script execution."""
    import streamlit.components.v2 as components
    scripts = [HERE / 'assets' / 'gsap.min.js', HERE / 'assets' / 'ScrollTrigger.min.js', HERE / 'motion.js']
    # UMD's browser branch writes window.window, a readonly property in ES modules.
    # Use its supported CommonJS branch, then expose only the two library handles.
    javascript = ('export default function() {\nif (!window.gsap) { (function(){var exports = {}, module = {exports}, define;\n'
                  + scripts[0].read_text(encoding='utf-8') + '\n;window.gsap = exports.gsap;\n'
                  + scripts[1].read_text(encoding='utf-8') + '\n;window.ScrollTrigger = exports.ScrollTrigger;\n})(); }\n'
                  + scripts[2].read_text(encoding='utf-8') + '\n}')
    return components.component('mixue_gsap_motion', js=javascript, isolate_styles=False)


def render_brand_hero(login=False):
    subtitle = 'Một chút ngọt ngào. Một ngày thật vui.' if login else 'Cùng Tuyết Vương chăm chút từng món ngon và bắt đầu một ca làm việc thật hứng khởi.'
    st.html(f'''<section class="mixue-stage {'login-stage' if login else ''}" aria-label="Chào mừng đến Mixue">
    <div class="stage-orbit orbit-one"></div><div class="stage-orbit orbit-two"></div><button class="stage-motion-toggle" type="button" aria-pressed="false">Bật chuyển động</button>
    <div class="stage-copy"><span class="stage-eyebrow">ICE CREAM &amp; TEA · SINCE 1997</span>
    <h1><span>Thêm ngọt ngào.</span><br><em>Thêm niềm vui.</em></h1>
    <p>{subtitle}</p><div class="stage-chips"><span>✦ Pha chế chuẩn vị</span><span>♡ Đồng hành mỗi ngày</span></div>
    {'' if login else '<a class="stage-cta" href="#mixue-menu">Khám phá thực đơn <span>↗</span></a>'}
    <div class="stage-foot">MIXUE BEVERAGEOPS <span>39 TÔN QUANG PHIỆT ↗</span></div></div>
    <div class="stage-gallery"><span class="gallery-word" aria-hidden="true">SWEET!</span><div class="stage-sparkles" aria-hidden="true">{''.join(f'<i style="--i:{i}">✦</i>' for i in range(9))}</div>
    <figure class="photo-card photo-main" data-tilt><img src="{asset('ice-cream.png')}" alt="Kem ốc quế Mixue và Tuyết Vương"><figcaption>Kem tươi Mixue <span>01 / SWEET CLASSIC</span></figcaption></figure>
    <figure class="photo-card photo-secondary" data-tilt><img src="{asset('lemonade.png')}" alt="Nước chanh tươi Mixue"><figcaption>Tươi mát mỗi ngày <span>02 / FRESH LEMON</span></figcaption></figure>
    <div class="stage-stamp">MADE WITH<br><b>LOVE ♡</b></div>
    <div class="stage-mascot"><img src="{asset('snow-king-reference.png')}" alt="Linh vật Tuyết Vương"><span>Xin chào,<br><b>mình là Tuyết Vương!</b></span></div>
    </div></section>''')
    st.markdown('<div class="mixue-ribbon" aria-hidden="true"><div>' + '<span>YOU LOVE ME ♡ I LOVE YOU</span><span> MIXUE ICE CREAM &amp; TEA ✦ </span>' * 4 + '</div></div>', unsafe_allow_html=True)


def product_photo(sku, name):
    """Explicit SKU mapping; never substitute a different drink by category."""
    return product_images().get(sku, {}).get('file', 'snow-king-reference.png')


@lru_cache(maxsize=1)
def product_images():
    return json.loads((HERE / 'assets' / 'product-images.json').read_text(encoding='utf-8'))


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold().replace('đ', 'd')) if unicodedata.category(c) != 'Mn')


def menu_group(sku):
    return {'DK': 'Kem', 'TS': 'Trà sữa', 'THQ': 'Trà trái cây', 'ST': 'Sữa trái cây', 'CF': 'Cà phê'}.get(''.join(c for c in sku if c.isalpha()), 'Khác')


def _SwitchToChatTab():
    st.session_state.main_navigation = "💬 Tuyết Vương AI"


def _render_recipe_modal_body(sku, name, variant, price):
    """Render full BOM recipe & SOP details inside the popup modal."""
    price_label = f'{price:,.0f}'.replace(',', '.')
    group_label = variant or menu_group(sku)
    st.markdown(
        f'''<div class="recipe-modal-banner">
        <div class="recipe-modal-title-group">
            {snow_king_image(54)}
            <div>
                <span class="recipe-sku-badge">{escape(sku)} · {escape(group_label)}</span>
                <h3 class="recipe-modal-title">{escape(name)}</h3>
            </div>
        </div>
        <div class="recipe-modal-price">{price_label} đ</div>
        </div>''',
        unsafe_allow_html=True,
    )

    agent = st.session_state.get("operations_agent")
    rec_res = None
    if agent is not None and hasattr(agent, "tool_decode_recipe_or_sticker"):
        try:
            rec_res = agent.tool_decode_recipe_or_sticker(sku)
        except Exception:
            rec_res = None

    if rec_res and rec_res.get("status") == "SUCCESS" and rec_res.get("recipe_lines"):
        lines = rec_res["recipe_lines"]
        rows_html = "".join(
            f"<tr><td><code>{escape(str(r.get('ingredient_id', '')))}</code></td>"
            f"<td><strong>{escape(str(r.get('ingredient_name', '')))}</strong></td>"
            f"<td style='text-align:right;font-weight:700;color:#e60012;'>{r.get('quantity', '')}</td>"
            f"<td>{escape(str(r.get('unit', '')))}</td></tr>"
            for r in lines
        )
        st.markdown(
            f'''<table class="recipe-bom-table">
            <thead><tr><th>Mã NL</th><th>Tên nguyên liệu</th><th style="text-align:right;">Định lượng chuẩn</th><th>Đơn vị</th></tr></thead>
            <tbody>{rows_html}</tbody>
            </table>''',
            unsafe_allow_html=True,
        )
        bar_rule = rec_res.get("standard_bar_rule", "Tuân thủ đúng định lượng muỗng/bơm chuẩn SOP Mixue.")
        st.markdown(
            f'''<div class="recipe-sop-banner">
            💡 <strong>Quy chuẩn Pha chế Quầy Bar (SOP Mixue):</strong> {escape(str(bar_rule))}
            </div>''',
            unsafe_allow_html=True,
        )
    else:
        st.info("Đang đồng bộ định lượng nguyên liệu chi tiết từ sổ tay BOM cửa hàng 2132.")

    c_ask, c_close = st.columns([1.6, 1])
    with c_ask:
        if st.button("💬 Hỏi Tuyết Vương ở màn hình Chat", key=f"modal_ask_{sku}", type="primary", use_container_width=True, on_click=_SwitchToChatTab):
            st.session_state.chat_input_val = f"Công thức {sku}"
            st.rerun()
    with c_close:
        if st.button("Đóng cửa sổ", key=f"modal_close_{sku}", use_container_width=True):
            st.rerun()


if hasattr(st, "dialog"):
    @st.dialog("🧋 Sổ tay Công thức & Định lượng Chuẩn Mixue", width="large")
    def open_recipe_popup(sku, name, variant, price):
        _render_recipe_modal_body(sku, name, variant, price)
elif hasattr(st, "experimental_dialog"):
    @st.experimental_dialog("🧋 Sổ tay Công thức & Định lượng Chuẩn Mixue", width="large")
    def open_recipe_popup(sku, name, variant, price):
        _render_recipe_modal_body(sku, name, variant, price)
else:
    def open_recipe_popup(sku, name, variant, price):
        with st.container(border=True):
            _render_recipe_modal_body(sku, name, variant, price)


def render_home(menu, sales, user_role="STAFF"):
    from src.auth import is_admin_role
    is_admin = is_admin_role(user_role)
    number = lambda value: f'{value:,.0f}'.replace(',', '.')

    render_brand_hero()
    st.caption('Ảnh theo từng món trong thực đơn Mixue · Giá và công thức lấy từ dữ liệu cửa hàng')

    if is_admin and not sales.empty:
        last_day = sales['business_date'].max()
        latest = sales[sales['business_date'] == last_day]
        st.markdown(f'''<div class="statline" role="region" aria-label="Chỉ số nhanh trong ngày">
        <div><small>DOANH THU · {last_day:%d/%m}</small><strong>{number(latest['revenue_vnd'].sum())} đ</strong></div>
        <div><small>SẢN LƯỢNG · {last_day:%d/%m}</small><strong>{number(latest['quantity_sold'].sum())} ly</strong></div>
        <div><small>THỰC ĐƠN</small><strong>{len(menu)} món</strong></div></div>''', unsafe_allow_html=True)
    else:
        # Nhân viên KHÔNG được phép xem Doanh thu và Sản lượng
        st.markdown(f'''<div class="statline" role="region" aria-label="Thông tin vận hành quầy">
        <div><small>QUY MÔ THỰC ĐƠN</small><strong>{len(menu)} món</strong></div>
        <div><small>TIÊU CHUẨN PHA CHẾ</small><strong>SOP Mixue Bar</strong></div>
        <div><small>GIỜ PHỤC VỤ</small><strong>08:00 – 23:00</strong></div></div>''', unsafe_allow_html=True)
    st.markdown('<div class="section-heading" id="mixue-menu"><h2>Món ngon, chuẩn vị.</h2><span>THỰC ĐƠN CỬA HÀNG · Tra cứu công thức từng món ↗</span></div>', unsafe_allow_html=True)

    filter_col1, filter_col2 = st.columns([1.2, 1.8], gap="medium")
    with filter_col1:
        query = st.text_input('Tìm món theo tên hoặc mã', placeholder='Tìm món yêu thích, ví dụ: trà sữa, TS1…', key='menu_search')
    with filter_col2:
        group = st.pills('Nhóm đồ uống', ['Tất cả', 'Kem', 'Trà sữa', 'Trà trái cây', 'Sữa trái cây', 'Cà phê'], default='Tất cả', key='menu_group') or 'Tất cả'

    featured = {'DK1': 0, 'TS1': 1, 'THQ1': 2}
    ordered = sorted(menu, key=lambda m: (featured.get(m[0], 3), m[0].rstrip('0123456789'), int(''.join(c for c in m[0] if c.isdigit()) or '0')))
    filtered = [m for m in ordered if (group == 'Tất cả' or menu_group(m[0]) == group) and normalized(query) in normalized(f'{m[0]} {m[1]}')]

    meta_col1, meta_col2 = st.columns([2, 1])
    with meta_col1:
        st.caption(f'{len(filtered)} món phù hợp')
    if not filtered:
        st.info('Không tìm thấy món. Thử tên khác hoặc chọn Tất cả.')
        return
    pages = (len(filtered) + 5) // 6
    page_key = f'menu_page_{group}_{query}'
    with meta_col2:
        page = st.selectbox('Trang thực đơn', range(1, pages + 1), format_func=lambda n: f'Trang {n} / {pages}', key=page_key, label_visibility='collapsed') if pages > 1 else 1

    for start in range((page - 1) * 6, min(page * 6, len(filtered)), 3):
        columns = st.columns(3, gap="medium")
        for col, (sku, name, variant, price) in zip(columns, filtered[start:min(start + 3, page * 6)]):
            with col:
                theme = 'milk' if sku.startswith('TS') else 'tea' if sku.startswith('THQ') else 'coffee' if sku.startswith('CF') else ''
                price_label = f'{price:,.0f}'.replace(',', '.')
                image_info = product_images().get(sku, {})
                image_note = image_info.get('variant_note', '')
                note_html = f'<span>{escape(image_note)}</span>' if image_note else ''
                st.markdown(f'''<article class="menu-card {theme}" data-tilt><div class="menu-photo"><img src="{asset(product_photo(sku, name))}" alt="{escape(image_info.get('source_name', name))} · Mixue" loading="lazy">{note_html}<i class="product-halo" aria-hidden="true"></i><i class="product-shine" aria-hidden="true"></i></div><div class="menu-copy"><small>{escape(sku)} · {escape(variant or menu_group(sku))}</small>
                <h3 title="{escape(name)}">{escape(name)}</h3><b>{price_label} đ</b><span class="menu-arrow" aria-hidden="true">↗</span></div></article>''', unsafe_allow_html=True)
                if st.button('Xem công thức ↗', key=f'menu_{sku}', use_container_width=True):
                    st.session_state.chat_input_val = f'Công thức {sku}'
                    open_recipe_popup(sku, name, variant, price)


def _apply_login_session(user):
    st.session_state["authenticated"] = True
    st.session_state["user"] = user
    st.session_state["username"] = user["username"]
    st.session_state["user_role"] = user["role"]
    st.session_state["user_name"] = user["name"]
    st.session_state["user_title"] = user["title"]
    st.session_state["user_badge"] = user["badge"]
    st.session_state["must_change_password"] = bool(user.get("must_change_password", False))
    st.session_state["last_activity"] = datetime.now()


def render_force_change_password_screen():
    """Màn hình bắt buộc đổi mật khẩu lần đầu (gồm đúng 6 chữ số) cho nhân viên."""
    from src.auth import change_user_password

    user_name = st.session_state.get("user_name", "Nhân viên")
    username = st.session_state.get("username", "")

    c_pad1, c_card, c_pad2 = st.columns([1, 1.8, 1])
    with c_card:
        st.markdown(
            f'''
            <div style="text-align: center; margin-top: 20px; margin-bottom: 20px;">
                <div style="display:inline-block; padding: 12px; border-radius: 50%; background: #fff1f2; border: 2px solid #fecdd3; margin-bottom: 12px;">
                    {snow_king_image(80)}
                </div>
                <h2 style="color: #e60012; margin: 0 0 6px 0; font-size: 24px; font-weight: 800;">🔐 YÊU CẦU ĐỔI MẬT KHẨU LẦN ĐẦU</h2>
                <p style="color: #475569; font-size: 14px; margin: 0 0 4px 0;">Xin chào <strong>{user_name}</strong> (Tài khoản: <code>{username}</code>)</p>
                <div style="display: inline-block; background: #fee2e2; color: #991b1b; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600;">
                    Chính sách an toàn quầy bar Mixue 39 Tôn Quang Phiệt
                </div>
            </div>
            ''',
            unsafe_allow_html=True
        )

        with st.container(border=True):
            st.warning("⚠️ **Lưu ý bảo mật:** Bạn đang dùng mật khẩu khởi tạo mặc định (`123456`). Để kích hoạt tài khoản làm việc tại quầy, bạn bắt buộc phải thiết lập **mật khẩu cá nhân mới gồm đúng 6 chữ số** (ví dụ: `686868`, `246810`).")

            with st.form("force_change_password_form", clear_on_submit=False):
                old_pass = st.text_input("Mật khẩu hiện tại (Mặc định: 123456)", type="password", value="123456", key="force_old_pass")
                new_pass = st.text_input("Mật khẩu mới (Bắt buộc đúng 6 chữ số)", type="password", placeholder="Nhập 6 số (ví dụ: 686868)", max_chars=6, key="force_new_pass")
                confirm_pass = st.text_input("Xác nhận lại mật khẩu mới", type="password", placeholder="Nhập lại đúng 6 số trên", max_chars=6, key="force_confirm_pass")
                
                submitted = st.form_submit_button("Xác nhận Đổi Mật Khẩu & Vào Hệ Thống 🚀", type="primary", use_container_width=True)

                if submitted:
                    if not new_pass or not confirm_pass:
                        st.error("Vui lòng điền đầy đủ mật khẩu mới và xác nhận lại mật khẩu!")
                    elif new_pass != confirm_pass:
                        st.error("Mật khẩu xác nhận không khớp! Vui lòng kiểm tra lại.")
                    else:
                        ok, msg = change_user_password(username, old_pass, new_pass)
                        if ok:
                            st.session_state["must_change_password"] = False
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        if st.button("🚪 Hủy bỏ & Đăng xuất", key="btn_cancel_change_pass", use_container_width=True):
            for k in ["authenticated", "user", "username", "user_role", "user_name", "user_title", "user_badge", "must_change_password", "main_navigation"]:
                st.session_state.pop(k, None)
            st.rerun()


def render_login_screen():
    """Màn hình đăng nhập nhận diện Mixue Tuyết Vương - Bắt buộc đăng nhập trước khi vào hệ thống."""
    from src.auth import verify_user

    st.markdown('<div class="login-atmosphere" aria-hidden="true"><i>❄</i><i>✦</i><i>❄</i><i>✧</i><i>❄</i><i>✦</i><i>❄</i><i>✧</i></div><button class="stage-motion-toggle login-motion-toggle" type="button" aria-pressed="true">Tạm dừng hiệu ứng</button>', unsafe_allow_html=True)
    with st.container(key="login_shell"):
        st.markdown(
            '''
            <div class="login-welcome"><span>MIXUE · ICE CREAM &amp; TEA</span><h2>Chào mừng trở lại!</h2><p>Đăng nhập để bắt đầu một ca làm ngọt ngào.</p></div>
            ''',
            unsafe_allow_html=True
        )

        with st.container(key="login_card"):
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("Tên đăng nhập", key="login_username", placeholder="Nhập tên đăng nhập của bạn")
                password = st.text_input("Mật khẩu", type="password", key="login_password", placeholder="Nhập mật khẩu")
                submitted = st.form_submit_button("Đăng nhập vào Hệ thống 🚀", type="primary", use_container_width=True)

                if submitted:
                    if not username.strip() or not password.strip():
                        st.warning("⚠️ Vui lòng nhập đầy đủ Tên đăng nhập và Mật khẩu.")
                    else:
                        user = verify_user(username.strip(), password.strip())
                        if user:
                            _apply_login_session(user)
                            st.success(f"Đăng nhập thành công! Xin chào {user['name']}.")
                            st.rerun()
                        else:
                            st.error("Tên đăng nhập hoặc mật khẩu không chính xác! Vui lòng thử lại.")

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        with st.expander("🔑 Tài khoản dùng thử & đăng nhập nhanh", expanded=False):
            st.caption("Bấm chọn tài khoản bên dưới để đăng nhập trực tiếp thử nghiệm theo từng phân quyền:")
            cq1, cq2 = st.columns(2, gap="small")
            with cq1:
                if st.button("👑 Chủ Quán (Admin)\nPass: 123", key="quick_login_owner", use_container_width=True):
                    u = verify_user("chucuahang", "123")
                    if u:
                        _apply_login_session(u)
                        st.rerun()
            with cq2:
                if st.button("🛡️ Quản Lý (Admin)\nPass: 123", key="quick_login_manager", use_container_width=True):
                    u = verify_user("quanly", "123")
                    if u:
                        _apply_login_session(u)
                        st.rerun()

            cq3, cq4 = st.columns(2, gap="small")
            with cq3:
                if st.button("☕ NV Chính Thức\nPass: 123", key="quick_login_staff", use_container_width=True):
                    u = verify_user("nhanvien", "123")
                    if not u:
                        u = verify_user("nhanvien", "123456")
                    if u:
                        _apply_login_session(u)
                        st.rerun()
            with cq4:
                if st.button("🌱 NV Thử Việc (Mới)\nPass: 123456", key="quick_login_staff_probation", use_container_width=True):
                    u = verify_user("nhanvien_moi", "123456")
                    if u:
                        _apply_login_session(u)
                        st.rerun()

            st.markdown("""
            <div style="font-size: 12px; color: #475569; line-height: 1.6; margin-top: 10px; background: #fff5f5; padding: 10px; border-radius: 8px; border: 1px solid #fed7d7;">
                <strong>📋 Chi tiết Phân quyền Hệ thống &amp; Quy định Mật khẩu:</strong><br>
                • <strong>Chủ quán &amp; Quản lý:</strong> Quyền Admin toàn quyền duyệt báo cáo, dự báo, đối soát kho, ký đơn PO và <b>Quản lý nhân viên</b>.<br>
                • <strong>Nhân viên mới/thử việc:</strong> Mật khẩu mặc định là <code>123456</code>. Khi đăng nhập lần đầu <b>bắt buộc đổi sang mã PIN 6 số</b> trước khi vào xem công thức BOM và Chat Tuyết Vương AI.<br>
                • <strong>Reset mật khẩu:</strong> Quản lý có quyền reset mật khẩu nhân viên về lại <code>123456</code> bất cứ lúc nào.
            </div>
            """, unsafe_allow_html=True)


def _render_chat_conversation(agent, role, user_name, history_height=250, key_suffix=""):
    """Shared interactive chat body used by both the Floating Popover and Dedicated Fullscreen Chat Tab."""
    from src.auth import is_admin_role

    clean_role = (role or "STAFF").strip().upper()
    is_admin = is_admin_role(clean_role)

    if 'chat_history_vi' not in st.session_state:
        if is_admin:
            welcome_text = 'Xin chào Quản trị viên! Mình là **Tuyết Vương AI**. Bạn cần xem báo cáo doanh số, dự báo số ly, đối soát kho hay duyệt kế hoạch vận hành?'
        else:
            welcome_text = 'Xin chào! Mình là **Tuyết Vương AI** (Chế độ Nhân viên quầy). Bạn cần tra cứu công thức món nào, quy chuẩn sơ chế topping hay giải mã tem dán ly?'
        st.session_state.chat_history_vi = [{'role': 'assistant', 'content': welcome_text}]

    history = st.container(height=history_height, border=True)
    input_key = f"operations_chat{key_suffix}" if key_suffix else "operations_chat"
    prompt = st.chat_input('Hỏi Tuyết Vương…', key=input_key)
    prompt = st.session_state.pop('chat_input_val', None) or prompt

    avatar_path = HERE / 'assets' / 'snow-king-reference.png'
    assistant_avatar = str(avatar_path) if avatar_path.is_file() else None

    with history:
        for message in st.session_state.chat_history_vi:
            avatar = assistant_avatar if message['role'] == 'assistant' else None
            with st.chat_message(message['role'], avatar=avatar):
                st.markdown(message['content'])
                if message.get('evidence'):
                    with st.expander('Nguồn dữ liệu'):
                        st.write(message['evidence'])
        thinking_slot = st.empty()

    if prompt:
        st.session_state.chat_history_vi.append({'role': 'user', 'content': prompt})
        with history, st.chat_message('user'):
            st.markdown(prompt)
        thinking_slot.markdown(
            f'''<div class="snowking-thinking-card">
            {snow_king_image(42, mode="thinking")}
            <div class="thinking-text-wrap">
                <div class="thinking-title">Tuyết Vương Multi-Agent đang phân tích <span class="thinking-dots"><span></span><span></span><span></span></span></div>
                <div class="thinking-sub">Đang điều phối các Agent lục tìm Repo, Docs, Quy chuẩn và Database…</div>
                <div class="thinking-shimmer"></div>
            </div>
            </div>''',
            unsafe_allow_html=True,
        )
        try:
            response = agent.process_query(
                prompt,
                user_role=clean_role,
                user_name=user_name,
                chat_history=st.session_state.chat_history_vi
            )
            reply_msg = {'role': 'assistant', 'content': response['text'], 'evidence': response.get('evidence_refs', [])}
        except Exception:
            reply_msg = {'role': 'assistant', 'content': 'Mình chưa truy xuất được dữ liệu. Bạn hãy thử lại hoặc kiểm tra kết nối dữ liệu cửa hàng.'}
        st.session_state.chat_history_vi.append(reply_msg)
        thinking_slot.empty()
        with history, st.chat_message('assistant', avatar=assistant_avatar):
            st.markdown(reply_msg['content'])
            if reply_msg.get('evidence'):
                with st.expander('Nguồn dữ liệu'):
                    st.write(reply_msg['evidence'])


def render_chat(agent, role, user_name, mode="auto"):
    """Render Chatbot either as a Dedicated Fullscreen Tab or as a Floating Bottom-Right Popover Button."""
    from src.auth import is_admin_role

    clean_role = (role or "STAFF").strip().upper()
    is_admin = is_admin_role(clean_role)

    current_tab = st.session_state.get("main_navigation", "Trang chủ")
    effective_mode = mode if mode != "auto" else ("fullscreen" if current_tab == "💬 Tuyết Vương AI" else "floating")

    # Phân quyền câu hỏi gợi ý nhanh theo vai trò
    if is_admin:
        quick = [
            ('Dự báo số ly', 'Dự báo doanh số ngày mai'),
            ('Kiểm tra tồn kho', 'Đối soát tồn kho'),
            ('Sơ chế topping', 'Ngày mai nên sơ chế bao nhiêu mẻ topping?'),
            ('Giải mã tem', 'Giải mã mã tem 24101'),
        ]
    else:
        quick = [
            ('Công thức Trà sữa', 'Công thức TS1'),
            ('Sơ chế trân châu', 'Quy trình sơ chế trân châu và hạn dùng'),
            ('Sơ chế thạch đào', 'Cách sơ chế thạch đào và hạn bảo quản'),
            ('Giải mã tem', 'Giải mã mã tem 24101'),
        ]

    def ask_quick(question):
        st.session_state.chat_input_val = question

    def render_quick_questions():
        with st.container(key="chat_quick_questions"):
            st.markdown('<div class="chat-quick-label"><span>⚡ Câu hỏi gợi ý nhanh</span><span>Chạm để hỏi</span></div>', unsafe_allow_html=True)
            for row in (quick[:2], quick[2:]):
                for col, (label, question) in zip(st.columns(2, gap="small"), row):
                    col.button(label, key=f'chat_{label}', use_container_width=True,
                               on_click=ask_quick, args=(question,))

    if effective_mode == "fullscreen":
        with st.container(key="chat_panel_box", border=True):
            role_label = "Quản trị viên" if is_admin else "Nhân viên"
            st.markdown(
                f'''<div class="chat-head">{snow_king_image(42)}
                <div><strong>Tuyết Vương AI</strong><small><span class="chat-online-dot"></span>Đang trực tuyến · {escape(user_name)} ({role_label})</small></div></div>''',
                unsafe_allow_html=True,
            )
            _render_chat_conversation(agent, clean_role, user_name, history_height=430, key_suffix="")
            render_quick_questions()
            if st.button('Bắt đầu cuộc trò chuyện mới', key='clear_chat', use_container_width=True):
                st.session_state.pop('chat_history_vi', None)
                st.rerun()
    else:
        with st.container(key="chat_fab_container"):
            if hasattr(st, "popover"):
                with st.popover("🍦 Chat Tuyết Vương AI"):
                    st.markdown(
                        f'''<div class="chat-head">{snow_king_image(38)}
                        <div><strong>Tuyết Vương AI</strong><small><span class="chat-online-dot"></span>Trợ lý vận hành · Hỏi nhanh tại chỗ</small></div></div>''',
                        unsafe_allow_html=True,
                    )
                    _render_chat_conversation(agent, clean_role, user_name, history_height=240, key_suffix="")
                    render_quick_questions()
                    st.button("⤢ Mở màn hình Chat lớn", key="open_fullscreen_chat", use_container_width=True, on_click=_SwitchToChatTab)
                    if st.button('Xóa lịch sử', key='clear_chat', use_container_width=True):
                        st.session_state.pop('chat_history_vi', None)
                        st.rerun()
            else:
                st.button("🍦 Mở màn hình Chat Tuyết Vương AI", key="fab_open_chat_tab", type="primary", on_click=_SwitchToChatTab)
