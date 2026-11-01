"""Mixue presentation components; business data comes from the existing engines."""
import base64
import json
import unicodedata
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from html import escape
from pathlib import Path
from src.runtime_settings import demo_enabled
from src.dashboard.sales_view import business_today, daily_window

import streamlit as st

HERE = Path(__file__).resolve().parent


def ui_icon(name):
    """Small local SVG icons: consistent strokes without an external font."""
    aliases = {'📊': 'chart', '🥤': 'cup', '⭐': 'star', '🗓️': 'calendar', '📋': 'recipe', '⏰': 'clock', '📦': 'box'}
    paths = {
        'chart': '<path d="M5 20v-6m7 6V5m7 15V10" stroke-width="3.5"/>',
        'cup': '<path d="M6 9h13l-2 12H8L6 9Zm7 0 2-7M5 9h15"/>',
        'star': '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9L12 3Z"/>',
        'calendar': '<rect x="4" y="5" width="16" height="16" rx="3"/><path d="M8 3v4m8-4v4M4 11h16"/>',
        'store': '<path d="m3 9 2-6h14l2 6M4 10v11h16V10M9 21v-7h6v7M3 9c0 4 5 4 5 0 0 4 8 4 8 0 0 4 5 4 5 0"/>',
        'search': '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
        'bell': '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
        'box': '<path d="m12 3 9 5v10l-9 5-9-5V8l9-5Zm-9 5 9 5 9-5M12 13v10M7.5 5.5l9 5"/>',
        'trend': '<path d="m3 17 6-6 4 4 8-11M15 4h6v6"/>',
        'prep': '<path d="M3 12h18c0 7-3 9-9 9s-9-2-9-9Zm11-3 5-6M6 8l2-3"/>',
        'recipe': '<rect x="5" y="3" width="14" height="19" rx="3"/><path d="M9 8h6m-6 5h6m-6 4h4"/>',
        'users': '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6m2 3a5 5 0 0 1 3 5v2"/>',
        'chat': '<path d="M21 11a9 9 0 0 1-9 9H4l-2 2V11a9 9 0 0 1 19 0Z"/><path d="M7 11h.01m5 0h.01m5 0h.01"/>',
        'clock': '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/>',
        'camera': '<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
        'home': '<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
        'logout': '<path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10"/>',
    }
    path = paths.get(aliases.get(name, name), paths['star'])
    return f'<svg class="mx-icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>'


def navigate_to(page):
    st.session_state.main_navigation = page


def render_mobile_navigation(pages, current):
    st.session_state['mobile_navigation'] = current
    short = {'Trang chủ': '🏠 Trang chủ', 'Báo cáo & kho': '📦 Kho', 'Dự báo': '📈 Dự báo', 'Sơ chế': '🥣 Sơ chế', 'Nhập hàng': '🛒 Nhập hàng', 'Tem & công thức': '📋 Công thức', '👥 Quản lý nhân viên': '👥 Nhân sự', '💬 Tuyết Vương AI': '💬 AI Agent', '📸 Chốt ca & OCR': '📸 OCR'}
    def change_page():
        navigate_to(st.session_state.mobile_navigation)
    with st.container(key='mobile_dock'):
        st.radio('Chuyển trang', pages, format_func=lambda p: short.get(p, p),
                 horizontal=True, label_visibility='collapsed', key='mobile_navigation', on_change=change_page)

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
            f'<img src="{asset("snow-king-cutout.png")}" width="{size}" height="{size}" alt="Tuyết Vương Mixue"></span>')


STATIC_DIR = HERE / 'static'


def static_url(name):
    """URL of a browser-cached copy built by scripts/build_static_assets.py, or None."""
    path = Path(name)
    served = path.with_suffix('.webp') if path.suffix.lower() in {'.png', '.jpg', '.jpeg'} else path
    return f'app/static/{served.as_posix()}' if (STATIC_DIR / served).is_file() else None


@lru_cache(maxsize=64)
def asset(name):
    """Image URL for HTML/CSS. Prefer the static copy (sent once, cached) over inline base64."""
    if name in ('snow-king.png', 'chat-avatar.png'):
        name = 'snow-king-reference.png'
    if url := static_url(name):
        return url
    asset_path = HERE / 'assets' / name
    if asset_path.is_file():
        mime = {'.webp': 'image/webp', '.svg': 'image/svg+xml'}.get(asset_path.suffix, 'image/png')
        return f'data:{mime};base64,' + base64.b64encode(asset_path.read_bytes()).decode('ascii')
    return _FALLBACK_SVG


def install_brand():
    css_path = HERE / 'brand.css'
    if css_path.is_file():
        css = css_path.read_text(encoding='utf-8').replace('__MIXUE_BACKGROUND_PATTERN__', asset('brand-pattern.svg')).replace('__MIXUE_LOGIN_SCENE__', asset('login-snow-world-v1.png')).replace('__MIXUE_LOGIN_MOBILE_SCENE__', asset('login-snow-world-mobile-v1.png'))
        st.html('<style>' + css + '</style>')
    mockup_path = HERE / 'mockup.css'
    if mockup_path.is_file():
        st.html('<style>' + mockup_path.read_text(encoding='utf-8') + '</style>')
    st.html('<style>' + (HERE / 'dashboard.css').read_text(encoding='utf-8') + '</style>')
    # Redesign layer (two thesis pillars first); loaded last so it wins over older rules.
    st.html('<style>' + (HERE / 'pillars.css').read_text(encoding='utf-8') + '</style>')
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


NAV_ICONS = {
    'Trang chủ': '🏠', 'Báo cáo & kho': '📊', 'Dự báo': '📈', 'Sơ chế': '🥣', 'Nhập hàng': '📦',
    'Tem & công thức': '📋', '👥 Quản lý nhân viên': '👥', '💬 Tuyết Vương AI': '💬', '📸 Chốt ca & OCR': '📸',
}
NAV_LABELS = {
    'Báo cáo & kho': 'Báo cáo & sổ kho', 'Tem & công thức': 'Tem ly & công thức', 'Dự báo': 'Dự báo nhu cầu',
    'Sơ chế': 'Sơ chế topping', 'Nhập hàng': 'Đơn nhập hàng', '👥 Quản lý nhân viên': 'Quản lý nhân viên',
    '💬 Tuyết Vương AI': 'Tuyết Vương AI (LangGraph Agent)',
    '📸 Chốt ca & OCR': 'Chốt Ca & Đối Soát OCR (Chữ viết tay & POS)',
}
NAV_GROUP_TITLES = {
    'core': 'TRỤ CỘT AI CỦA ĐỀ TÀI',
    'support': 'CÔNG CỤ PHỤ TRỢ',
    'admin': 'QUẢN TRỊ',
}

PAGE_HEROES = {
    'Trang chủ': ('Xin chào, {name}!', 'Cùng kiểm soát vận hành quán Mixue 2132 hiệu quả hơn mỗi ngày ✨', 'Chất lượng hôm nay\nTạo nên khách hàng ngày mai!'),
    'Báo cáo & kho': ('Báo cáo & quản lý kho', 'Theo dõi tồn kho, duyệt lệnh kho và đối soát doanh thu theo ca', 'Kho gọn gàng,\nVận hành trơn tru!'),
    'Dự báo': ('Dự báo nhu cầu', 'Dự báo số ly bán ra và nhu cầu nguyên liệu cho ngày kế tiếp', 'Dự báo chuẩn,\nNhập hàng đủ!'),
    'Sơ chế': ('Sơ chế topping', 'Lên kế hoạch sơ chế topping theo dự báo, hạn chế hao hụt', 'Sơ chế đúng lượng,\nKhông lãng phí!'),
    'Nhập hàng': ('Nhập hàng & đề xuất', 'Tạo đơn nhập, nhận hàng và theo dõi các yêu cầu chờ duyệt', 'Đủ hàng mỗi ngày,\nKhông lo gián đoạn!'),
    'Tem & công thức': ('Công thức pha chế', 'Tra cứu định lượng nguyên liệu và quy trình pha chế theo món', 'Đúng công thức,\nĐậm vị Mixue!'),
    '👥 Quản lý nhân viên': ('Quản lý nhân sự & phân quyền chi nhánh', 'Quản trị danh sách nhân viên, cấp phát tài khoản mới và quyền reset mật khẩu', 'Chăm chút đội ngũ,\nTạo nên trải nghiệm ngọt ngào!'),
    '💬 Tuyết Vương AI': ('Tuyết Vương AI — LangGraph Agent dựa trên bằng chứng', 'Đồ thị trạng thái 6 node · RBAC máy chủ · tạm dừng interrupt() chờ Quản lý phê duyệt', 'Không có bằng chứng,\nkhông kết luận!'),
    '📸 Chốt ca & OCR': ('Chốt ca & đối soát OCR có kiểm chứng', 'Đọc sổ chốt ca viết tay và hóa đơn POS · gắn cờ trường mơ hồ · đối soát số học chéo', 'Số chưa chắc,\nđể người xác nhận!'),
}


def _initials(name):
    parts = [p for p in (name or '').split() if p]
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) > 1 else (parts[0][:2].upper() if parts else 'NV')


NAV_SVG = {
    'Trang chủ': 'home', '💬 Tuyết Vương AI': 'chat', '📸 Chốt ca & OCR': 'camera', 'Báo cáo & kho': 'chart',
    'Dự báo': 'trend', 'Sơ chế': 'prep', 'Nhập hàng': 'store', 'Tem & công thức': 'recipe', '👥 Quản lý nhân viên': 'users',
}


def nav_label(page):
    """Plain text label; the line icon is drawn by CSS (see nav_group_css) like in the design."""
    return NAV_LABELS.get(page, page)


def _icon_mask(name):
    from urllib.parse import quote
    svg = ui_icon(name).replace('<svg class="mx-icon" ', '<svg xmlns="http://www.w3.org/2000/svg" ').replace('currentColor', '#000')
    return 'url("data:image/svg+xml,' + quote(svg, safe='') + '")'


def nav_group_css(pages):
    """Group headers above the first page of each navigation group (pure CSS, index based)."""
    from src.auth import page_group
    rules, seen = [], set()
    for index, page in enumerate(pages, 1):
        group = page_group(page)
        if group in NAV_GROUP_TITLES and group not in seen:
            seen.add(group)
            title = NAV_GROUP_TITLES[group].replace('"', '')
            rules.append(f'[data-testid="stSidebar"] .st-key-main_navigation [role="radiogroup"] > *:nth-child({index})::before'
                         f'{{content:"{title}";display:block;font-size:11px;font-weight:700;letter-spacing:.06em;'
                         f'color:#6b5560;margin:16px 12px 6px;}}')
    for index, page in enumerate(pages, 1):
        if page in NAV_SVG:
            mask = _icon_mask(NAV_SVG[page])
            rules.append(f'[data-testid="stSidebar"] .st-key-main_navigation [role="radiogroup"] > *:nth-child({index}) p::before'
                         f'{{content:"";display:inline-block;width:18px;height:18px;margin-right:10px;vertical-align:-4px;'
                         f'background:currentColor;-webkit-mask:{mask} center/contain no-repeat;mask:{mask} center/contain no-repeat;}}')
    if rules:
        st.html('<style>' + ''.join(rules) + '</style>')


def render_sidebar_top(user_name='', user_title='', user_badge=''):
    """Brand block: red tile with Tuyết Vương, store name and product name."""
    st.markdown(f'''<div class="px-brand"><span class="px-brand-tile"><img src="{asset('snow-king-cutout.png')}" alt="Tuyết Vương"></span>
    <div><strong>MIXUE 2132</strong><span>39 Tôn Quang Phiệt · BeverageOps AI</span></div></div>''', unsafe_allow_html=True)


def render_sidebar_bottom(user_name='', user_title='', user_badge=''):
    """Signed-in user, pinned under the navigation (logout button follows)."""
    st.markdown(f'''<div class="px-side-user"><span class="px-avatar">{escape(_initials(user_name))}</span>
    <div><strong>{escape(user_name)}</strong><span>{escape(user_title)}</span></div></div>''', unsafe_allow_html=True)


WEEKDAYS_VI = ('Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ nhật')


def shift_of_day(hour):
    return 'Ca sáng' if hour < 13 else 'Ca chiều' if hour < 18 else 'Ca tối'


def render_topbar(user_name, notifications=0, page='Trang chủ'):
    from src.auth import get_allowed_pages
    now = datetime.now(timezone(timedelta(hours=7)))
    bell = f'<span>{notifications}</span>' if notifications else ''
    pages = get_allowed_pages(st.session_state.get('user_role', 'STAFF'))
    commands = ''.join(f'<button type="button" data-command-page="{escape(nav_label(page))}">{escape(nav_label(page))}<span>↗</span></button>' for page in pages)
    from src.auth import CHAT_PAGE, OCR_PAGE
    title = '' if page in (CHAT_PAGE, OCR_PAGE) else NAV_LABELS.get(page, page).split(' (')[0]
    st.markdown(f'''<div class="mx-topbar px-topbar">
    <div class="px-top-title"><small>{WEEKDAYS_VI[now.weekday()]}, {now:%d/%m/%Y} · {shift_of_day(now.hour)}</small>{f'<h1>{escape(title)}</h1>' if title else ''}</div>
    <button class="mx-search" type="button" data-command-open>{ui_icon('search')}<span>Tìm chức năng, món, mã tem…</span><kbd>Ctrl K</kbd></button>
    <button type="button" class="stage-motion-toggle mx-motion" aria-pressed="true" title="Bật hoặc tạm dừng chuyển động">Tạm dừng hiệu ứng</button>
    <span class="mx-bell" title="{notifications} việc chờ duyệt">{ui_icon('bell')}{bell}</span></div>
    <dialog class="mx-command" aria-label="Tìm nhanh chức năng"><div class="mx-command-head"><b>Bạn muốn làm gì?</b><button type="button" data-command-close aria-label="Đóng tìm kiếm">✕</button></div><input type="search" placeholder="Tìm trang, ví dụ: kho, dự báo, công thức…" aria-label="Tìm chức năng"><div class="mx-command-results">{commands}</div><p class="mx-command-empty" hidden>Không tìm thấy chức năng phù hợp.</p><small>Enter để mở · Esc để đóng</small></dialog>''', unsafe_allow_html=True)


def render_page_hero(page, user_name=''):
    title, sub, quote = PAGE_HEROES.get(page, (page, '', ''))
    first = ' '.join((user_name or '').split()[-2:]) if '{name}' in title else ''
    title = title.format(name=first or 'bạn')
    bubble = escape(quote).replace('\n', '<br>')
    st.markdown(f'''<section class="mx-hero" data-scene="{escape(page)}"><div class="mx-hero-copy"><span class="mx-eyebrow">MỖI NGÀY MỘT CHÚT NGỌT NGÀO <i>✦</i></span><h2>{escape(title)}</h2><p>{escape(sub)}</p><span class="mx-hero-status"><i></i> Không gian vận hành cửa hàng 2132</span></div>
    <div class="mx-hero-art" aria-hidden="true"><span class="mx-orbit"></span><span class="mx-orbit second"></span><span class="mx-spark s1">✦</span><span class="mx-spark s2">✧</span><span class="mx-spark s3">♡</span><div class="mx-bubble">“{bubble}”</div><span class="mx-hero-drink" style="background-image:url('{asset('milk-tea.png')}')"></span>{snow_king_image(144)}</div></section>''', unsafe_allow_html=True)


def _delta(cur, prev):
    if not prev:
        return ''
    pct = (cur - prev) / prev * 100
    cls, arrow = ('mx-up', '↑') if pct >= 0 else ('mx-down', '↓')
    return f'<em><span class="{cls}">{arrow} {abs(pct):.0f}%</span> so với hôm qua</em>'


def render_kpi_cards(items):
    """items: list of (icon, label, value, footnote_html)."""
    cards = ''.join(f'<div class="mx-kpi" data-tilt><div class="mx-kpi-ico tone-{i % 4}">{ui_icon(ico)}</div><div><small>{escape(lbl)}</small>'
                    f'<strong>{escape(val)}</strong>{note}</div></div>' for i, (ico, lbl, val, note) in enumerate(items))
    st.markdown(f'<div class="mx-kpis">{cards}</div>', unsafe_allow_html=True)


def render_revenue_chart(sales, days=7):
    daily = daily_window(sales, days=days)
    known = daily[daily['available']]
    top = float(known['revenue'].max()) if not known.empty else 1.0
    top = top or 1.0
    fmt = lambda v: f'{v:,.0f}'.replace(',', '.')
    bars = []
    for day, row in daily.iterrows():
        if not row['available']:
            bars.append(f'<div class="mx-bar mx-bar-missing" aria-label="{day:%d/%m}: Chưa có kết quả"><span>Chưa có</span></div>')
        else:
            bars.append(f'<div class="mx-bar" tabindex="0" aria-label="{day:%d/%m}: {fmt(row.revenue)} đồng"><span class="mx-bar-tip">{fmt(row.revenue)} đ<br>{row.cups:.0f} ly</span><i style="height:{max(row.revenue / top * 85, 2):.0f}%"></i></div>')
    axis = ''.join(f'<span>{day:%d/%m}</span>' for day in daily.index)
    total = f"{fmt(known['revenue'].sum())} <small>đ</small>" if len(known) == days else 'Chưa có kết quả' if known.empty else 'Chưa đủ dữ liệu'
    st.markdown(f'''<div class="mx-card mx-revenue"><div class="mx-card-heading"><h3>{ui_icon('chart')} Doanh thu {days} ngày gần nhất</h3><span class="mx-tag">Đến hôm nay</span></div>
    <div class="mx-revenue-total">{total}</div><p class="mx-caption">{daily.index[0]:%d/%m} – {daily.index[-1]:%d/%m/%Y} · Đã cập nhật {len(known)}/{days} ngày</p>
    <div class="mx-chart">{''.join(bars)}</div><div class="mx-axis">{axis}</div><p class="mx-caption">Ngày chưa nhập dữ liệu hiển thị “Chưa có”, không tính thành 0.</p></div>''', unsafe_allow_html=True)


def page_link(page, label):
    return f'<button class="mx-text-link" type="button" data-command-page="{escape(nav_label(page))}">{escape(label)} <span>↗</span></button>'


PILLARS = (
    ('📸 Chốt ca & OCR', 'pillar_open_ocr', 'TRỤ CỘT 1', '📸 Verifiable Vision OCR',
     'Đọc sổ chốt ca viết tay và hóa đơn POS có kiểm chứng.',
     ['Tách vùng 🧾 POS / ✍️ sổ tay / ảnh ghép', 'Kiểm tra ảnh mờ trước khi tin số',
      'Không tự nhân 1.000 · không tự cộng 962 + 629', 'Gắn cờ uncertain + review_reason',
      'Đối soát số học chéo sổ tay ↔ POS', 'Benchmark 7 nhóm lỗi OCR']),
    ('💬 Tuyết Vương AI', 'pillar_open_chat', 'TRỤ CỘT 2', '💬 Stateful AI Operations Agent',
     'LangGraph + Human-in-the-Loop + RBAC, trả lời dựa trên bằng chứng.',
     ['Đồ thị 6 node: guard · model/offline · authorize · tools · approval', 'interrupt() chờ Quản lý duyệt DRAFT_OCR / PLAN_*',
      'Lưu vết SqliteSaver (checkpoints.sqlite)', 'Chặn ảo giác số liệu: MISSING_EVIDENCE',
      'RBAC phía máy chủ, không tin lời tự nhận', 'Gửi ảnh chốt ca ngay trong khung chat']),
)


@st.cache_data(ttl=600, show_spinner=False)
def _benchmark_headline():
    """Raw vs verified errors on the labelled synthetic set (deterministic, cached)."""
    from src.engine.ocr_evaluation import run_ocr_benchmark
    report = run_ocr_benchmark('scripted')
    return report['raw_summary']['errors_reaching_form'], report['verified_summary']['errors_reaching_form']


def _vnd(value):
    return f'{value:,.0f}'.replace(',', '.')


def _home_state(agent, user_role, user_name):
    """Live numbers for the greeting band and the pillar cards (never invented)."""
    from src.auth import is_admin_role
    from src.engine.plan_service import list_plans
    from src.engine.shift_service import get_all_shift_reports, get_daily_closing_summary, latest_shift_report_date
    state = {'pending_approval': None, 'draft': None, 'plans_waiting': 0, 'stock_waiting': 0}
    if agent is not None:
        try:
            history = agent.conversation_history(user_role, user_name, user_id=st.session_state.get('username', user_name))
            state.update(pending_approval=history.get('pending_approval'), draft=history.get('pending_ocr_draft'))
        except Exception:  # noqa: BLE001 - the home page must render even if the agent store is unavailable
            pass
        rt = agent._runtime()
        state['tools_allowed'] = sum(1 for spec in rt.tools.values() if spec.allowed(user_role))
        state['online'] = bool(getattr(agent, 'is_llm_online', lambda: False)())
    if is_admin_role(user_role):
        from src.engine.daily_stock_service import get_pending_requests
        today = business_today().isoformat()
        # Only plans for today or later still need a decision; older drafts are history.
        state['plans_waiting'] = sum(1 for p in list_plans()
                                     if p.get('status') == 'PENDING_APPROVAL' and str(p.get('target_date', ''))[:10] >= today)
        state['stock_waiting'] = len(get_pending_requests())
    latest = latest_shift_report_date()
    summary = get_daily_closing_summary(latest)
    state.update(latest=latest, reports=len(get_all_shift_reports(latest)), summary=summary)
    state['bench_raw'], state['bench_verified'] = _benchmark_headline()
    return state


def render_home_greeting(agent, user_role, user_name):
    """Compact red band: greeting, what needs the user now, and Tuyết Vương."""
    from src.auth import OCR_PAGE, CHAT_PAGE, can_access_page
    state = _home_state(agent, user_role, user_name)
    st.session_state['_home_state'] = state
    now = datetime.now(timezone(timedelta(hours=7)))
    part = 'buổi sáng' if now.hour < 11 else 'buổi trưa' if now.hour < 14 else 'buổi chiều' if now.hour < 18 else 'buổi tối'
    first = (user_name or 'bạn').split()[-1]
    tasks = []
    if state['pending_approval']:
        tasks.append((CHAT_PAGE, f"Duyệt {state['pending_approval'].get('plan_id', 'yêu cầu')}", 'light'))
    if state['draft']:
        tasks.append((CHAT_PAGE, f"Dự thảo OCR còn {len(state['draft'].get('missing_fields') or [])} trường chờ xác nhận", 'light'))
    if state['plans_waiting']:
        tasks.append((CHAT_PAGE, f"{state['plans_waiting']} kế hoạch sơ chế/nhập hàng chờ duyệt", 'ghost'))
    if state['stock_waiting']:
        tasks.append(('Báo cáo & kho', f"{state['stock_waiting']} lệnh kho chờ duyệt", 'ghost'))
    if can_access_page(user_role, OCR_PAGE):
        tasks.append((OCR_PAGE, 'Chốt ca từ ảnh sổ', 'ghost'))
    count = sum(1 for _, _, tone in tasks if tone == 'light') + state['plans_waiting'] + state['stock_waiting']
    headline = (f'Chào {part}, {first}! Còn {count} việc cần bạn xử lý trước khi chốt ngày.' if count
                else f'Chào {part}, {first}! Mọi phê duyệt đã xong, chỉ còn chốt ca.')
    if state['draft']:
        bubble = f"Dự thảo <b>{escape(state['draft']['draft_id'])}</b> còn số chưa rõ đơn vị — mình để trống chờ bạn xác nhận nhé."
    elif state['pending_approval']:
        bubble = 'Luồng đang dừng ở bước phê duyệt. Bạn xem và bấm <b>Phê duyệt</b> giúp mình nhé.'
    else:
        bubble = 'Hết ca thì chụp sổ chốt ca gửi mình. Số nào chưa chắc mình sẽ để trống cho bạn xác nhận.'
    tasks = tasks[:4]
    if tasks:  # the most urgent task is the white primary action, as in the design
        tasks[0] = (tasks[0][0], tasks[0][1], 'light')
    buttons = ''.join(f'<button type="button" class="px-link {tone}" data-command-page="{escape(nav_label(page))}">{escape(label)}</button>'
                      for page, label, tone in tasks)
    flakes = ''.join(f'<i class="px-flake" style="left:{left}%;top:{top}%">✦</i>'
                     for left, top in ((8, 18), (22, 72), (47, 12), (58, 78), (71, 30), (90, 64)))
    st.markdown(f'''<section class="px-greet" aria-label="Lời chào và việc cần làm">{flakes}
    <div class="px-greet-copy"><span class="px-eyebrow">MIXUE ICE CREAM &amp; TEA · CỬA HÀNG 2132 · {now:%d/%m/%Y}</span>
    <h2>{escape(headline)}</h2><div class="px-greet-tasks">{buttons}</div></div>
    <div class="px-greet-art"><div class="px-bubble">{bubble}</div>
    <img class="px-mascot" src="{asset('snow-king-cutout.png')}" alt="Linh vật Tuyết Vương"></div></section>''', unsafe_allow_html=True)


def render_pillars(user_role):
    """The two technical pillars of the thesis, with live status, first on the home page."""
    from src.auth import get_allowed_pages
    pages = get_allowed_pages(user_role)
    visible = [p for p in PILLARS if p[0] in pages]
    if not visible:
        return
    state = st.session_state.get('_home_state') or {}
    st.markdown('<div class="px-section-head"><h2>2 trụ cột kỹ thuật</h2>'
                '<span>Mọi số liệu ghi sổ đều qua bằng chứng và người phê duyệt</span></div>', unsafe_allow_html=True)
    summary = state.get('summary') or {}
    latest = state.get('latest')
    columns = st.columns(len(visible), gap='medium')
    for column, (page, key, tag, title, lead, bullets) in zip(columns, visible):
        with column, st.container(border=True, key=f'{key}_card'):
            if key == 'pillar_open_ocr':
                icon, heading = ui_icon('camera'), 'Verifiable Vision OCR'
                variance = summary.get('variance_pos_vnd')
                stats = [('Ca đã chốt · ' + (f'{latest:%d/%m}' if latest else '—'), str(state.get('reports', 0)), state.get('reports', 0)),
                         ('Đối soát POS ↔ sổ', f"{variance:+,.0f} đ".replace(',', '.').replace('-', '−') if variance is not None else '—', None),
                         ('Số sai không bị gắn cờ', f"{state.get('bench_raw', '—')} → {state.get('bench_verified', '—')}", None)]
                draft = state.get('draft')
                badge = (f'<span class="px-pill warn">{len(draft.get("missing_fields") or [])} trường chờ xác nhận</span>' if draft
                         else '<span class="px-pill ok">Không có dự thảo treo</span>')
                extra = ('<p>Tách vùng 🧾 POS và ✍️ sổ tay, kiểm tra ảnh mờ, không tự nhân 1.000, không tự cộng '
                         '<code class="px-code">962 + 629</code>, đối soát cộng ngang.</p>')
            else:
                icon, heading = ui_icon('chat'), 'Tuyết Vương AI · LangGraph Agent'
                pending = state.get('pending_approval')
                waiting = (1 if pending else 0) + state.get('plans_waiting', 0)
                stats = [('Phê duyệt đang chờ', str(waiting), waiting),
                         ('Công cụ được phép', str(state.get('tools_allowed', '—')), state.get('tools_allowed')),
                         ('Chế độ', 'AI Online' if state.get('online') else 'Offline', None)]
                badge = ('<span class="px-pill red">⏸ 1 interrupt đang chờ</span>' if pending
                         else '<span class="px-pill slate">Không có interrupt</span>')
                nodes = ['guard', 'model / offline', 'authorize', 'tools', 'approval ⏸' if pending else 'approval']
                chain = '<span class="px-arrow" aria-hidden="true">→</span>'.join(
                    f'<span class="px-node{" stop" if n.endswith("⏸") else ""}">{n}</span>' for n in nodes)
                extra = (f'<div class="px-chain" aria-label="Đồ thị LangGraph">{chain}</div>'
                         '<p>Gửi ảnh chốt ca ngay trong chat, sửa số bằng lời, Quản lý bấm Phê duyệt mới ghi sổ. '
                         'RBAC kiểm tra ở máy chủ, thiếu bằng chứng thì không kết luận.</p>')
            cells = ''.join(
                f'<div class="px-stat"><small>{escape(label)}</small><b' + (f' data-count="{count}"' if isinstance(count, int) else '') + f'>{escape(value)}</b></div>'
                for label, value, count in stats)
            st.markdown(f'''<div class="px-pillar"><div class="px-pillar-head"><span class="px-pillar-icon">{icon}</span>
            <div style="flex:1"><span class="px-eyebrow">{tag}</span><h3>{escape(heading)}</h3></div>{badge}</div>
            <div class="px-stats">{cells}</div>{extra}</div>''', unsafe_allow_html=True)
            label = 'Mở Chốt ca & Đối soát OCR →' if key == 'pillar_open_ocr' else 'Mở Tuyết Vương AI →'
            with st.container(horizontal=True, key=f'{key}_actions'):
                st.button(label, key=key, type='primary', width='content', on_click=navigate_to, args=(page,))
                if key == 'pillar_open_chat':
                    st.button('Xem phê duyệt đang chờ', key='pillar_view_pending', width='content',
                              on_click=navigate_to, args=(page,))


def render_home_kpis(sales, menu):
    """Four figures from the latest business day that has data (never 'today' guesses)."""
    from src.engine.shift_service import get_all_shift_reports
    number = lambda value: f'{value:,.0f}'.replace(',', '.')
    state = st.session_state.get('_home_state') or {}
    cards = []
    if not sales.empty:
        frame = sales.copy()
        frame['business_date'] = frame['business_date'].astype(str).str[:10]
        day = frame['business_date'].max()
        today_rows = frame[frame['business_date'] == day]
        top = today_rows.groupby('sku_name')['quantity_sold'].sum().sort_values(ascending=False)
        label_day = f'{day[8:10]}/{day[5:7]}'
        cards += [(f'Doanh thu POS · {label_day}', f"{number(today_rows['revenue_vnd'].sum())} đ", 'Nguồn: sales_daily', ''),
                  ('Số ly bán ra', f"{number(today_rows['quantity_sold'].sum())} ly",
                   f'{escape(top.index[0])} dẫn đầu · {int(top.iloc[0])} ly' if len(top) else '', '')]
    else:
        cards.append(('Doanh thu POS', 'Chưa có dữ liệu', 'Nhập dữ liệu bán hàng để xem', ''))
    summary, latest = state.get('summary') or {}, state.get('latest')
    if latest and summary.get('total_collected_vnd'):
        reports = get_all_shift_reports(latest)
        signer = next((r.get('signed_by') for r in reversed(reports) if r.get('signed_by')), '')
        variance = summary.get('variance_pos_vnd') or 0
        cards += [(f'Tổng thu sổ chốt ca · {latest:%d/%m}', f"{number(summary['total_collected_vnd'])} đ",
                   'Đã duyệt' + (f' · ký: {escape(signer)}' if signer else ''), ''),
                  ('Lệch so với thực thu POS', f"{number(variance).replace('-', '−')} đ",
                   f"POS {number(summary.get('pos_collected_vnd') or 0)} đ · " + ('trong ngưỡng' if abs(variance) < 50_000 else 'cần kiểm tra'),
                   'ok' if abs(variance) < 50_000 else 'bad')]
    else:
        cards.append(('Thực đơn', f'{len(menu)} món', 'Tra cứu công thức từng món', ''))
    html = ''.join(f'<div class="px-kpi"><small>{escape(label)}</small><b class="px-num {tone}">{escape(value)}</b><span>{note}</span></div>'
                   for label, value, note, tone in cards)
    st.markdown(f'<section class="px-kpis" aria-label="Số liệu ngày gần nhất">{html}</section>', unsafe_allow_html=True)


def render_shortcuts(user_role):
    from src.auth import get_allowed_pages
    pages = get_allowed_pages(user_role)
    features = [('Báo cáo & kho', 'box', 'Sổ kho, doanh thu POS'), ('Dự báo', 'trend', 'Nhu cầu theo thời tiết'),
                ('Sơ chế', 'prep', 'Tối ưu mẻ topping'), ('Nhập hàng', 'store', 'Dự thảo đơn PO'),
                ('Tem & công thức', 'recipe', 'Giải mã tem, BOM')]
    cards = ''.join(f'<button type="button" class="mx-shortcut tone-{i}" data-command-page="{escape(nav_label(page))}"><span class="mx-shortcut-icon">{ui_icon(icon)}</span><span class="mx-shortcut-arrow">↗</span><b>{escape(NAV_LABELS.get(page, page))}</b><small>{desc}</small></button>'
                    for i, (page, icon, desc) in enumerate(features) if page in pages)
    if cards:
        st.markdown(f'<section class="mx-card mx-shortcuts px-card"><div class="px-section-head"><h2>Dữ liệu &amp; công cụ phụ trợ</h2><span>Công cụ tất định cung cấp số liệu cho Agent</span></div><div class="mx-shortcut-grid">{cards}</div></section>', unsafe_allow_html=True)


@st.cache_data(ttl=300, show_spinner=False)
def forecast_snapshot(target_date):
    from src.engine.forecasting import ForecastingEngine
    engine = ForecastingEngine()
    try:
        return engine.forecast_demand(target_date=target_date, model='auto')
    finally:
        engine.close()


def render_home_overview(menu, sales):
    """Read-only overview of actual sales, pending stock requests and D+1 demand."""
    from src.engine.daily_stock_service import get_pending_requests
    requests = get_pending_requests()
    with st.container(key='home_analytics'):
        left, right = st.columns([1.12, 1], gap='medium')
        with left:
            render_revenue_chart(sales)
        with right:
            rows = ''.join(f'<div class="mx-request"><span class="mx-list-icon tone-2">{ui_icon("box")}</span><div><b>{escape(r["ingredient_name"])}</b><small>{escape(r["type_vi"])} · {r["quantity"]:g} · {escape(r["recorded_by"])}</small></div><span class="mx-status">Chờ duyệt</span></div>' for r in requests[:4])
            if not rows:
                rows = '<div class="mx-all-clear"><span>✓</span><b>Mọi yêu cầu đã được xử lý</b><p>Bạn đã sẵn sàng cho một ca làm thật tốt!</p></div>'
            st.markdown(f'<section class="mx-card mx-approvals"><div class="mx-card-heading"><h3>{ui_icon("clock")} Yêu cầu chờ phê duyệt <em>{len(requests)}</em></h3>{page_link("Báo cáo & kho", "Xem tất cả")}</div><p class="mx-caption">Theo dõi các lệnh kho cần bạn xử lý</p>{rows}<div class="mx-approval-foot"><i></i> Chỉ ghi sổ khi được quản lý phê duyệt</div></section>', unsafe_allow_html=True)

    today = business_today()
    latest = max(sales['business_date']) if not sales.empty else None
    target = today + timedelta(days=1)
    forecast = forecast_snapshot(target) if latest == today else sales.iloc[:0]
    top_forecast = forecast.sort_values('predicted_qty', ascending=False).head(3) if not forecast.empty else forecast
    product_rows = ''.join(f'<div class="mx-product-row"><img src="{asset(product_photo(r.sku_id, r.sku_name))}" alt="" loading="lazy"><span>{escape(r.sku_name)}</span><b>{r.predicted_qty:,.0f} <small>ly</small></b></div>' for r in top_forecast.itertuples())
    total_label = f"{forecast['predicted_qty'].sum():,.0f} <small>ly dự kiến</small>" if not forecast.empty else 'Chưa đủ dữ liệu dự báo'
    tops = sales[sales['business_date'] == today].groupby(['sku_id', 'sku_name'])['quantity_sold'].sum().sort_values(ascending=False).head(3)
    best_rows = ''.join(f'<div class="mx-product-row"><span class="mx-rank">{i+1:02}</span><img src="{asset(product_photo(sku, name))}" alt="" loading="lazy"><span>{escape(name)}</span><b>{qty:,.0f} <small>ly</small></b></div>' for i, ((sku, name), qty) in enumerate(tops.items()))
    st.markdown(f'''<div class="mx-summary-grid"><section class="mx-card"><div class="mx-card-heading"><h3>{ui_icon('trend')} Nhu cầu ngày kế tiếp</h3><span class="mx-tag">{target:%d/%m}</span></div><div class="mx-summary-number">{total_label}</div><p class="mx-caption">Trung bình trượt 7 ngày · dựa trên dữ liệu đến {latest.strftime('%d/%m/%Y') if latest else 'chưa có'}</p>{product_rows}{page_link('Dự báo', 'Khám phá dự báo')}</section><section class="mx-card"><div class="mx-card-heading"><h3>{ui_icon('star')} Món được yêu thích</h3><span class="mx-tag">{today:%d/%m}</span></div><p class="mx-caption">Top 3 sản phẩm theo số ly bán ra</p>{best_rows or '<p>Chưa có kết quả hôm nay.</p>'}{page_link('Tem & công thức', 'Tra cứu công thức')}</section><section class="mx-card mx-ai-note"><div class="mx-card-heading"><h3>{ui_icon('chat')} Một chút gợi ý từ AI</h3><span>✦</span></div><div class="mx-ai-intro">{snow_king_image(62)}<p>Một ngày vận hành tốt<br>bắt đầu từ sự chuẩn bị.</p></div><p>Xem dự báo, kiểm tra nguyên liệu và chuẩn bị topping trước giờ cao điểm cùng Tuyết Vương nhé!</p>{page_link('💬 Tuyết Vương AI', 'Trò chuyện với Tuyết Vương')}</section></div>''', unsafe_allow_html=True)


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

    if is_admin:
        render_home_kpis(sales, menu)
    else:
        # Nhân viên KHÔNG được phép xem Doanh thu và Sản lượng
        render_kpi_cards([
            ('⭐', 'Quy mô thực đơn', f'{len(menu)} món', '<em>Tra cứu công thức từng món</em>'),
            ('📋', 'Tiêu chuẩn pha chế', 'SOP Mixue Bar', '<em>Đúng công thức, đậm vị</em>'),
            ('⏰', 'Giờ phục vụ', '08:00 – 23:00', '<em>Hàng ngày</em>'),
        ])
    render_shortcuts(user_role)
    render_menu_card(menu)


def render_menu_card(menu):
    """Compact menu: search + group pills + rows with a thumbnail and the recipe action."""
    with st.container(border=True, key='home_menu_card'):
        head, search = st.columns([1.4, 1], gap='medium', vertical_alignment='center')
        head.markdown(f'<div class="px-section-head" id="mixue-menu"><h2>Thực đơn · {len(menu)} món</h2></div>', unsafe_allow_html=True)
        query = search.text_input('Tìm món theo tên hoặc mã', placeholder='Tìm món: trà sữa, TS1…', key='menu_search',
                                  label_visibility='collapsed')
        group = st.pills('Nhóm đồ uống', ['Tất cả', 'Kem', 'Trà sữa', 'Trà trái cây', 'Sữa trái cây', 'Cà phê'], default='Tất cả',
                         key='menu_group', label_visibility='collapsed') or 'Tất cả'

        featured = {'DK1': 0, 'TS1': 1, 'THQ1': 2}
        ordered = sorted(menu, key=lambda m: (featured.get(m[0], 3), m[0].rstrip('0123456789'), int(''.join(c for c in m[0] if c.isdigit()) or '0')))
        filtered = [m for m in ordered if (group == 'Tất cả' or menu_group(m[0]) == group) and normalized(query) in normalized(f'{m[0]} {m[1]}')]
        if not filtered:
            st.info('Không tìm thấy món. Thử tên khác hoặc chọn Tất cả.')
            return
        per_page = 9
        pages = (len(filtered) + per_page - 1) // per_page
        page = 1
        if pages > 1:
            meta, picker = st.columns([2, 1], vertical_alignment='center')
            meta.caption(f'{len(filtered)} món phù hợp')
            page = picker.selectbox('Trang thực đơn', range(1, pages + 1), format_func=lambda n: f'Trang {n} / {pages}',
                                    key=f'menu_page_{group}_{query}', label_visibility='collapsed')
        items = filtered[(page - 1) * per_page:page * per_page]
        for start in range(0, len(items), 3):
            for col, (sku, name, variant, price) in zip(st.columns(3, gap='small'), items[start:start + 3]):
                with col, st.container(key=f'menu_row_{sku}'):
                    price_label = f'{price:,.0f}'.replace(',', '.')
                    image_info = product_images().get(sku, {})
                    st.markdown(f'''<div class="px-menu-row"><img src="{asset(product_photo(sku, name))}" alt="{escape(image_info.get('source_name', name))}" loading="lazy">
                    <div><strong title="{escape(name)}">{escape(name)}</strong><small>{escape(sku)} · {escape(variant or menu_group(sku))} · {price_label} đ</small></div></div>''',
                                unsafe_allow_html=True)
                    if st.button('Công thức', key=f'menu_{sku}', type='tertiary'):
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
            policy = 'đúng 6 chữ số' if demo_enabled() else 'từ 12 đến 128 ký tự'
            st.warning(f'Bạn cần đổi mật khẩu tạm do quản lý cấp. Mật khẩu mới phải có {policy}.')

            with st.form("force_change_password_form", clear_on_submit=False):
                old_pass = st.text_input('Mật khẩu hiện tại', type='password', key='force_old_pass')
                new_pass = st.text_input(f'Mật khẩu mới ({policy})', type='password', max_chars=128, key='force_new_pass')
                confirm_pass = st.text_input('Xác nhận lại mật khẩu mới', type='password', max_chars=128, key='force_confirm_pass')
                
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

        if not demo_enabled():
            st.caption('Dùng tài khoản do quản lý cấp. Liên hệ quản lý nếu bạn chưa có tài khoản hoặc cần đặt lại mật khẩu.')
            return
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


def _render_chat_evidence(refs):
    """Keep precise references in history; show readable source names on request."""
    names = {
        '09_Cong_thuc_so_che_theo_me': 'Công thức sơ chế theo mẻ',
        '10_Quy_dinh_bao_quan_theo_anh': 'Quy định bảo quản',
        '13_Thoi_gian_so_che_theo_anh': 'Thời gian sơ chế',
        '15_Han_dung_nguyen_lieu_tren_anh': 'Hạn dùng nguyên liệu',
        '16_Quy_tac_duong_va_topping': 'Quy tắc đường và topping',
        'sales_daily': 'Dữ liệu bán hàng', 'daily_sales': 'Dữ liệu bán hàng',
        'recipe_bom': 'Định lượng công thức', 'bom_recipes': 'Định lượng công thức',
        'shift_reports': 'Báo cáo chốt ca', 'pos_slip': 'Phiếu POS',
    }
    labels = []
    for ref in refs:
        ref = str(ref)
        label = next((name for key, name in names.items() if key in ref), None)
        label = label or ref.removeprefix('file:').removeprefix('table:').split('/')[-1]
        if label not in labels:
            labels.append(label)
    with st.expander('Nguồn dữ liệu', expanded=False):
        st.caption(' · '.join(labels))


def conversation_labels(conversations):
    """Unique, stable selector labels.

    Streamlit serializes a selectbox value by its formatted label, so two chats with the
    same title would map back to the wrong conversation on the next rerun. The label uses
    the creation time (never changes) and a short id when titles still collide.
    """
    base = {}
    for row in conversations:
        stamp = ''
        try:
            created = datetime.fromisoformat(str(row.get('created_at')))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            stamp = created.astimezone(timezone(timedelta(hours=7))).strftime('%d/%m %H:%M')
        except (TypeError, ValueError):
            pass
        base[row['id']] = f"{row.get('title') or 'Cuộc trò chuyện'}" + (f' · {stamp}' if stamp else '')
    counts = {}
    for label in base.values():
        counts[label] = counts.get(label, 0) + 1
    # Suffix every member of a colliding group so the mapping does not depend on list order.
    return {ident: (label if counts[label] == 1 else f'{label} · #{str(ident)[:6]}') for ident, label in base.items()}


def render_approval_card(agent, pending, clean_role, user_name, is_admin, key_suffix=''):
    """The LangGraph interrupt() card: Manager approves or cancels; the server rechecks on resume."""
    with st.container(border=True, key=f'approval_card{key_suffix}'):
        if pending.get('plan_type') == 'SHIFT_OCR_DRAFT':
            from src.dashboard import ocr_components as vocr
            draft = pending.get('plan') or {}
            fields = draft.get('fields', {})
            st.markdown(f"#### ⏸️ LangGraph `interrupt()` · Phê duyệt lưu chốt ca `{pending['plan_id']}`")
            st.caption(f"Yêu cầu bởi `{pending.get('requested_by')}` · Ngày `{fields.get('report_date')}` · Ca `{fields.get('shift_code')}` · "
                       "Chưa có số nào được ghi vào sổ doanh thu cho tới khi Quản lý bấm Phê duyệt.")
            vocr.install_css()
            st.markdown(vocr.document_badge(draft.get('document_type')), unsafe_allow_html=True)
            summary = ''.join(f"<tr><td>{vocr.FIELD_LABELS[k]}</td><td class='vocr-num'>{vocr.money(fields.get(k))}</td></tr>"
                              for k in vocr.FIELD_LABELS if fields.get(k) is not None)
            st.markdown(f"<table class='vocr-table'><thead><tr><th>Khoản mục</th><th>Giá trị sẽ ghi sổ</th></tr></thead><tbody>{summary}</tbody></table>",
                        unsafe_allow_html=True)
            for disc in (draft.get('consistency') or {}).get('discrepancies', []):
                st.warning(f"⚠️ {disc.get('message')}")
        else:
            st.markdown(f"**Xác nhận kế hoạch {pending['plan_id']}**")
            with st.expander('Xem nội dung kế hoạch trước khi duyệt'):
                st.json(pending['plan'])
        accept, reject = st.columns(2)
        approved = accept.button('✅ Phê duyệt', type='primary', key=f'approve_agent{key_suffix}', disabled=not is_admin)
        cancelled = reject.button('🛑 Hủy', key=f'reject_agent{key_suffix}')
        if not is_admin:
            st.caption('🔒 Chỉ Quản lý/Chủ quán được phê duyệt (kiểm tra lại ở máy chủ khi tiếp tục luồng).')
        if approved or cancelled:
            result = agent.resume_approval(approved, clean_role, user_name,
                                           user_id=st.session_state.get('username', user_name))
            st.session_state.agent_pending_approval = result.get('pending_approval')
            st.session_state.setdefault('chat_history_vi', []).append(
                {'role': 'assistant', 'content': result['text'], 'evidence': result.get('evidence_refs', [])})
            st.session_state['approval_notice'] = result['text']
            st.rerun()


def _render_chat_conversation(agent, role, user_name, history_height=250, key_suffix=""):
    """Persistent conversation with a normal page flow and one message composer."""
    from src.auth import is_admin_role

    clean_role = (role or "STAFF").strip().upper()
    is_admin = is_admin_role(clean_role)

    account_id = st.session_state.get('username', user_name)
    saved = agent.conversation_history(clean_role, user_name, user_id=account_id)
    conversations = saved['conversations']
    choices = [row['id'] for row in conversations]
    titles = conversation_labels(conversations)
    selector_key = f'chat_conversation_{account_id}_{clean_role}'
    if choices:
        selected = st.selectbox('Lịch sử trò chuyện', choices,
                                index=choices.index(saved['conversation_id']) if saved['conversation_id'] in choices else 0,
                                format_func=lambda ident: titles.get(ident, ident), key=selector_key)
        if selected in titles and selected != saved['conversation_id']:
            agent.select_conversation(selected, clean_role, user_name, user_id=account_id)
            st.session_state.pop('chat_input_val', None)
            st.rerun()
    st.session_state.agent_pending_approval = saved['pending_approval']
    st.session_state.chat_history_vi = saved['messages'] or [
        {'role': 'assistant', 'content': f'Xin chào {user_name}! Mình là **Tuyết Vương AI**.'}]
    st.caption('Lịch sử được lưu riêng theo tài khoản. Mở cuộc trò chuyện cũ để tiếp tục ngữ cảnh.')

    history = st.container(height=history_height, border=False) if history_height else st.container()
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
                    _render_chat_evidence(message['evidence'])
                if message['role'] == 'assistant' and message.get('message_id'):
                    feedback_key = f"chat_rating_{message['message_id']}"
                    if feedback_key not in st.session_state:
                        st.session_state[feedback_key] = message.get('rating')
                    def save_feedback(mid=message['message_id'], key=feedback_key):
                        rating = st.session_state.get(key)
                        if rating is not None:
                            agent.record_feedback(mid, rating, clean_role, user_name, user_id=account_id)
                    st.feedback('thumbs', key=feedback_key, on_change=save_feedback)
        thinking_slot = st.empty()

    if prompt:
        st.session_state.chat_history_vi.append({'role': 'user', 'content': prompt})
        with history, st.chat_message('user'):
            st.markdown(prompt)
        thinking_slot.markdown(
            f'''<div class="snowking-thinking-card">
            {snow_king_image(42, mode="thinking")}
            <div class="thinking-text-wrap">
                <div class="thinking-title">Tuyết Vương đang trả lời bạn <span class="thinking-dots"><span></span><span></span><span></span></span></div>
                <div class="thinking-sub">Chờ mình một chút nhé.</div>
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
                user_id=st.session_state.get('username', user_name),
                chat_history=st.session_state.chat_history_vi
            )
            reply_msg = {'role': 'assistant', 'content': response['text'], 'evidence': response.get('evidence_refs', [])}
            st.session_state.agent_pending_approval = response.get('pending_approval')
            st.session_state.agent_execution_mode = response.get('execution_mode')
            st.session_state.agent_last_tool = response.get('tool_called')
        except Exception:
            reply_msg = {'role': 'assistant', 'content': 'Mình chưa truy xuất được dữ liệu. Bạn hãy thử lại hoặc kiểm tra kết nối dữ liệu cửa hàng.'}
        st.session_state.chat_history_vi.append(reply_msg)
        thinking_slot.empty()
        with history, st.chat_message('assistant', avatar=assistant_avatar):
            st.markdown(reply_msg['content'])
            if reply_msg.get('evidence'):
                _render_chat_evidence(reply_msg['evidence'])

    exec_mode = st.session_state.get('agent_execution_mode')
    if exec_mode == 'llm':
        st.caption('🟢 Chế độ AI Online (Gemini + LangGraph Tool Calling) · Đã xác thực nguồn dữ liệu.')
    elif exec_mode == 'offline_fallback':
        st.caption('⚡ Đã tự động chuyển sang Động cơ Tra cứu Cục bộ (do kết nối API gián đoạn) · Vẫn đảm bảo chính xác 100%.')
    elif exec_mode == 'offline_rules':
        st.caption('⚡ Chế độ Tra cứu Nhanh cục bộ (<50ms) · Bạn có thể bấm nút "⚡ Chế độ Nhanh (Offline)" phía trên để bật AI Online.')
    pending = st.session_state.get('agent_pending_approval')
    if pending and pending.get('plan_type') == 'SHIFT_OCR_DRAFT' and st.session_state.get('main_navigation') == '📸 Chốt ca & OCR':
        st.caption('⏸️ Thẻ phê duyệt chốt ca đang hiển thị trong phần **Chốt Ca & Đối Soát OCR** phía trên.')
    elif pending:
        render_approval_card(agent, pending, clean_role, user_name, is_admin, key_suffix)

    # OCR Draft Review & Confirmation Card (Prompt 2)
    # The conversation store is the source of truth: a confirmed or cancelled draft disappears here.
    if prompt:
        saved = agent.conversation_history(clean_role, user_name, user_id=account_id)
    active_ocr_draft = saved.get('pending_ocr_draft')
    st.session_state.agent_pending_ocr_draft = active_ocr_draft
    if active_ocr_draft:
        from src.dashboard import ocr_components as vocr
        with st.container(border=True, key=f'ocr_draft_card{key_suffix}'):
            st.markdown(f"### 📸 Dự Thảo Chốt Ca Từ Ảnh (`{active_ocr_draft['draft_id']}`)")
            vocr.install_css()
            st.markdown(f"{vocr.document_badge(active_ocr_draft.get('document_type'))} "
                        + vocr.badge(f"{len(active_ocr_draft.get('missing_fields') or [])} trường chờ xác nhận",
                                     'ok' if active_ocr_draft.get('is_complete') else 'warn'),
                        unsafe_allow_html=True)
            f_ids = active_ocr_draft.get("file_ids") or ([active_ocr_draft.get("file_id")] if active_ocr_draft.get("file_id") else [])
            f_names = active_ocr_draft.get("filenames") or []
            if len(f_ids) > 1:
                f_meta = f"Mã tệp ({len(f_ids)} ảnh): " + ", ".join(f"`{f}`" for f in f_ids)
                if f_names:
                    f_meta += f" *({', '.join(f_names)})*"
            else:
                f_meta = f"Mã tệp: `{active_ocr_draft.get('file_id')}`"
                if f_names:
                    f_meta += f" *({f_names[0]})*"
            st.caption(f"{f_meta} · Loại chứng từ: `{active_ocr_draft.get('document_type')}` · Trạng thái: **Đang chờ xác nhận**")

            consistency = active_ocr_draft.get('consistency') or {}
            discrepancies = consistency.get('discrepancies') or []
            if discrepancies:
                for d in discrepancies:
                    st.warning(f"⚠️ {d['message']}")
            with st.expander('🔎 Bằng chứng từng trường: nguồn · trạng thái · đọc thô · lý do', expanded=not active_ocr_draft.get('is_complete')):
                vocr.render_field_table(active_ocr_draft.get('field_readings', {}), active_ocr_draft.get('fields', {}))

            with st.expander("✏️ Chỉnh sửa số liệu dự thảo trước khi xác nhận", expanded=False):
                with st.form(key=f"ocr_edit_form_{active_ocr_draft['draft_id']}{key_suffix}"):
                    c1, c2, c3 = st.columns(3)
                    e_date = c1.text_input("Ngày báo cáo (YYYY-MM-DD)", value=active_ocr_draft.get('business_date') or "")
                    cur_sc = active_ocr_draft.get('shift_code') or "CA_SANG"
                    sc_opts = ["CA_SANG", "CA_CHIEU", "CA_TOI"]
                    e_shift = c2.selectbox("Mã ca", sc_opts, index=sc_opts.index(cur_sc) if cur_sc in sc_opts else 0)
                    e_signed = c3.text_input("Người ký", value=active_ocr_draft.get('signed_by') or "")

                    fields_data = active_ocr_draft.get('fields', {})
                    c_rev, c_col = st.columns(2)
                    e_rev = c_rev.number_input("Tổng doanh thu POS (đ)", value=int(fields_data.get('pos_revenue_vnd') or 0), step=1000)
                    e_col = c_col.number_input("Thực thu POS (đ)", value=int(fields_data.get('pos_collected_vnd') or 0), step=1000)

                    c_cash, c_diff = st.columns(2)
                    e_cash = c_cash.number_input("Tiền mặt thực tế (đ)", value=int(fields_data.get('cash_vnd') or 0), step=1000)
                    e_diff = c_diff.number_input("Lệch tiền mặt (dư/thiếu đ)", value=int(fields_data.get('cash_diff_vnd') or 0), step=1000)

                    c_shp, c_grb, c_exp = st.columns(3)
                    e_shp = c_shp.number_input("ShopeeFood (đ)", value=int(fields_data.get('shopee_food_vnd') or 0), step=1000)
                    e_grb = c_grb.number_input("GrabFood (đ)", value=int(fields_data.get('grab_food_vnd') or 0), step=1000)
                    e_exp = c_exp.number_input("Chi phí trong ca (đ)", value=int(fields_data.get('expenses_vnd') or 0), step=1000)

                    save_changes = st.form_submit_button("Lưu chỉnh sửa dự thảo")
                    if save_changes:
                        updates = {
                            "report_date": e_date.strip() if e_date else None,
                            "shift_code": e_shift,
                            "signed_by": e_signed.strip(),
                            "pos_revenue_vnd": e_rev,
                            "pos_collected_vnd": e_col,
                            "cash_vnd": e_cash,
                            "cash_diff_vnd": e_diff,
                            "shopee_food_vnd": e_shp,
                            "grab_food_vnd": e_grb,
                            "expenses_vnd": e_exp,
                        }
                        up_res = agent.update_ocr_draft(updates, user_role=clean_role, user_name=user_name, user_id=account_id, draft_id=active_ocr_draft['draft_id'])
                        st.session_state.agent_pending_ocr_draft = up_res.get('draft')
                        st.session_state.chat_history_vi.append({'role': 'assistant', 'content': up_res['text'], 'evidence': up_res.get('source_refs', [])})
                        st.rerun()

            c_act1, c_act2 = st.columns(2)
            waiting = bool(pending and pending.get('plan_id') == active_ocr_draft['draft_id'])
            btn_confirm = c_act1.button(
                "⏸️ Đang chờ Quản lý phê duyệt" if waiting else "📨 Yêu cầu phê duyệt lưu (LangGraph interrupt)",
                type="primary", key=f"confirm_ocr_{active_ocr_draft['draft_id']}{key_suffix}", disabled=waiting,
                help="Gọi request_shift_draft_confirmation: luồng dừng ở interrupt() và chỉ ghi sổ khi Quản lý bấm Phê duyệt.")
            btn_cancel = c_act2.button("🛑 Hủy dự thảo", key=f"cancel_ocr_{active_ocr_draft['draft_id']}{key_suffix}")
            if btn_confirm:
                st.session_state.chat_input_val = 'Yêu cầu phê duyệt lưu báo cáo chốt ca'
                st.rerun()
            elif btn_cancel:
                c_res = agent.confirm_ocr_draft(False, user_role=clean_role, user_name=user_name, user_id=account_id, draft_id=active_ocr_draft['draft_id'])
                st.session_state.agent_pending_ocr_draft = None
                st.session_state.chat_history_vi.append({'role': 'assistant', 'content': c_res['text'], 'evidence': c_res.get('evidence_refs', [])})
                st.rerun()

    with st.expander("📸 Đính kèm ảnh chứng từ chốt ca (POS / Sổ viết tay / Hóa đơn)",
                     expanded=bool(st.session_state.pop('ocr_uploader_open', False))):
        uploaded_slips = st.file_uploader(
            "Chọn file ảnh chụp phiếu POS, sổ chốt ca viết tay hoặc hóa đơn (hỗ trợ chọn nhiều ảnh cùng lúc)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            key=f"ocr_slip_uploader_{account_id}{key_suffix}",
        )
        if uploaded_slips:
            count = len(uploaded_slips)
            st.caption(f"📁 Đã chọn {count} ảnh chứng từ: " + ", ".join(f"`{f.name}`" for f in uploaded_slips[:3]) + ("..." if count > 3 else ""))
            btn_txt = f"🚀 Gửi {count} ảnh cho Tuyết Vương AI đọc" if count > 1 else "🚀 Gửi ảnh cho Tuyết Vương AI đọc"
            if st.button(btn_txt, key=f"btn_process_slip_{account_id}{key_suffix}"):
                with st.spinner(f"Tuyết Vương đang kiểm tra bố cục và nhận diện {count} chứng từ..." if count > 1 else "Tuyết Vương đang kiểm tra bố cục và nhận diện chứng từ..."):
                    files_payload = [(f.name, f.getvalue()) for f in uploaded_slips]
                    img_res = agent.process_image_message(
                        files=files_payload,
                        user_role=clean_role,
                        user_name=user_name,
                        user_id=account_id,
                    )
                st.session_state.agent_pending_ocr_draft = img_res.get('draft')
                st.session_state.chat_history_vi.append({'role': 'assistant', 'content': img_res['text'], 'evidence': img_res.get('evidence_refs', [])})
                st.rerun()
        samples = sorted((HERE.parent.parent / 'data' / 'shift_photos').glob('2026*.jpg'))
        if samples:
            st.caption('🧪 Hoặc dùng ảnh chứng từ mẫu của cửa hàng (ngày 14/10/2026):')
            sample_labels = {'20261014_ca_sang_chieu.jpg': '✍️ Sổ ca sáng/chiều', '20261014_ca_toi_tong_ket.jpg': '✍️ Sổ ca tối',
                             '20261014_pos_slip.jpg': '🧾 Hóa đơn POS'}
            for column, sample in zip(st.columns(len(samples)), samples):
                if column.button(sample_labels.get(sample.name, sample.name), key=f"ocr_sample_{sample.stem}{key_suffix}", use_container_width=True):
                    with st.spinner("Tuyết Vương đang kiểm tra chất lượng ảnh và tách vùng chứng từ..."):
                        stamp = sample.name[:8]
                        hint = f"Ảnh mẫu chốt ca{' ca tối' if 'ca_toi' in sample.name else ''} ngày {stamp[6:8]}/{stamp[4:6]}/{stamp[:4]}"
                        img_res = agent.process_image_message(files=[(sample.name, sample.read_bytes())], user_query=hint,
                                                              user_role=clean_role, user_name=user_name, user_id=account_id)
                    st.session_state.chat_history_vi.append({'role': 'assistant', 'content': img_res['text'], 'evidence': img_res.get('evidence_refs', [])})
                    st.rerun()


ACTION_CHIPS = (
    ('chip_ocr_read', '📸 Đọc & đối soát ảnh sổ chốt ca viết tay', 'Đọc & đối soát ảnh sổ chốt ca viết tay', True),
    ('chip_ocr_update', '✏️ Cập nhật số liệu dự thảo OCR đang chờ', 'Cập nhật số liệu dự thảo OCR đang chờ', False),
    ('chip_ocr_approve', '✅ Yêu cầu phê duyệt lưu báo cáo chốt ca', 'Yêu cầu phê duyệt lưu báo cáo chốt ca', False),
    ('chip_sticker_sop', '🏷️ Giải mã tem ly 24101 & tra cứu SOP nấu trân châu', 'Giải mã tem ly 24101 & tra cứu SOP nấu trân châu', False),
    ('chip_governance', '🛡️ Kiểm tra quyền hạn & lịch sử phê duyệt (HITL)', 'Kiểm tra quyền hạn & lịch sử phê duyệt (HITL)', False),
)


def render_chat(agent, role, user_name, mode="auto"):
    """Render the dedicated conversation page; never mount a floating duplicate."""
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
            ('Quy trình bảo quản', 'Cách bảo quản nguyên liệu sau khi mở bao bì?'),
        ]
    else:
        quick = [
            ('Công thức Trà sữa', 'Công thức TS1'),
            ('Sơ chế trân châu', 'Quy trình sơ chế trân châu và hạn dùng'),
            ('Sơ chế thạch đào', 'Cách sơ chế thạch đào và hạn bảo quản'),
            ('Quy trình bảo quản', 'Cách bảo quản nguyên liệu sau khi mở bao bì?'),
        ]

    def ask_quick(question):
        st.session_state.chat_input_val = question

    def ask_chip(question, open_uploader=False):
        st.session_state.chat_input_val = question
        if open_uploader:
            st.session_state['ocr_uploader_open'] = True

    def render_action_chips():
        with st.container(key="chat_action_chips"):
            st.caption('⚡ Thao tác nhanh — 2 trụ cột OCR & Agent')
            for column, (key, label, question, opens) in zip(st.columns(len(ACTION_CHIPS), gap="small"), ACTION_CHIPS):
                column.button(label, key=key, use_container_width=True, on_click=ask_chip, args=(question, opens), help=question)

    def render_quick_questions():
        with st.expander('Gợi ý câu hỏi', expanded=False), st.container(key="chat_quick_questions"):
            for row in (quick[:2], quick[2:]):
                for col, (label, question) in zip(st.columns(2, gap="small"), row):
                    col.button(label, key=f'chat_{label}', use_container_width=True,
                               on_click=ask_quick, args=(question,))

    def _handle_new_conversation():
        act_id = st.session_state.get('username', user_name)
        new_id = agent.new_conversation(clean_role, user_name, user_id=act_id)
        st.session_state[f"chat_conversation_{act_id}_{clean_role}"] = new_id
        st.session_state.pop('agent_pending_approval', None)
        st.session_state['chat_history_vi'] = [
            {'role': 'assistant', 'content': f'Xin chào {user_name}! Mình là **Tuyết Vương AI**.'}
        ]

    is_online_now = bool(getattr(agent, "is_llm_online", lambda: False)())

    def _handle_toggle_llm():
        if hasattr(agent, "set_llm_mode"):
            target = not bool(agent.is_llm_online())
            _, notice = agent.set_llm_mode(target)
            st.session_state["llm_mode_notice"] = notice

    with st.container(key="chat_panel_box"):
        title, mode_col, action = st.columns([3.2, 1.3, 1.1])
        title.markdown(
            f'<div class="px-chat-head"><img src="{asset("snow-king-cutout.png")}" alt="">'
            '<div><span class="px-eyebrow">TRỤ CỘT 2 · LANGGRAPH AGENT</span><h3>Tuyết Vương AI</h3></div></div>',
            unsafe_allow_html=True,
        )
        mode_label = '🟢 AI Online (Gemini)' if is_online_now else '⚡ Chế độ Nhanh (Offline)'
        mode_col.button(
            mode_label,
            key='toggle_llm_mode_btn',
            on_click=_handle_toggle_llm,
            use_container_width=True,
            help='Bấm để chuyển đổi trực tiếp giữa Mô hình AI Online (Gemini + Tool Calling) và Chế độ Tra cứu Nhanh cục bộ (<50ms)',
        )
        action.button('＋ Trò chuyện mới', key='clear_chat', on_click=_handle_new_conversation, use_container_width=True)
        if llm_notice := st.session_state.pop("llm_mode_notice", None):
            st.info(llm_notice)
        render_action_chips()
        if effective_mode == "fullscreen":
            main_col, rail_col = st.columns([2.6, 1], gap="medium")
            with main_col, st.container(key='chat_main_card'):
                _render_chat_conversation(agent, clean_role, user_name, history_height=None)
            with rail_col:
                render_agent_rail(agent, clean_role, user_name, is_online_now)
        else:
            _render_chat_conversation(agent, clean_role, user_name, history_height=280)
        render_quick_questions()
        with st.expander('Dữ liệu và chức năng có thể tra cứu'):
            render_chat_context(is_admin)


TRACE_NODES = (('guard', 'Chặn injection / dữ liệu nhạy cảm'), ('model', 'Gemini chọn công cụ hoặc offline router'),
               ('authorize', 'Kiểm tra RBAC theo vai trò'), ('tools', 'Gọi công cụ, gắn bằng chứng'),
               ('approval', 'interrupt() chờ Admin'))


def render_agent_rail(agent, role, user_name, is_online):
    """Right rail: where the LangGraph run stopped, what this role may do, and the last evidence."""
    from src.auth import is_admin_role
    try:
        saved = agent.conversation_history(role, user_name, user_id=st.session_state.get('username', user_name))
    except Exception:  # noqa: BLE001 - the rail is informative only
        saved = {}
    pending = saved.get('pending_approval')
    draft = saved.get('pending_ocr_draft')
    last_tool = st.session_state.get('agent_last_tool')
    asked = any(m.get('role') == 'user' for m in saved.get('messages', []))
    rows = []
    for node, hint in TRACE_NODES:
        if node == 'approval':
            state, mark, note = ('pause', '⏸', 'đang chờ') if pending else ('idle', '', 'khi ghi sổ')
        elif not asked:
            state, mark, note = 'idle', '', ''
        else:
            state, mark = '', '✓'
            note = escape(last_tool) if node == 'tools' and last_tool else ('online' if node == 'model' and is_online else 'offline' if node == 'model' else '')
        rows.append(f'<li title="{escape(hint)}"><span class="dot {state}">{mark}</span>{node}<small>{note}</small></li>')
    rt = agent._runtime()
    allowed = [spec for spec in rt.tools.values() if spec.allowed(role)]
    effects = {}
    for spec in allowed:
        effects[spec.effect] = effects.get(spec.effect, 0) + 1
    effect_vi = {'read': 'Chỉ đọc', 'draft': 'Tạo dự thảo', 'approval': 'Cần phê duyệt'}
    rbac = ''.join(f'<div class="px-kv"><span>{effect_vi.get(k, k)}</span><b class="px-num">{v}</b></div>' for k, v in sorted(effects.items()))
    account = escape(str(st.session_state.get('username', user_name)))
    role_note = ('Admin · duyệt được interrupt' if is_admin_role(role)
                 else 'Nhân viên · bị chặn ở node authorize với công cụ cần phê duyệt')
    evidence = next((m.get('evidence') for m in reversed(saved.get('messages', [])) if m.get('role') == 'assistant' and m.get('evidence')), []) or []
    refs = ''.join(f'<span class="px-ref">{escape(str(ref))}</span>' for ref in evidence[:6]) or '<small>Chưa có bằng chứng trong cuộc trò chuyện này.</small>'
    status = ''
    if draft:
        status = (f'<div class="px-kv"><span>Dự thảo OCR</span><b>{escape(draft["draft_id"])}</b></div>'
                  f'<div class="px-kv"><span>Trường chờ xác nhận</span><b class="px-num">{len(draft.get("missing_fields") or [])}</b></div>')
    st.markdown(f'''<div class="px-rail">
    <div class="px-rail-card"><h4>Luồng LangGraph · lượt này</h4><ol class="px-trace">{''.join(rows)}</ol>{status}</div>
    <div class="px-rail-card"><h4>Quyền hạn (máy chủ xác thực)</h4><div class="px-kv"><span>Tài khoản</span><b>{account} · {escape(role)}</b></div>
    <div class="px-kv"><span>Công cụ được phép</span><b class="px-num">{len(allowed)}/{len(rt.tools)}</b></div>{rbac}<p class="px-rail-note">{escape(role_note)}</p></div>
    <div class="px-rail-card"><h4>Nguồn bằng chứng</h4>{refs}<p class="px-rail-note">Thiếu nguồn cho câu hỏi số liệu → trả MISSING_EVIDENCE, không đoán.</p></div></div>''', unsafe_allow_html=True)


def render_chat_context(is_admin):
    """Only expose the sources allowed for the current user's role."""
    from src.database import SessionLocal
    from src.models import Ingredient, MenuItem, RecipeBOM
    with SessionLocal() as db:
        sources = [('recipe', 'Thực đơn cửa hàng', f'{db.query(MenuItem).count()} món trong thực đơn'),
                   ('cup', 'Công thức & định lượng', f'{db.query(RecipeBOM).count()} định lượng nguyên liệu'),
                   ('box', 'Danh mục nguyên liệu', f'{db.query(Ingredient).count()} nguyên liệu')]
    rows = ''.join(f'<div class="mx-source-row"><span>{ui_icon(icon)}</span><div><b>{label}</b><small>{detail}</small></div><i>✓</i></div>' for icon, label, detail in sources)
    links = page_link('Tem & công thức', 'Mở sổ tay công thức')
    if is_admin:
        links += page_link('Dự báo', 'Xem dự báo nhu cầu')
        links += page_link('Báo cáo & kho', 'Kiểm tra kho & báo cáo')
    st.markdown(f'<aside class="mx-context"><section class="mx-card"><div class="mx-card-heading"><h3>{ui_icon("recipe")} Dữ liệu của cửa hàng</h3></div><p>Các nguồn dữ liệu có sẵn để tra cứu</p>{rows}</section><section class="mx-card mx-ai-note"><div class="mx-ai-intro">{snow_king_image(54)}<b>Luôn sẵn sàng<br>giúp bạn một tay.</b></div><p>Bạn có thể hỏi công thức, dữ liệu cửa hàng hoặc quy trình sơ chế. Mở phần “Nguồn dữ liệu” dưới câu trả lời để xem thông tin đối chiếu.</p><div class="mx-context-links">{links}</div></section></aside>', unsafe_allow_html=True)
