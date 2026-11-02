"""BeverageOps AI — Giao diện Quản trị Vận hành Chi nhánh Mixue 39 Tôn Quang Phiệt.

Thiết kế nhận diện thương hiệu Tuyết Vương (Snow King / 雪王) và phong cách ứng dụng My Mixue.
Đồng bộ 100% tiếng Việt chuyên ngành F&B, tối ưu hiệu năng và kiểm soát lỗi toàn diện.
"""

import os
import sys
import time
_RUN_STARTED = time.perf_counter()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from datetime import datetime

import pandas as pd
import streamlit as st

from src.agent.mixue_agent import MixueOperationsAgent
from src.agent.config import AgentSettings
from src.engine.weather import VN
from src.engine.stock_matrix import matrix_views
from src.dashboard.forecast_context_ui import render_forecast_context
from src.auth import (
    CHAT_PAGE,
    OCR_PAGE,
    can_access_page,
    create_employee,
    update_employee,
    delete_employee,
    normalize_role,
    get_all_employees,
    get_allowed_pages,
    is_admin_role,
    reset_employee_password,
)
from src.dashboard.sales_view import business_today
from src.dashboard.brand_ui import (
    install_brand,
    nav_group_css,
    nav_label,
    render_chat,
    render_force_change_password_screen,
    render_home,
    render_login_screen,
    render_mobile_navigation,
    render_page_hero,
    render_pillars,
    render_home_greeting,
    render_sidebar_bottom,
    render_sidebar_top,
    render_topbar,
)
from src.dashboard.shift_closing_ui import render_shift_closing_view
from src.database import SessionLocal
from src.engine.bom_engine import BOMEngine
from src.engine.daily_stock_service import (
    column_map_for_period,
    approve_stock_request,
    create_stock_request,
    delete_stock_movement,
    generate_excel_export,
    get_all_movements_detailed,
    get_cell_value,
    get_pending_requests,
    get_stock_matrix_df,
    get_user_requests,
    reject_stock_request,
    update_stock_cell_manually,
    update_stock_matrix_from_editor,
    update_stock_movement,
)
from src.models import MenuItem, User
from src.engine.plan_service import list_plans

# ==============================================================================
# CẤU HÌNH TRANG STREAMLIT
# ==============================================================================
st.set_page_config(
    page_title="Mixue 39 Tôn Quang Phiệt — Trợ lý Vận hành Tuyết Vương AI",
    page_icon="🍦",
    layout="wide",
    initial_sidebar_state="auto"
)

# ==============================================================================
# PHONG CÁCH NHẬN DIỆN THƯƠNG HIỆU TUYẾT VƯƠNG & MY MIXUE (CSS)
# ==============================================================================
install_brand()

# ==============================================================================
# KHỞI TẠO DỊCH VỤ VÀ BỘ NHỚ ĐỆM
# ==============================================================================
def get_operations_agent():
    # Keep drafts and database sessions isolated between browser sessions.
    settings = AgentSettings.from_env()
    existing = st.session_state.get('operations_agent')
    if existing is None or type(existing) is not MixueOperationsAgent or existing._graph_options.get('settings') != settings:
        if existing is not None:
            existing.close()
            st.session_state.pop('agent_pending_approval', None)
        st.session_state.operations_agent = MixueOperationsAgent(settings=settings)
    return st.session_state.operations_agent

try:
    agent = get_operations_agent()
except ValueError as error:
    st.error(f'Chưa khởi tạo được cấu hình vận hành: {error}')
    st.stop()

# ==============================================================================
# KIỂM TRA ĐĂNG NHẬP BẮT BUỘC (MANDATORY AUTHENTICATION)
# ==============================================================================
if not st.session_state.get("authenticated", False):
    from src import login_sessions
    from src.dashboard.brand_ui import _apply_login_session
    restored = login_sessions.restore(st.query_params.get(login_sessions.QUERY_KEY))
    if restored:
        _apply_login_session(restored, remember=False)
    else:
        st.query_params.pop(login_sessions.QUERY_KEY, None)
        render_login_screen()
        st.stop()

# Kiểm tra thời gian chờ phiên làm việc (Session Idle Timeout: 15 phút)
SESSION_TIMEOUT_MINUTES = 15
last_activity = st.session_state.get("last_activity")
now_dt = datetime.now()
if last_activity is not None and isinstance(last_activity, datetime):
    if (now_dt - last_activity).total_seconds() > SESSION_TIMEOUT_MINUTES * 60:
        from src import login_sessions
        login_sessions.revoke(st.query_params.get(login_sessions.QUERY_KEY))
        st.query_params.pop(login_sessions.QUERY_KEY, None)
        for k in ["authenticated", "user", "username", "user_role", "user_name", "user_title", "user_badge", "must_change_password", "main_navigation", "last_activity"]:
            st.session_state.pop(k, None)
        st.warning(f"Phiên làm việc đã hết hạn do không hoạt động quá {SESSION_TIMEOUT_MINUTES} phút. Vui lòng đăng nhập lại.")
        render_login_screen()
        st.stop()

st.session_state["last_activity"] = now_dt

# Refresh account permissions so edits, deactivation and deletion affect existing sessions.
with SessionLocal() as account_db:
    account = account_db.get(User, st.session_state.get("username", ""))
    if not account or not account.is_active:
        st.session_state.clear()
        st.query_params.clear()
        st.warning("Tài khoản không còn hoạt động. Vui lòng đăng nhập lại.")
        render_login_screen()
        st.stop()
    st.session_state["user_role"] = account.role
    st.session_state["user_name"] = account.full_name
    st.session_state["must_change_password"] = account.must_change_password

# Kiểm tra yêu cầu đổi mật khẩu lần đầu (bắt buộc gồm đúng 6 chữ số)
if st.session_state.get("must_change_password", False):
    render_force_change_password_screen()
    st.stop()

user_role = st.session_state.get("user_role", "STAFF_OFFICIAL")
user_name = st.session_state.get("user_name", "Nhân viên Quầy Bar")
user_title = st.session_state.get("user_title", "Nhân viên pha chế")
user_badge = st.session_state.get("user_badge", "☕ Nhân viên")
role_key = user_role
is_admin = is_admin_role(user_role)



def get_cached_sales():
    eng = BOMEngine()
    df = eng.get_sales_summary()
    eng.close()
    return df

@st.cache_data
def get_cached_waste():
    eng = BOMEngine()
    df = eng.get_topping_waste_summary()
    eng.close()
    return df

@st.cache_data
def get_cached_menu_list():
    db = SessionLocal()
    items = [(m.sku_id, m.sku_name, m.variant, float(m.selling_price_vnd)) for m in db.query(MenuItem).order_by(MenuItem.sku_id).all()]
    db.close()
    return items

@st.cache_data
def get_cached_reconciliation_data():
    eng = BOMEngine()
    df = eng.calculate_inventory_reconciliation()
    eng.close()
    return df

@st.cache_data
def get_cached_daily_revenue():
    eng = BOMEngine()
    df = eng.get_daily_revenue_breakdown()
    eng.close()
    return df


@st.cache_data(ttl=900, show_spinner=False)
def cached_backtest(_engine, as_of_iso):
    """The model comparison only changes once a day; it took most of the Dự báo page's run time."""
    from datetime import date as _date
    return _engine.run_backtest(as_of=_date.fromisoformat(as_of_iso))


def quick_chart(df, x, y, kind, color):
    """A plain Vega-Lite spec: st.line_chart/bar_chart build and validate an Altair chart on every run (~0.1 s each)."""
    data = pd.DataFrame({x: pd.to_datetime(df[x]).dt.strftime("%Y-%m-%d"), y: df[y]})
    st.vega_lite_chart(data, {
        "mark": {"type": kind, "color": color, "tooltip": True, **({"point": True} if kind == "line" else {})},
        "encoding": {"x": {"field": x, "type": "temporal", "title": None, "axis": {"format": "%d/%m"}},
                     "y": {"field": y, "type": "quantitative", "title": None}},
        "height": 260,
    }, use_container_width=True)


@st.fragment
def render_live_home():
    render_home(get_cached_menu_list(), get_cached_sales(), user_role=user_role)


# ==============================================================================
# THANH ĐIỀU HƯỚNG BÊN TRÁI (SIDEBAR) — NHẬN DIỆN CHI NHÁNH & PHÂN QUYỀN
# ==============================================================================
with st.sidebar:
    render_sidebar_top()

    allowed_tabs = get_allowed_pages(user_role)
    current_nav = st.session_state.get("main_navigation")
    if current_nav not in allowed_tabs:
        current_nav = allowed_tabs[0]
        st.session_state["main_navigation"] = current_nav

    nav_index = allowed_tabs.index(current_nav) if current_nav in allowed_tabs else 0

    nav_group_css(allowed_tabs)
    section = st.radio(
        "Điều hướng",
        allowed_tabs,
        index=nav_index,
        format_func=nav_label,
        label_visibility="collapsed",
        key="main_navigation",
        width="stretch",
    )

    render_sidebar_bottom(user_name, user_title, user_badge)
    if st.button("Đăng xuất", key="btn_logout", icon=":material/logout:", use_container_width=True):
        agent.reset_conversation(start_new=False)
        st.session_state.pop('agent_pending_approval', None)
        from src import login_sessions
        login_sessions.revoke(st.query_params.get(login_sessions.QUERY_KEY))
        st.query_params.pop(login_sessions.QUERY_KEY, None)
        for k in ["authenticated", "user", "username", "user_role", "user_name", "user_title", "user_badge", "must_change_password", "main_navigation", "chat_history_vi", "last_activity"]:
            st.session_state.pop(k, None)
        st.rerun()

_pending_notifications = len(get_pending_requests()) if is_admin else 0
render_topbar(user_name, _pending_notifications, section)
if section not in (CHAT_PAGE, OCR_PAGE, "Trang chủ"):
    render_page_hero(section, user_name)
render_mobile_navigation(allowed_tabs, section)

if is_admin and section != OCR_PAGE:
    # Staff submissions wait on the OCR page; say so wherever the manager is.
    _waiting = agent.list_staff_submissions(user_role, user_name, user_id=st.session_state.get("username", user_name))
    if _waiting:
        def _open_inbox():
            st.session_state.main_navigation = OCR_PAGE
        with st.container(key="staff_inbox_banner"):
            _msg, _btn = st.columns([4, 1.3], vertical_alignment="center")
            _msg.warning(f"📥 Có **{len(_waiting)}** báo cáo chốt ca nhân viên gửi đang chờ bạn duyệt.")
            _btn.button("Mở & duyệt", key="open_staff_inbox", type="primary", on_click=_open_inbox, use_container_width=True)

with st.container(key="workspace"):
    if not can_access_page(user_role, section):
        st.error("🔒 **Truy cập bị từ chối:** Bạn không có quyền truy cập trang này. Chức năng chỉ dành riêng cho Quản lý và Chủ cửa hàng (Admin).")
    elif section == "Trang chủ":
        # Outside the auto-refresh fragment so the pillar buttons trigger a full rerun (page switch).
        render_home_greeting(agent, user_role, user_name)
        render_pillars(user_role)
        render_live_home()

    elif section == OCR_PAGE:
        render_shift_closing_view(user_role=user_role, user_name=user_name, is_admin=is_admin)

    elif section == "Báo cáo & kho":
        stock_period = st.date_input('Tháng xem sổ kho', value=datetime.now(VN).date().replace(day=1), key='stock_period')
        stock_year, stock_month = stock_period.year, stock_period.month
        stock_column_map = column_map_for_period(stock_year, stock_month)
        stock_views = matrix_views(stock_year, stock_month)
        # Hiển thị thông báo trạng thái thao tác kho (Flash alert) nếu có
        if "stock_flash_msg" in st.session_state:
            f_data = st.session_state["stock_flash_msg"]
            f_type = f_data.get("type", "success")
            f_text = f_data.get("text", "")
            if f_type == "success":
                st.success(f_text, icon="✅")
            elif f_type == "error":
                st.error(f_text, icon="⚠️")
            else:
                st.info(f_text, icon="ℹ️")
            del st.session_state["stock_flash_msg"]

        st.caption("📸 Chốt ca bằng ảnh & đối soát OCR nằm ở phân hệ riêng **📸 Chốt Ca & Đối Soát OCR** trên thanh điều hướng. "
                   "Trang này là công cụ phụ trợ: sổ kho, báo cáo doanh thu và đối soát thất thoát.")
        if not is_admin:
            (tab_staff_stock,) = st.tabs(["📝 Phiếu Đề Xuất Lệnh Kho Quầy Bar"])

            with tab_staff_stock:
                # ==============================================================================
                # GIAO DIỆN DÀNH CHO NHÂN VIÊN (STAFF MAKER REQUEST)
                # ==============================================================================
                st.subheader("📝 Phiếu Đề Xuất Lệnh Xuất / Nhập Kho Quầy Bar")
                st.caption("Chi nhánh Mixue 39 Tôn Quang Phiệt · Tạo đề xuất khui hàng pha chế hoặc nhận hàng xe tổng chuyển Quản lý phê duyệt.")

                st.markdown("""
                <div style="background:#eff6ff; border-left:4px solid #3b82f6; padding:12px 16px; border-radius:6px; margin-bottom:18px;">
                    <div style="font-weight:600; color:#1e40af; margin-bottom:4px;">🔒 Quy trình Kiểm soát Kho 2 Bước (Maker - Checker)</div>
                    <div style="font-size:13px; color:#1e3a8a; line-height:1.5;">
                        • Theo quy chế vận hành, nhân viên tạo lệnh đề xuất xuất/nhập kho tại quầy.<br>
                        • Sau khi gửi, lệnh sẽ ở trạng thái <b>⏳ Chờ Quản lý duyệt</b>.<br>
                        • Quản lý / Chủ cửa hàng sẽ kiểm tra và xác nhận duyệt thì dữ liệu mới được ghi vào sổ thẻ kho chi nhánh.<br>
                        • Bảng ma trận chi tiết và file bảng tính được bảo mật riêng cho Quản trị viên.
                    </div>
                </div>
                """, unsafe_allow_html=True)

                col_form, col_history = st.columns([1, 1.25], gap="large")

                with col_form:
                    with st.container(border=True):
                        st.write("#### ✍️ Tạo Phiếu Đề Xuất Lệnh Kho")
                        st.caption("Nhập thông tin xuất khui dùng hoặc nhận hàng xe tổng tại quầy.")

                        matrix_df_items = get_stock_matrix_df(stock_year, stock_month)
                        item_choices = [f"{row['Mã NL']} — {row['Tên mặt hàng (Quy cách)']}" for _, row in matrix_df_items.iterrows()]

                        with st.form("staff_stock_request_form", clear_on_submit=True):
                            e_date = st.date_input("Ngày phát sinh lệnh", value=business_today())
                            selected_item_str = st.selectbox("Chọn mặt hàng & quy cách đóng gói", item_choices)
                            selected_ing_id = selected_item_str.split(" — ")[0]

                            action_type = st.radio(
                                "Loại thao tác đề xuất",
                                [
                                    ("OUT", "📤 Xuất quầy bar sử dụng (Khui thùng / kiện / dây / bình)"),
                                    ("IN", "📥 Nhập hàng từ xe tổng về quầy (Nhận hàng PO)")
                                ],
                                format_func=lambda x: x[1]
                            )

                            e_qty = st.number_input("Số lượng đề xuất (Thùng / Kiện / Bình / Dây)", min_value=0.1, max_value=50.0, value=1.0, step=0.5)
                            e_notes = st.text_input("Ghi chú lý do / ca trực", placeholder="Ví dụ: Ca sáng khui dùng quầy trà, Nhận bổ sung 2 kiện")

                            btn_submit_req = st.form_submit_button("Gửi Đề Xuất Lệnh Kho Chờ Quản Lý Duyệt 📤", type="primary", use_container_width=True)

                            if btn_submit_req:
                                res_req = create_stock_request(
                                    business_date=e_date,
                                    ingredient_id=selected_ing_id,
                                    movement_type=action_type[0],
                                    quantity=e_qty,
                                    recorded_by=st.session_state.get("username", "nhanvien"),
                                    user_role=user_role,
                                    notes=e_notes
                                )
                                if res_req["status"] == "SUCCESS":
                                    st.success(res_req["message"])
                                    st.rerun()
                                else:
                                    st.error(res_req["message"])

                with col_history:
                    with st.container(border=True):
                        st.write("#### 📋 Trạng Thái Các Lệnh Kho Của Bạn")
                        st.caption("Theo dõi tiến độ phê duyệt từ Quản lý chi nhánh theo thời gian thực.")

                        my_username = st.session_state.get("username", "nhanvien")
                        my_reqs = get_user_requests(username=my_username, limit=30)
                        if my_reqs:
                            st.dataframe(pd.DataFrame(my_reqs), use_container_width=True, hide_index=True)
                        else:
                            st.info("Hiện bạn chưa gửi đề xuất lệnh kho nào trong ca này.")

        else:
            # ==============================================================================
            # GIAO DIỆN DÀNH CHO QUẢN TRỊ VIÊN / QUẢN LÝ / CHỦ QUÁN (ADMIN)
            # ==============================================================================
            pending_list = get_pending_requests()
            pending_count = len(pending_list)
            inbox_tab_label = f"📋 Duyệt Lệnh Kho ({pending_count} chờ)" if pending_count > 0 else "📋 Duyệt Lệnh Kho"

            tab_inbox, tab_matrix, tab_sales, tab_recon = st.tabs([
                inbox_tab_label,
                "📦 Sổ Thẻ Kho Ma Trận (31 Ngày Tháng 10/2026)",
                "📊 Báo Cáo Doanh Thu & Bán Hàng POS",
                "🔍 Đối Soát Thất Thoát Kho Chi Tiết"
            ])

            # TAB 1: DUYỆT LỆNH KHO (MAKER - CHECKER INBOX)
            with tab_inbox:
                st.subheader("📋 Hòm Thư Phê Duyệt Lệnh Xuất / Nhập Kho (Maker - Checker)")
                st.caption("Kiểm duyệt các đề xuất lệnh kho từ nhân viên pha chế quầy bar trước khi ghi nhận chính thức vào sổ thẻ kho 31 ngày.")

                if pending_count == 0:
                    st.success("🎉 Tất cả các yêu cầu từ nhân viên đều đã được xử lý xong! Không còn lệnh nào đang chờ duyệt.")
                else:
                    st.info(f"Đang có **{pending_count}** đề xuất lệnh kho từ nhân viên quầy bar cần bạn kiểm duyệt:")
                    for req in pending_list:
                        with st.container(border=True):
                            c_info, c_action = st.columns([2.7, 1.3])
                            with c_info:
                                st.markdown(f"**Lệnh #{req['id']} — {req['type_vi']}** | Ngày phát sinh: `{req['business_date']}`")
                                st.write(f"• **Mặt hàng:** `{req['ingredient_name']}` (Mã: `{req['ingredient_id']}`)")
                                st.write(f"• **Số lượng:** **{req['quantity']}** (Thùng/Kiện/Bình/Dây) | **Nhân viên tạo:** `{req['recorded_by']}` ({req['created_at']})")
                                if req['notes'] and req['notes'] != "—":
                                    st.caption(f"📝 *Ghi chú:* {req['notes']}")
                            with c_action:
                                st.write("")
                                btn_col1, btn_col2, btn_col3 = st.columns(3)
                                with btn_col1:
                                    if st.button("✅ Duyệt", key=f"btn_app_{req['id']}", type="primary", use_container_width=True):
                                        ok, msg = approve_stock_request(req["id"], admin_username=st.session_state.get("username", "admin"))
                                        st.session_state["stock_flash_msg"] = {"type": "success" if ok else "error", "text": msg}
                                        st.rerun()
                                with btn_col2:
                                    if st.button("❌ Từ chối", key=f"btn_rej_{req['id']}", use_container_width=True):
                                        ok, msg = reject_stock_request(req["id"], admin_username=st.session_state.get("username", "admin"), reason="Quản lý từ chối")
                                        st.session_state["stock_flash_msg"] = {"type": "info" if ok else "error", "text": msg}
                                        st.rerun()
                                with btn_col3:
                                    if st.button("🗑️ Xóa", key=f"btn_del_req_{req['id']}", use_container_width=True):
                                        ok, msg = delete_stock_movement(req["id"], admin_username=st.session_state.get("username", "admin"))
                                        st.session_state["stock_flash_msg"] = {"type": "success" if ok else "error", "text": msg}
                                        st.rerun()

                st.divider()
                with st.expander("🕒 Lịch Sử Các Lệnh Đề Xuất Của Toàn Bộ Nhân Viên (Sửa & Xóa Lệnh)", expanded=False):
                    all_reqs = get_user_requests(username=None, limit=50)
                    if all_reqs:
                        st.dataframe(pd.DataFrame(all_reqs), use_container_width=True, hide_index=True)

                        c_del_hist1, c_del_hist2 = st.columns([3, 1])
                        with c_del_hist1:
                            hist_options = [f"#{r['Mã lệnh'].replace('#', '')} — {r['Mặt hàng']} ({r['Loại lệnh']} {r['Số lượng']}) — {r['Trạng thái']}" for r in all_reqs]
                            sel_hist_item = st.selectbox("Chọn lệnh kho cần XÓA BỎ:", hist_options, key="sel_hist_to_del")
                            sel_hist_id = int(sel_hist_item.split(" — ")[0].replace("#", ""))
                        with c_del_hist2:
                            st.write("")
                            st.write("")
                            if st.button("🗑️ XÓA LỆNH NÀY", type="secondary", use_container_width=True, key="btn_del_hist_req"):
                                ok, msg = delete_stock_movement(sel_hist_id, admin_username=st.session_state.get("username", "admin"))
                                st.session_state["stock_flash_msg"] = {"type": "success" if ok else "error", "text": msg}
                                st.rerun()
                    else:
                        st.caption("Chưa có lịch sử lệnh kho nào.")

            # TAB 2: SỔ THẺ KHO MA TRẬN 31 NGÀY (THÁNG 10/2026)
            with tab_matrix:
                st.subheader(f"📦 Sổ kho tháng {stock_month}/{stock_year}")
                st.caption("Chi nhánh Mixue 39 Tôn Quang Phiệt · Sổ kho chuẩn hóa theo quy cách đóng gói F&B (Thùng/Kiện/Dây/Bình).")

                matrix_df = get_stock_matrix_df(stock_year, stock_month)

                # Top KPI metrics
                kpi1, kpi2, kpi3, kpi4 = st.columns(4, gap="medium")
                with kpi1:
                    st.metric("Tổng mặt hàng theo dõi", f"{len(matrix_df)} mặt hàng", help="Quy cách đóng gói chuẩn F&B Mixue")
                with kpi2:
                    total_in = pd.to_numeric(matrix_df["Tổng nhập"], errors="coerce").fillna(0).sum()
                    st.metric("Tổng nhập trong tháng", f"{total_in:,.1f} kiện/thùng", help="Số lượng nhập từ tổng kho")
                with kpi3:
                    total_out = pd.to_numeric(matrix_df["Tổng xuất"], errors="coerce").fillna(0).sum()
                    st.metric("Tổng xuất dùng quầy bar", f"{total_out:,.1f} kiện/thùng", help="Số lượng khui dùng tại quầy pha chế")
                with kpi4:
                    total_stock = pd.to_numeric(matrix_df["Tồn sổ sách"], errors="coerce").fillna(0).sum()
                    st.metric("Tồn kho hiện tại", f"{total_stock:,.1f} kiện/thùng", help="Tồn lũy kế hiện có tại cửa hàng")

                st.divider()

                col_act, col_filter = st.columns([1.2, 1.8], gap="large")

                with col_act:
                    with st.container(border=True):
                        st.write("#### ⚡ Thao Tác Sửa & Xóa Kho Bằng Tay")
                        act_tab1, act_tab2, act_tab3 = st.tabs(["➕ Thêm Lệnh", "✏️ Sửa / Xóa 1 Ô", "🗑️ Quản Lý Lệnh Kho"])

                        with act_tab1:
                            st.caption("Quản lý/Chủ quán tạo lệnh xuất, nhập hoặc kiểm kê đếm kho (duyệt tự động).")
                            with st.form("admin_stock_entry_form", clear_on_submit=True):
                                e_date = st.date_input("Ngày phát sinh", value=business_today(), key="admin_stock_date")

                                item_choices = [f"{row['Mã NL']} — {row['Tên mặt hàng (Quy cách)']}" for _, row in matrix_df.iterrows()]
                                selected_item_str = st.selectbox("Chọn mặt hàng & quy cách", item_choices, key="admin_stock_item")
                                selected_ing_id = selected_item_str.split(" — ")[0]

                                action_type = st.radio(
                                    "Thao tác kho",
                                    [
                                        ("OUT", "📤 Xuất quầy bar sử dụng (Khui thùng/dây)"),
                                        ("IN", "📥 Nhập hàng từ kho tổng (PO Received)"),
                                        ("ACTUAL_COUNT", "🔍 Kiểm kê thực tế cuối ngày/tuần")
                                    ],
                                    format_func=lambda x: x[1],
                                    key="admin_stock_action"
                                )

                                e_qty = st.number_input("Số lượng (Thùng / Kiện / Bình / Dây)", min_value=0.0, max_value=50.0, value=1.0, step=0.5, key="admin_stock_qty")
                                e_notes = st.text_input("Ghi chú (Tùy chọn)", placeholder="Ví dụ: Quản lý nhận hàng ca chiều", key="admin_stock_notes")

                                btn_stock_save = st.form_submit_button("Lưu Ghi Nhận Trực Tiếp Vào Sổ Kho 🚀", type="primary", use_container_width=True)

                                if btn_stock_save:
                                    res_save = create_stock_request(
                                        business_date=e_date,
                                        ingredient_id=selected_ing_id,
                                        movement_type=action_type[0],
                                        quantity=e_qty,
                                        recorded_by=st.session_state.get("username", "admin"),
                                        user_role=user_role,
                                        notes=e_notes
                                    )
                                    if res_save["status"] == "SUCCESS":
                                        st.session_state["stock_flash_msg"] = {"type": "success", "text": res_save["message"]}
                                        st.rerun()
                                    else:
                                        st.error(res_save["message"])

                        with act_tab2:
                            st.caption("Chọn ô cụ thể trên ma trận để xem giá trị, sửa lại hoặc bấm XÓA về trống.")
                            item_choices_edit = [f"{row['Mã NL']} — {row['Tên mặt hàng (Quy cách)']}" for _, row in matrix_df.iterrows()]
                            edit_item_str = st.selectbox("1. Chọn mặt hàng:", item_choices_edit, key="edit_item_picker")
                            edit_ing_id = edit_item_str.split(" — ")[0]

                            edit_col_options = list(stock_column_map.keys())
                            edit_col_name = st.selectbox("2. Chọn cột / ngày phát sinh:", edit_col_options, key="edit_col_picker")

                            cur_val = get_cell_value(edit_ing_id, edit_col_name, year=stock_year, month=stock_month)
                            if cur_val is not None:
                                st.info(f"📊 Giá trị hiện tại trong ô: **{cur_val:g}** (Thùng/Kiện/Dây)")
                                default_input = float(cur_val)
                            else:
                                st.caption("ℹ️ Ô này hiện đang trống (chưa có số liệu).")
                                default_input = 1.0

                            edit_qty_input = st.number_input("3. Nhập số lượng mới:", min_value=0.0, max_value=100.0, value=default_input, step=0.5, key="edit_qty_val_num")

                            col_btn_save, col_btn_del = st.columns(2)
                            with col_btn_save:
                                if st.button("💾 Lưu Sửa Số Lượng", type="primary", use_container_width=True, key="btn_save_cell_single"):
                                    ok, msg = update_stock_cell_manually(
                                        ingredient_id=edit_ing_id,
                                        column_name=edit_col_name,
                                        new_value=edit_qty_input,
                                        updated_by=st.session_state.get("username", "admin"), year=stock_year, month=stock_month
                                    )
                                    st.session_state["stock_flash_msg"] = {"type": "success" if ok else "error", "text": msg}
                                    st.rerun()

                            with col_btn_del:
                                if st.button("🗑️ XÓA Ô NÀY (Về Trống)", type="secondary", use_container_width=True, key="btn_del_cell_single"):
                                    ok, msg = update_stock_cell_manually(
                                        ingredient_id=edit_ing_id,
                                        column_name=edit_col_name,
                                        new_value="",
                                        updated_by=st.session_state.get("username", "admin"), year=stock_year, month=stock_month
                                    )
                                    st.session_state["stock_flash_msg"] = {"type": "success" if ok else "error", "text": msg}
                                    st.rerun()

                        with act_tab3:
                            st.caption("Xem danh sách tất cả các lệnh kho đã ghi nhận. Chọn một lệnh để Sửa số lượng hoặc Xóa vĩnh viễn.")
                            all_movs_tab3 = get_all_movements_detailed(limit=100)
                            if all_movs_tab3:
                                mov_map = {
                                    f"#{m['id']} [{m['business_date']}] {m['ingredient_name']} — {m['type_label']} {m['quantity']:g} (Bởi: {m['recorded_by']})": m
                                    for m in all_movs_tab3
                                }
                                sel_mov_label = st.selectbox("Chọn lệnh kho cần thao tác:", list(mov_map.keys()), key="sel_mov_to_act_tab3")
                                sel_mov = mov_map[sel_mov_label]

                                st.markdown(f"""
                                <div style="background:#f1f5f9; border-radius:6px; padding:10px; font-size:13px; margin-bottom:10px; border:1px solid #cbd5e1;">
                                    <b>Mã lệnh:</b> #{sel_mov['id']} | <b>Ngày:</b> {sel_mov['business_date']}<br>
                                    <b>Mặt hàng:</b> {sel_mov['ingredient_name']}<br>
                                    <b>Loại thao tác:</b> {sel_mov['type_label']} | <b>Số lượng:</b> {sel_mov['quantity']:g}<br>
                                    <b>Người tạo:</b> {sel_mov['recorded_by']} | <b>Người duyệt:</b> {sel_mov['approved_by']}
                                </div>
                                """, unsafe_allow_html=True)

                                c_up_qty, c_del_mov = st.columns(2)
                                with c_up_qty:
                                    new_m_qty = st.number_input("Số lượng mới:", min_value=0.1, max_value=100.0, value=float(sel_mov['quantity']), step=0.5, key="new_m_qty_val_tab3")
                                    if st.button("✏️ Lưu Số Lượng", type="primary", use_container_width=True, key="btn_update_mov_qty_tab3"):
                                        ok, msg = update_stock_movement(sel_mov['id'], new_m_qty, admin_username=st.session_state.get("username", "admin"))
                                        st.session_state["stock_flash_msg"] = {"type": "success" if ok else "error", "text": msg}
                                        st.rerun()

                                with c_del_mov:
                                    st.write("")
                                    st.write("")
                                    if st.button("🗑️ XÓA LỆNH NÀY", type="secondary", use_container_width=True, key="btn_del_mov_perm_tab3"):
                                        ok, msg = delete_stock_movement(sel_mov['id'], admin_username=st.session_state.get("username", "admin"))
                                        st.session_state["stock_flash_msg"] = {"type": "success" if ok else "error", "text": msg}
                                        st.rerun()
                            else:
                                st.info("Chưa có lệnh kho nào trong hệ thống.")

                with col_filter:
                    with st.container(border=True):
                        st.write("#### 📑 Bảng Điều Khiển Ma Trận & Xuất File")
                        st.caption("Xuất file bảng tính Excel chuẩn nhận diện Google Sheet hoặc lọc theo tuần.")

                        cf1, cf2 = st.columns([1.5, 1])
                        with cf1:
                            view_mode = st.selectbox(
                                "Chọn phạm vi hiển thị cột:",
                                list(stock_views)
                            )
                        with cf2:
                            # Built only when the button is pressed (it costs seconds on a small server).
                            st.download_button(
                                label="📥 Tải File Excel (.xlsx)",
                                data=lambda y=stock_year, m=stock_month: generate_excel_export(y, m),
                                on_click="ignore",
                                file_name=f"Mixue_Kho_{stock_year}_{stock_month}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )

                        st.markdown("""
                        <div style="font-size: 12px; color: #475569; background: #f8fafc; padding: 10px; border-radius: 6px; border: 1px solid #e2e8f0; line-height: 1.5;">
                            🎨 <strong>Quy ước màu sắc chuẩn sổ kho Mixue:</strong><br>
                            • <span style="background:#e0f2fe; padding:2px 6px; border-radius:4px; font-weight:bold; color:#0369a1;">Màu xanh dương:</span> Cột <b>Nhập hàng</b> từ kho tổng.<br>
                            • <span style="background:#dcfce7; padding:2px 6px; border-radius:4px; font-weight:bold; color:#15803d;">Màu xanh lá:</span> Cột <b>Chốt tồn</b> sau mỗi chu kỳ tuần.<br>
                            • <span>Cột T2 - CN:</span> Lượng xuất dùng pha chế tại quầy theo từng ngày.
                        </div>
                        """, unsafe_allow_html=True)

                st.write(f"#### 📋 Sổ kho tháng {stock_month}/{stock_year}")
                st.caption("💡 **Chế độ sửa trực tiếp bằng tay:** Bạn có thể bấm đúp chuột vào bất kỳ ô số liệu nào trên bảng để gõ số sửa trực tiếp như Excel, sau đó bấm nút **'💾 Lưu Các Ô Đã Sửa Vào Sổ Kho'** bên dưới.")

                cols_show = stock_views[view_mode] or [c for c in matrix_df.columns if c != 'Mã NL']

                disabled_cols = [c for c in cols_show if c not in stock_column_map]

                # Ràng buộc dữ liệu: chỉ cho phép nhập số dương/không âm (>= 0.0)
                stock_col_config = {
                    c: st.column_config.NumberColumn(
                        min_value=0.0,
                        step=0.5,
                        format="%.1f"
                    )
                    for c in cols_show if c in stock_column_map
                }

                edited_matrix = st.data_editor(
                    matrix_df[cols_show],
                    use_container_width=True,
                    hide_index=True,
                    disabled=disabled_cols,
                    column_config=stock_col_config,
                    key=f"stock_editor_{stock_year}_{stock_month}_{view_mode}"
                )

                c_save_col, c_hint_col = st.columns([1.5, 3], gap="medium")
                with c_save_col:
                    btn_save_manual = st.button("💾 Lưu Các Ô Đã Sửa Vào Sổ Kho", type="primary", use_container_width=True)
                    if btn_save_manual:
                        editor_key = f"stock_editor_{stock_year}_{stock_month}_{view_mode}"
                        editor_session_data = st.session_state.get(editor_key, {})
                        res_update = update_stock_matrix_from_editor(
                            edited_df=edited_matrix,
                            original_df=matrix_df,
                            updated_by=st.session_state.get("username", "admin"),
                            editor_session_data=editor_session_data, year=stock_year, month=stock_month
                        )
                        if res_update["updated_count"] > 0:
                            st.session_state["stock_flash_msg"] = {
                                "type": "success",
                                "text": f"Đã lưu thành công {res_update['updated_count']} ô sửa đổi vào sổ kho! Toàn bộ công thức tồn sổ sách đã được tính toán lại."
                            }
                            if editor_key in st.session_state:
                                st.session_state[editor_key] = {"edited_rows": {}}
                            st.rerun()
                        else:
                            st.info("ℹ️ Không phát hiện thay đổi nào trên bảng. Nhấp đúp chuột vào ô để sửa số, nhấn Enter rồi bấm Lưu.")
                with c_hint_col:
                    st.caption("💡 *Mẹo sửa trên bảng:* Nhấp đúp chuột vào bất kỳ ô số liệu nào (trừ các cột công thức tính tự động), gõ số mới, nhấn **Enter**, sau đó bấm **'Lưu Các Ô Đã Sửa Vào Sổ Kho'**.")

                with st.expander("📑 Bảng Chi Tiết Tất Cả Lệnh Kho Đã Ghi Sổ — Tra Cứu & Đối Soát", expanded=False):
                    all_movs_list = get_all_movements_detailed(limit=100)
                    if all_movs_list:
                        movs_df = pd.DataFrame(all_movs_list)
                        show_movs_df = movs_df[["id", "business_date", "ingredient_name", "type_label", "quantity", "status", "recorded_by", "approved_by", "notes"]].rename(
                            columns={
                                "id": "Mã",
                                "business_date": "Ngày",
                                "ingredient_name": "Mặt hàng",
                                "type_label": "Loại lệnh",
                                "quantity": "Số lượng",
                                "status": "Trạng thái",
                                "recorded_by": "Người tạo",
                                "approved_by": "Người duyệt",
                                "notes": "Ghi chú"
                            }
                        )
                        st.dataframe(show_movs_df, use_container_width=True, hide_index=True)
                    else:
                        st.caption("Chưa có lệnh kho nào.")

            # TAB 4: BÁO CÁO DOANH THU & BÁN HÀNG POS
            with tab_sales:
                st.subheader("📊 Báo cáo Doanh thu Hoạt động Chi nhánh Mixue 39 Tôn Quang Phiệt")
                st.caption("Dữ liệu kinh doanh thực tế tích lũy 30 ngày qua tại quầy POS và hệ thống kiểm kê kho cửa hàng 2132.")

                sales_df = get_cached_sales()

                if not sales_df.empty:
                    col1, col2, col3, col4 = st.columns(4, gap="medium")
                    total_rev = sales_df["revenue_vnd"].sum()
                    total_cups = sales_df["quantity_sold"].sum()
                    avg_cups_day = total_cups / sales_df["business_date"].nunique()
                    num_skus = sales_df["sku_id"].nunique()

                    with col1:
                        st.metric("Tổng doanh thu tích lũy", f"{total_rev:,.0f} đ", help="Doanh thu tích lũy trong 30 ngày qua")
                    with col2:
                        st.metric("Tổng sản lượng phục vụ", f"{total_cups:,.0f} ly", help="Tổng số ly phục vụ thành công")
                    with col3:
                        st.metric("Sản lượng trung bình", f"{avg_cups_day:.1f} ly/ngày", help="Bình quân mỗi ngày")
                    with col4:
                        st.metric("Quy mô thực đơn", f"{num_skus} món", help="Số lượng mặt hàng trên menu quán")

                    st.divider()

                    c1, c2 = st.columns([3, 2], gap="medium")
                    with c1:
                        with st.container(border=True):
                            st.write("#### 📅 Xu hướng Sản lượng Bán theo Ngày (Mixue 39 Tôn Quang Phiệt)")
                            daily_agg = sales_df.groupby("business_date")["quantity_sold"].sum().reset_index()
                            daily_agg.columns = ["Ngày kinh doanh", "Số ly bán"]
                            daily_agg["Ngày kinh doanh"] = pd.to_datetime(daily_agg["Ngày kinh doanh"])
                            quick_chart(daily_agg, "Ngày kinh doanh", "Số ly bán", "line", "#E60012")

                    with c2:
                        with st.container(border=True):
                            st.write("#### 🏆 Top 10 Món Bán Chạy Nhất Tại Quán")
                            top10 = sales_df.groupby(["sku_id", "sku_name"])["quantity_sold"].sum().reset_index()
                            top10.columns = ["Mã món", "Tên món", "Tổng số ly bán"]
                            top10 = top10.sort_values(by="Tổng số ly bán", ascending=False).head(10)
                            st.dataframe(top10, use_container_width=True, hide_index=True)

                    st.divider()

                    # --- BÁO CÁO DOANH THU THEO TỪNG NGÀY ---
                    st.write("### 💰 Báo cáo Chi tiết Doanh thu theo Ngày (30 Ngày Gần Nhất)")
                    st.caption("Bảng kê tổng hợp doanh số thực thu, số ly bán, giá bình quân mỗi ly và món bán chạy nhất theo từng ngày kinh doanh.")

                    daily_rev_df = get_cached_daily_revenue()
                    if not daily_rev_df.empty:
                        r_max_row = daily_rev_df.loc[daily_rev_df["revenue_vnd"].idxmax()]
                        r_min_row = daily_rev_df.loc[daily_rev_df["revenue_vnd"].idxmin()]
                        avg_daily_rev = daily_rev_df["revenue_vnd"].mean()
                        overall_aov = daily_rev_df["revenue_vnd"].sum() / daily_rev_df["quantity_sold"].sum()

                        c_rev1, c_rev2, c_rev3, c_rev4 = st.columns(4, gap="medium")
                        with c_rev1:
                            st.metric("🏆 Doanh thu cao nhất", f"{r_max_row['revenue_vnd']:,.0f} đ", f"{r_max_row['business_date']} ({r_max_row['day_of_week']})")
                        with c_rev2:
                            st.metric("📉 Doanh thu thấp nhất", f"{r_min_row['revenue_vnd']:,.0f} đ", f"{r_min_row['business_date']} ({r_min_row['day_of_week']})")
                        with c_rev3:
                            st.metric("💵 Doanh thu bình quân", f"{avg_daily_rev:,.0f} đ/ngày", help="Doanh thu bình quân mỗi ngày")
                        with c_rev4:
                            st.metric("🥤 Giá bán trung bình / ly", f"{overall_aov:,.0f} đ", help="Doanh thu tích lũy / Tổng ly bán")

                        c_chart1, c_chart2 = st.columns([3, 2], gap="medium")
                        with c_chart1:
                            with st.container(border=True):
                                st.write("##### 📊 Biểu đồ Doanh thu Từng Ngày (VND)")
                                chart_rev = daily_rev_df.copy()
                                chart_rev["Ngày"] = pd.to_datetime(chart_rev["business_date"])
                                chart_rev = chart_rev.rename(columns={"revenue_vnd": "Doanh thu (VND)"})
                                quick_chart(chart_rev, "Ngày", "Doanh thu (VND)", "bar", "#E60012")

                        with c_chart2:
                            with st.container(border=True):
                                st.write("##### 📈 Tăng trưởng Doanh số so với Hôm trước (% DoD)")
                                dod_df = daily_rev_df.copy()
                                dod_df["Ngày"] = pd.to_datetime(dod_df["business_date"])
                                dod_df = dod_df.rename(columns={"dod_growth_pct": "Tăng trưởng (%)"})
                                quick_chart(dod_df, "Ngày", "Tăng trưởng (%)", "line", "#FFB800")

                        # Bảng kê chi tiết 30 ngày
                        st.write("##### 📋 Bảng Kê Doanh Thu & Món Bán Chạy Từng Ngày")
                        table_display = daily_rev_df.copy()
                        table_display["Ngày kinh doanh"] = table_display["business_date"]
                        table_display["Thứ"] = table_display["day_of_week"]
                        table_display["Doanh thu (đ)"] = table_display["revenue_vnd"].map(lambda x: f"{x:,.0f} đ")
                        table_display["Số ly bán"] = table_display["quantity_sold"].map(lambda x: f"{x:,.0f} ly")
                        table_display["Giá TB/ly"] = table_display["avg_price_per_cup"].map(lambda x: f"{x:,.0f} đ")
                        table_display["Tăng trưởng (DoD)"] = table_display["dod_growth_pct"].map(
                            lambda x: f"+{x:.1f}%" if x > 0 else (f"{x:.1f}%" if x < 0 else "0.0%")
                        )
                        table_display["Món bán chạy nhất ngày"] = table_display["top_seller"]

                        st.dataframe(
                            table_display[["Ngày kinh doanh", "Thứ", "Doanh thu (đ)", "Số ly bán", "Giá TB/ly", "Tăng trưởng (DoD)", "Món bán chạy nhất ngày"]].sort_values(by="Ngày kinh doanh", ascending=False),
                            use_container_width=True,
                            hide_index=True
                        )
                else:
                    st.warning("Chưa tìm thấy dữ liệu bán hàng trong cơ sở dữ liệu của quán.")

            # TAB 4: ĐỐI SOÁT THẤT THOÁT KHO CHI TIẾT
            with tab_recon:
                st.subheader("🔍 Đối soát Thất thoát Kho Chi tiết: Tiêu thụ Lý thuyết (BOM) vs Tồn Thực tế Kiểm kê")
                st.caption("Đối soát tự động giữa tổng nhập, lượng tiêu hao theo công thức pha chế BOM và số tồn thực tế kiểm kê cuối kỳ.")
                if st.button("📊 Tải bảng đối soát kho chi tiết", key="btn_load_recon", type="primary") or "recon_df" in st.session_state:
                    if "recon_df" not in st.session_state:
                        st.session_state["recon_df"] = get_cached_reconciliation_data()
                    recon_df = st.session_state["recon_df"]

                    display_recon = recon_df.copy().rename(columns={
                        "ingredient_id": "Mã nguyên liệu",
                        "ingredient_name": "Tên nguyên liệu",
                        "total_purchased": "Tổng nhập",
                        "theoretical_usage": "Tiêu hao theo BOM",
                        "actual_stock_count": "Tồn thực tế kiểm kê",
                        "variance": "Chênh lệch kho",
                        "variance_pct": "Tỷ lệ lệch (%)",
                        "unit": "Đơn vị"
                    })
                    st.dataframe(
                        display_recon[["Mã nguyên liệu", "Tên nguyên liệu", "Tổng nhập", "Tiêu hao theo BOM", "Tồn thực tế kiểm kê", "Chênh lệch kho", "Tỷ lệ lệch (%)", "Đơn vị"]].head(25),
                        use_container_width=True,
                        hide_index=True
                    )


    # ==============================================================================
    # TAB 2: DỰ BÁO NHU CẦU D+1
    # ==============================================================================
    elif section == "Dự báo":
        st.subheader("📈 Dự báo Nhu cầu Tiêu thụ Ngày mai (D+1) & Kết quả Kiểm chứng Backtest")
        st.caption("Dự báo theo số ly, doanh thu gần đây và thời tiết trong giờ bán. Chỉ áp dụng điều chỉnh thời tiết khi kiểm chứng tốt hơn dự báo nền.")

        col_bt1, col_bt2 = st.columns([1.15, 1], gap="medium")
        with col_bt1:
            with st.container(border=True):
                st.write("#### 🎯 So sánh Độ chính xác Các Mô hình Dự báo")
                benchmark = cached_backtest(agent.forecast_engine, (datetime.now(VN).date() - pd.Timedelta(days=1)).isoformat())
                st.info(f"**Giai đoạn kiểm chứng mô hình nền:** {benchmark.get('evaluation_period', 'Chưa đủ lịch sử')}\n\n**Mô hình nền được chọn:** `{benchmark.get('best_model', 'Chưa xác định')}`")

                bt_table = []
                for m_name, v in benchmark.get("aggregate_metrics", {}).items():
                    bt_table.append({
                        "Mô hình dự báo": m_name,
                        "Sai số tuyệt đối (MAE)": f"{v['MAE']} ly",
                        "Tỷ lệ sai số (WAPE)": f"{v['WAPE_pct']}%",
                        "Độ lệch tổng thể (Bias)": f"{v['Bias_pct']}%",
                        "Đánh giá chuyên môn": "Sai số thấp nhất" if m_name == benchmark['best_model'] else "Mô hình đối chiếu"
                    })
                st.dataframe(pd.DataFrame(bt_table), use_container_width=True, hide_index=True)

        with col_bt2:
            with st.container(border=True):
                st.write("#### ⚙️ Thiết lập Dự báo Ngày mai (D+1)")
                target_date_input = st.date_input("Ngày cần dự báo", value=datetime.now(VN).date() + pd.Timedelta(days=1), key="fc_date_picker_vi")
                model_choice_map = {
                    "Tự động chọn mô hình tối ưu nhất (Auto)": "auto",
                    "Trung bình trượt 7 ngày (Moving Average)": "moving_average",
                    "Chu kỳ tuần trước (Seasonal Naive)": "seasonal_naive",
                    "Trung bình theo thứ trong tuần": "day_of_week_ma"
                }
                selected_model_label = st.selectbox("Chọn giải thuật dự báo", list(model_choice_map.keys()))
                selected_model_val = model_choice_map[selected_model_label]

                if st.button("🚀 Chạy Mô hình Dự báo", key="run_fc_btn_vi", type="primary", use_container_width=True):
                    with st.spinner("Đang tính toán dự báo sản lượng cho toàn bộ 39 món thực đơn..."):
                        fc_res = agent.forecast_engine.forecast_demand(target_date_input, horizon_days=1, model=selected_model_val)
                        st.session_state.pop('latest_forecast_vi', None)
                        if fc_res.empty:
                            st.warning('Chưa có lịch sử bán hàng trước ngày này để dự báo.')
                        else:
                            st.session_state["latest_forecast_vi"] = fc_res
                            st.success(f"Đã lập dự báo thành công cho toàn bộ {len(fc_res)} món!")

        # Hiển thị bảng dự báo
        if "latest_forecast_vi" in st.session_state:
            st.divider()
            fc_df = st.session_state["latest_forecast_vi"].copy()
            total_pred_cups = fc_df["predicted_qty"].sum()
            render_forecast_context(fc_df.attrs.get('forecast_context', {}))

            result_date = fc_df['target_date'].iloc[0]
            st.write(f"#### 📋 Bảng Dự báo Sản lượng Menu Ngày {result_date.strftime('%d/%m/%Y')} (Tổng dự kiến: **{total_pred_cups:,.0f} ly**)")

            fc_display = fc_df.rename(columns={
                "sku_id": "Mã món",
                "sku_name": "Tên món",
                "predicted_qty": "Dự báo (Ly)",
                "lower_bound": "Ước lượng tối thiểu",
                "upper_bound": "Ước lượng tối đa",
                "model_used": "Mô hình áp dụng",
                "confidence": "Độ tin cậy"
            })

            conf_map = {"HIGH": "Cao 🟢", "MEDIUM": "Trung bình 🟡", "LOW": "Thấp 🔴"}
            fc_display["Độ tin cậy"] = fc_display["Độ tin cậy"].map(lambda x: conf_map.get(x, x))
            st.caption('Các mức thấp/cao chỉ để tham khảo từ dao động lịch sử, không phải giới hạn chắc chắn của số ly thực bán.')

            st.dataframe(
                fc_display[["Mã món", "Tên món", "Dự báo (Ly)", "Ước lượng tối thiểu", "Ước lượng tối đa", "Độ tin cậy"]].sort_values(by="Dự báo (Ly)", ascending=False),
                use_container_width=True,
                hide_index=True
            )


    # ==============================================================================
    # TAB 3: KẾ HOẠCH SƠ CHẾ TOPPING
    # ==============================================================================
    elif section == "Sơ chế":
        st.subheader("🥣 Kế hoạch Sơ chế Topping & Nấu Trà theo Mẻ Chuẩn Mixue")
        st.caption("Tự động làm tròn số lượng theo quy cách mẻ thực tế tại quầy, tính toán đệm an toàn và tuân thủ thời gian bảo quản SOP Mixue.")

        col_p1, col_p2 = st.columns([1, 1.85], gap="medium")
        with col_p1:
            with st.container(border=True):
                buffer_val = st.slider("Tỷ lệ đệm an toàn (Buffer)", min_value=0, max_value=30, value=10, step=5, format="%d%%") / 100.0
                prep_date = st.date_input("Ngày thực hiện sơ chế", value=datetime.now(VN).date(), key="prep_date_in_vi")
                with st.expander('Định mức đầu ra tạm tính'):
                    pearl_yield = st.number_input('1 kg trân châu khô cho bao nhiêu gram thành phẩm đã ráo?',
                                                 min_value=1000, max_value=5000, value=2000, step=100,
                                                 key='pearl_yield_estimate')
                    st.caption('Giả định để lập kế hoạch, chưa phải số đo hay quy chuẩn chính thức. Thay số này rồi tính lại để so sánh.')

                if st.button("⚡ Tính toán Kế hoạch Sơ chế", key="calc_prep_btn_vi", type="primary", use_container_width=True):
                    res = agent.tool_optimize_topping_prep(target_date=prep_date.isoformat(), buffer_pct=buffer_val, pearl_yield_g=float(pearl_yield))
                    st.session_state.pop('prep_plan_vi', None)
                    if res.get('status') == 'NO_DATA':
                        st.warning(res['message'])
                    else:
                        st.session_state["prep_plan_vi"] = res

        with col_p2:
            st.markdown("""
            <div class="sop-card">
                <h4>Chuẩn bị theo từng đợt, đối chiếu đúng nguyên liệu</h4>
                <ul>
                    <li><strong>TP02 là trân châu nguyên vị đã nấu</strong>, tính bằng gram thành phẩm; TP07/TP08 là trà đã ủ, tính bằng ml.</li>
                    <li>Định mức đầu ra mỗi mẻ hiện là <strong>ước lượng</strong>, chưa phải số đo thực tế tại quán.</li>
                    <li>Không nấu toàn bộ lượng cả ngày từ đầu ca. Đối chiếu bán thực tế trước đợt tiếp theo.</li>
                    <li>Trân châu nguyên vị dùng trong <strong>4 giờ</strong> theo hướng dẫn đang có. Các nguyên liệu khác xem đúng công thức và SOP tương ứng.</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

        if "prep_plan_vi" in st.session_state:
            plan = st.session_state["prep_plan_vi"]
            render_forecast_context(plan.get('forecast_context', {}))
            st.info(plan.get('prep_policy', 'Chia đợt nấu theo hạn dùng, đối chiếu bán thực tế trước khi nấu tiếp.'))
            if plan.get('yield_assumption'):
                st.warning(plan['yield_assumption'])
            pearl_line = next((line for line in plan.get('recommendations', []) if line['ingredient_id'] == 'TP02'), None)
            if pearl_line and pearl_line.get('estimated_raw_input_g') is not None:
                st.info(f"Trân châu khô tạm tính: **{pearl_line['estimated_raw_input_g']/1000:g} kg cả ngày**, "
                        f"**{(pearl_line.get('initial_raw_input_g') or 0)/1000:g} kg đợt đầu**. "
                        f"Số mẻ có thể khoảng {pearl_line['batch_count_range'][0]}–{pearl_line['batch_count_range'][1]} theo khoảng sản lượng giả định.")
            st.divider()
            v_status = plan["verification"]["status"]
            if v_status == "VERIFIED":
                st.success(f"Đạt kiểm tra số lượng, đơn vị và làm tròn theo định mức đang dùng · Dự thảo `{plan['draft_plan_id']}`. Định mức ước lượng vẫn cần quản lý đối chiếu.")
            else:
                st.error("❌ **KẾ HOẠCH BỊ TỪ CHỐI DO VI PHẠM QUY CHUẨN**")

            prep_table = pd.DataFrame(plan["recommendations"])
            prep_table_display = prep_table.rename(columns={
                "ingredient_id": "Mã topping",
                "ingredient_name": "Tên topping / Trà",
                "preparation_action": "Cách chuẩn bị",
                "batch_size": "Thành phẩm/mẻ (tạm tính)",
                "forecasted_demand": "Nhu cầu dự báo",
                "num_batches": "Số mẻ ước tính",
                "initial_prep_qty": "Gợi ý nấu đợt đầu",
                "review_after": "Đánh giá lại lúc",
                "recommended_prep_qty": "Lượng nấu đề xuất",
                "unit": "Đơn vị",
                "expected_waste_qty": "Ước tính hủy thừa",
                "risk_level": "Nguy cơ hao hụt",
                "shelf_life_rule": "Hạn dùng theo SOP"
            })

            risk_map = {"LOW": "Thấp 🟢", "MEDIUM": "Trung bình 🟡", "HIGH": "Cao 🔴"}
            prep_table_display["Nguy cơ hao hụt"] = prep_table_display["Nguy cơ hao hụt"].map(lambda x: risk_map.get(x, x))

            st.dataframe(
                prep_table_display[[column for column in ["Mã topping", "Tên topping / Trà", "Cách chuẩn bị", "Thành phẩm/mẻ (tạm tính)", "Nhu cầu dự báo", "Số mẻ ước tính", "Lượng nấu đề xuất", "Gợi ý nấu đợt đầu", "Đánh giá lại lúc", "Đơn vị", "Ước tính hủy thừa", "Nguy cơ hao hụt", "Hạn dùng theo SOP"] if column in prep_table_display]],
                use_container_width=True,
                hide_index=True
            )

            # Phê duyệt theo thẩm quyền
            with st.container(border=True):
                c_app1, c_app2 = st.columns([2, 1], gap="medium")
                with c_app1:
                    st.info(f"**Người thao tác:** {user_name} ({user_badge})\n\n*Lưu ý: Chỉ Quản lý cửa hàng hoặc Chủ quán (Admin) mới có quyền ký duyệt.*")
                with c_app2:
                    if st.button("✍️ Ký duyệt Kế hoạch Sơ chế", key="approve_prep_btn_vi", type="primary", use_container_width=True):
                        app_res = agent.tool_approve_plan(plan["draft_plan_id"], user_role=role_key, user_name=user_name)
                        if app_res.get("is_approved"):
                            st.success(app_res["message"])
                        else:
                            st.error(app_res["message"])

        st.divider()
        st.write("#### 📉 Báo cáo Lịch sử Hao hụt & Tỷ lệ Hủy Topping (30 Ngày qua)")
        waste_df = get_cached_waste()
        if not waste_df.empty:
            waste_display = waste_df.copy().rename(columns={
                "prepared_ingredient_id": "Mã topping",
                "ingredient_name": "Tên topping",
                "total_prepared": "Tổng lượng chuẩn bị",
                "total_wasted": "Tổng lượng đổ bỏ",
                "total_used": "Lượng thực dùng",
                "waste_rate_pct": "Tỷ lệ hủy (%)",
                "unit": "Đơn vị"
            })
            st.dataframe(
                waste_display[["Mã topping", "Tên topping", "Tổng lượng chuẩn bị", "Tổng lượng đổ bỏ", "Lượng thực dùng", "Tỷ lệ hủy (%)", "Đơn vị"]],
                use_container_width=True,
                hide_index=True
            )


    # ==============================================================================
    # TAB 4: DỰ THẢO ĐƠN NHẬP HÀNG (REPLENISHMENT PO)
    # ==============================================================================
    elif section == "Nhập hàng":
        st.subheader("📦 Dự thảo Đơn Đặt hàng & Nhập kho Nguyên liệu (Replenishment PO)")
        st.caption("Tự động rà soát tồn kho hiện tại, thời gian giao hàng (Lead Time) và quy cách bao/gói/thùng của chuỗi Mixue.")

        col_po1, col_po2 = st.columns([1, 1.85], gap="medium")
        with col_po1:
            with st.container(border=True):
                lead_time = st.number_input("Thời gian giao hàng (Lead Time - ngày)", min_value=1, max_value=7, value=2, key="lead_time_in_vi")
                po_date = st.date_input("Ngày đề xuất đặt hàng", value=business_today(), key="po_date_in_vi")

                if st.button("📋 Tạo Dự thảo Đơn Đặt hàng", key="calc_po_btn_vi", type="primary", use_container_width=True):
                    res = agent.tool_optimize_replenishment(target_date=po_date.isoformat(), lead_time_days=lead_time)
                    st.session_state["po_plan_vi"] = res

        with col_po2:
            st.markdown("""
            <div class="sop-card">
                <h4>📦 Quy tắc Đặt hàng Chuỗi Mixue (Master Packaging SOP)</h4>
                <ul>
                    <li><strong>100% Số nguyên Thùng / Kiện:</strong> Nhập hàng theo số nguyên 1, 2, 3... thùng/kiện/cuộn, không nhập lẻ túi theo quy định phân phối kho Mixue.</li>
                    <li><strong>Tự động tách Bán thành phẩm:</strong> Loại trừ các bán thành phẩm tự nấu tại quán (chỉ đặt nguyên liệu thô từ tổng kho Mixue).</li>
                    <li><strong>Kiểm soát Phê duyệt (Human-in-the-loop):</strong> Nghiêm cấm AI tự ý phát hành đơn — bắt buộc Quản lý Bùi Văn Quang hoặc Chủ quán Nguyễn Hạnh Chi ký duyệt.</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

        if "po_plan_vi" in st.session_state and st.session_state["po_plan_vi"]["top_orders"]:
            po_res = st.session_state["po_plan_vi"]
            st.divider()
            st.write(f"#### 📄 Dự thảo Đơn Hàng `{po_res['draft_plan_id']}` (Gồm {po_res['critical_shortage_count']} mặt hàng nguy cấp)")

            po_items = pd.DataFrame(po_res["top_orders"])
            po_display = po_items.copy()

            # Định dạng cột tổng lượng quy đổi và tồn kho kèm đơn vị
            po_display = po_display.reindex(columns=["ingredient_id", "ingredient_name", "ingredient_group", "daily_demand", "current_on_hand", "days_of_stock_remaining", "carton_spec", "display_order", "recommended_order_qty", "unit", "priority"])
            po_display["Tổng quy đổi"] = po_display.apply(
                lambda r: f"{r['recommended_order_qty']:,.0f} {r['unit']}", axis=1
            )
            po_display["Tồn kho"] = po_display.apply(
                lambda r: f"{r['current_on_hand']:,.0f} {r['unit']}", axis=1
            )
            po_display["Nhu cầu/ngày"] = po_display.apply(
                lambda r: f"{r['daily_demand']:,.1f} {r['unit']}", axis=1
            )

            po_display = po_display.rename(columns={
                "ingredient_id": "Mã NL",
                "ingredient_name": "Tên nguyên liệu",
                "ingredient_group": "Nhóm hàng",
                "days_of_stock_remaining": "Số ngày đủ",
                "carton_spec": "Quy cách đóng gói chuẩn Mixue",
                "display_order": "Số lượng đặt (Nguyên thùng/kiện)",
                "priority": "Mức ưu tiên"
            })

            prio_map = {"CRITICAL": "🚨 NGUY CẤP (HẾT HÀNG)", "REORDER": "📦 CẦN NHẬP", "OK": "✅ ĐỦ HÀNG"}
            po_display["Mức ưu tiên"] = po_display["Mức ưu tiên"].map(lambda x: prio_map.get(x, x))

            st.dataframe(
                po_display[["Mã NL", "Tên nguyên liệu", "Nhóm hàng", "Nhu cầu/ngày", "Tồn kho", "Số ngày đủ", "Quy cách đóng gói chuẩn Mixue", "Số lượng đặt (Nguyên thùng/kiện)", "Tổng quy đổi", "Mức ưu tiên"]],
                use_container_width=True,
                hide_index=True
            )

            with st.container(border=True):
                c_po_app1, c_po_app2 = st.columns([2, 1], gap="medium")
                with c_po_app1:
                    st.warning("⚠️ Chỉ Quản lý cửa hàng (Bùi Văn Quang) hoặc Chủ quán (Nguyễn Hạnh Chi) mới có quyền ký duyệt đơn nhập hàng.")
                with c_po_app2:
                    if st.button("✍️ Ký duyệt Đơn Nhập Hàng", key="approve_po_btn_vi", type="primary", use_container_width=True):
                        app_res = agent.tool_approve_plan(po_res["draft_plan_id"], user_role=role_key, user_name=user_name)
                        if app_res.get("is_approved"):
                            st.success(app_res["message"])
                        else:
                            st.error(app_res["message"])


        st.divider()
        if "po_plan_vi" in st.session_state and not st.session_state["po_plan_vi"]["top_orders"]:
            st.info("Tồn kho đủ theo nhu cầu dự báo; không có nguyên liệu cần đặt thêm.")
        st.write("#### Lịch sử đơn nhập hàng đã lưu")
        saved_orders = list_plans("REPLENISHMENT_PO")
        if not saved_orders:
            st.info("Chưa có đơn nhập hàng. Tạo dự thảo để lưu đơn đầu tiên.")
        shown_orders = saved_orders[:8]
        if len(saved_orders) > 8:
            older = {f"{o['plan_id']} · {o['target_date']}": o for o in saved_orders[8:]}
            pick = st.selectbox(f"Đơn cũ hơn ({len(older)})", ["—"] + list(older), key="older_po_pick")
            if pick != "—":
                shown_orders = shown_orders + [older[pick]]
        for order in shown_orders:
            approved = order["status"] == "APPROVED"
            status_label = "Đã duyệt · Chờ nhận hàng" if approved else "Chờ duyệt"
            with st.expander(f"{order['plan_id']} · {order['target_date']} · {status_label}"):
                st.caption(f"Ngày tạo: {order['created_at']} · Thời gian giao: {order.get('lead_time_days', 2)} ngày")
                if approved:
                    st.success(f"Người duyệt: {order['approved_by']} · Lúc: {order['approved_at']}")
                lines = pd.DataFrame([line for line in order["lines"] if line.get("recommended_order_qty", 0) > 0])
                if lines.empty:
                    st.info("Không có nguyên liệu cần đặt trong đơn này.")
                else:
                    details = lines[["ingredient_id", "ingredient_name", "display_order", "carton_spec", "recommended_order_qty", "unit"]].rename(columns={
                        "ingredient_id": "Mã nguyên liệu", "ingredient_name": "Nguyên liệu", "display_order": "Số thùng/kiện",
                        "carton_spec": "Quy cách", "recommended_order_qty": "Tổng lượng", "unit": "Đơn vị"})
                    st.dataframe(details, use_container_width=True, hide_index=True)
                    def order_csv(details=details, order=order, status_label=status_label):
                        export = details.copy()
                        export.insert(0, "Mã đơn", order["plan_id"])
                        export.insert(1, "Ngày đặt", order["target_date"])
                        export.insert(2, "Trạng thái", status_label)
                        export.insert(3, "Người duyệt", order.get("approved_by", ""))
                        export.insert(4, "Thời điểm duyệt", order.get("approved_at", ""))
                        return export.to_csv(index=False).encode("utf-8-sig")
                    st.download_button("Tải phiếu đặt hàng CSV", order_csv, on_click="ignore",
                                       file_name=f"{order['plan_id']}.csv", mime="text/csv", key=f"download_{order['plan_id']}")
                if not approved and st.button("Ký duyệt đơn đã lưu", key=f"approve_{order['plan_id']}"):
                    result = agent.tool_approve_plan(order["plan_id"], user_role=role_key, user_name=user_name)
                    if result.get("is_approved"):
                        st.rerun()
                    else:
                        st.error(result["message"])
        st.caption("Ký duyệt lưu phiếu đặt hàng. Ghi nhận hàng thực nhận tại Sổ kho khi hàng được giao.")

    # ==============================================================================
    # TAB 5: TEM IN NHÃN & CÔNG THỨC PHA CHẾ (BOM)
    # ==============================================================================
    elif section == "Tem & công thức":
        st.subheader("📋 Sổ tay Công thức Pha chế")
        st.caption("Tra cứu định lượng nguyên liệu và hướng dẫn pha chế theo món.")

        with st.container(border=True):
            st.write("#### 🍵 Sổ tay Định lượng Công thức Pha chế (BOM)")
            menu_items_raw = get_cached_menu_list()
            menu_choices = [f"{m[0]} — {m[1]} ({m[2] if m[2] else 'Chuẩn'})" for m in menu_items_raw]
            selected_menu = st.selectbox("Chọn món để xem định lượng", menu_choices)

            if selected_menu:
                selected_sku = selected_menu.split()[0]
                rec_res = agent.tool_decode_recipe_or_sticker(selected_sku)

                if rec_res.get("status") == "SUCCESS" and rec_res.get("recipe_lines"):
                    st.write(f"**Giá niêm yết tại quầy:** `{rec_res.get('selling_price_vnd', 0):,.0f} đ`")
                    bom_df = pd.DataFrame(rec_res["recipe_lines"])
                    bom_df = bom_df.rename(columns={
                        "ingredient_id": "Mã nguyên liệu",
                        "ingredient_name": "Tên nguyên liệu",
                        "quantity": "Định lượng chuẩn",
                        "unit": "Đơn vị"
                    })
                    st.dataframe(
                        bom_df[["Mã nguyên liệu", "Tên nguyên liệu", "Định lượng chuẩn", "Đơn vị"]],
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("Món này đang cập nhật công thức định lượng chi tiết.")

    # ==============================================================================
    # TAB 6: QUẢN LÝ NHÂN VIÊN (CHỈ DÀNH CHO ADMIN)
    # ==============================================================================
    elif section == "👥 Quản lý nhân viên":
        st.subheader("👥 Quản lý Nhân sự & Phân quyền Tài khoản Chi nhánh")
        st.caption("Quản trị danh sách nhân viên Mixue 39 Tôn Quang Phiệt, cấp phát tài khoản mới và quyền reset mật khẩu quầy bar.")

        if notice := st.session_state.pop("employee_notice", None):
            st.success(notice)
        employees = get_all_employees()
        total_emp = sum(1 for e in employees if e["is_active"])
        official_emp = sum(1 for e in employees if e["is_active"] and normalize_role(e["role"]) == "STAFF_OFFICIAL")
        probation_emp = sum(1 for e in employees if e["is_active"] and normalize_role(e["role"]) == "STAFF_PROBATION")
        admin_emp = sum(1 for e in employees if e["is_active"] and is_admin_role(e["role"]))

        m1, m2, m3, m4 = st.columns(4, gap="medium")
        with m1:
            st.metric("Tổng số nhân sự", f"{total_emp} người", help="Số tài khoản đang làm việc trong hệ thống chi nhánh")
        with m2:
            st.metric("Nhân viên chính thức", f"{official_emp} người", help="Đã hoàn thành đào tạo quầy pha chế")
        with m3:
            st.metric("Nhân viên thử việc / mới", f"{probation_emp} người", help="Nhân viên mới cần tra cứu công thức và học việc")
        with m4:
            st.metric("Quản trị / Quản lý", f"{admin_emp} người", help="Chủ cửa hàng & Quản lý điều hành")

        st.divider()

        tab_list, tab_create, tab_reset = st.tabs(["📋 Danh sách Nhân viên", "➕ Đăng ký Nhân viên Mới", "🔄 Reset Mật khẩu Nhân viên"])

        with tab_list:
            st.write("#### 📋 Danh sách Tài khoản Nhân viên Chi nhánh")
            st.caption("Danh sách đầy đủ thông tin nhân sự, quyền truy cập và trạng thái mật khẩu.")

            if employees:
                df_emp = pd.DataFrame(employees)
                df_display = df_emp.copy()
                df_display["Trạng thái mật khẩu"] = df_display["must_change_password"].apply(
                    lambda x: "⚠️ Bắt buộc đổi MK (Mặc định 123456)" if x else "✅ Đã thiết lập mật khẩu 6 số"
                )
                df_display["Trạng thái tài khoản"] = df_display["is_active"].apply(
                    lambda x: "🟢 Đang làm việc" if x else "🔴 Đã nghỉ việc"
                )

                df_display = df_display.rename(columns={
                    "username": "Tên đăng nhập",
                    "full_name": "Họ và tên",
                    "phone": "Số điện thoại",
                    "role_badge": "Phân quyền",
                    "created_at": "Ngày tạo tài khoản"
                })

                st.dataframe(
                    df_display[["Tên đăng nhập", "Họ và tên", "Số điện thoại", "Phân quyền", "Trạng thái mật khẩu", "Trạng thái tài khoản", "Ngày tạo tài khoản"]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("Chưa có dữ liệu nhân viên trong cơ sở dữ liệu.")

        with tab_list:
            if employees:
                st.write("#### Sửa / xóa nhân viên")
                selected_employee = st.selectbox("Chọn tài khoản cần chỉnh sửa", employees,
                    format_func=lambda e: f"{e['full_name']} (@{e['username']})", key="edit_employee_select")
                target = selected_employee["username"]
                roles = ["STAFF_OFFICIAL", "STAFF_PROBATION", "ADMIN", "MANAGER", "OWNER"]
                with st.form(f"edit_employee_{target}"):
                    edit_name = st.text_input("Họ tên", selected_employee["full_name"])
                    edit_phone = st.text_input("Điện thoại", "" if selected_employee["phone"] == "—" else selected_employee["phone"])
                    edit_role = st.selectbox("Vai trò", roles, index=roles.index(normalize_role(selected_employee["role"])))
                    edit_active = st.checkbox("Đang làm việc / Cho phép đăng nhập", value=selected_employee["is_active"])
                    if st.form_submit_button("Lưu thông tin nhân viên", type="primary"):
                        ok, message = update_employee(st.session_state.get("username", ""), target, edit_name, edit_phone, edit_role, edit_active)
                        if ok:
                            st.session_state["employee_notice"] = message
                            st.rerun()
                        st.error(message)
                confirm_delete = st.checkbox(f"Xác nhận xóa tài khoản @{target}", key=f"confirm_delete_{target}")
                if st.button("Xóa nhân viên", key=f"delete_employee_{target}", disabled=not confirm_delete):
                    ok, message = delete_employee(st.session_state.get("username", ""), target)
                    if ok:
                        st.session_state["employee_notice"] = message
                        st.rerun()
                    st.error(message)

        with tab_create:
            st.write("#### ➕ Đăng ký Tài khoản Nhân viên Mới")
            st.caption("Mật khẩu khởi tạo mặc định cho nhân viên mới sẽ là **123456**. Khi đăng nhập lần đầu, hệ thống sẽ tự động bắt buộc nhân viên đổi mật khẩu riêng gồm đúng 6 chữ số.")

            with st.form("create_employee_form", clear_on_submit=True):
                col_c1, col_c2 = st.columns(2, gap="medium")
                with col_c1:
                    new_username = st.text_input("Tên đăng nhập (Username)", placeholder="Ví dụ: thuha_barista, quangnam", help="Viết liền không dấu, từ 3-30 ký tự")
                    new_fullname = st.text_input("Họ và tên nhân viên", placeholder="Ví dụ: Đỗ Thu Hà")
                with col_c2:
                    new_phone = st.text_input("Số điện thoại liên hệ", placeholder="Ví dụ: 0988123456")
                    role_options = [
                        ("STAFF_OFFICIAL", "☕ Nhân viên chính thức (Xem công thức, tem ly & chat AI)"),
                        ("STAFF_PROBATION", "🌱 Nhân viên thử việc / mới (Xem công thức, tem ly & chat AI)"),
                        ("ADMIN", "🛡️ Quản lý cửa hàng (Toàn quyền quản trị, báo cáo & duyệt)")
                    ]
                    new_role = st.selectbox(
                        "Phân loại vai trò / Vị trí",
                        role_options,
                        format_func=lambda x: x[1]
                    )

                st.markdown("""
                <div style="background: #f8fafc; border-left: 4px solid #e60012; padding: 10px 14px; border-radius: 4px; font-size: 13px; color: #334155; margin: 12px 0;">
                    📌 <strong>Quy chuẩn khởi tạo:</strong><br>
                    • Mật khẩu mặc định hệ thống tự cấp: <code>123456</code><br>
                    • Nhân viên mới đăng nhập lần đầu sẽ bị chặn và bắt buộc phải đổi sang mật khẩu riêng (mã PIN gồm đúng 6 chữ số) trước khi được vào quầy.
                </div>
                """, unsafe_allow_html=True)

                btn_create = st.form_submit_button("Tạo Tài Khoản Nhân Viên Ngay 🚀", type="primary", use_container_width=True)

                if btn_create:
                    if not new_username or not new_fullname:
                        st.error("Vui lòng điền đầy đủ Tên đăng nhập và Họ tên nhân viên!")
                    else:
                        ok, msg = create_employee(
                            admin_username=st.session_state.get("username", "admin"),
                            username=new_username,
                            full_name=new_fullname,
                            phone=new_phone,
                            role=new_role[0]
                        )
                        if ok:
                            st.session_state["employee_notice"] = msg
                            st.rerun()
                        else:
                            st.error(msg)

        with tab_reset:
            st.write("#### 🔄 Reset Mật khẩu Nhân viên về Mặc định")
            st.caption("Sử dụng khi nhân viên quên mật khẩu hoặc bàn giao ca mới. Mật khẩu sẽ được hoàn về **123456** và kích hoạt lại cờ bắt buộc đổi mật khẩu 6 số.")

            current_admin = st.session_state.get("username", "")
            reset_candidates = [e for e in employees if e["username"] != current_admin]

            if reset_candidates:
                emp_options = {
                    f"{e['full_name']} (@{e['username']}) — {e['role_badge']}": e["username"]
                    for e in reset_candidates
                }
                selected_label = st.selectbox("Chọn nhân viên cần Reset Mật khẩu:", list(emp_options.keys()))
                target_user = emp_options[selected_label]

                with st.container(border=True):
                    st.warning(f"⚠️ Bạn đang chuẩn bị reset mật khẩu cho tài khoản: **{selected_label}**.\n\nMật khẩu tạm mới sẽ được cấp sau khi xác nhận. Nhân viên cần đổi mật khẩu khi đăng nhập lần tới.")

                    if st.button("Xác nhận cấp lại mật khẩu 🔄", type="primary", use_container_width=True):
                        ok, msg = reset_employee_password(admin_username=current_admin, target_username=target_user)
                        if ok:
                            st.session_state["employee_notice"] = msg
                            st.rerun()
                        else:
                            st.error(msg)
            else:
                st.info("Hiện không có tài khoản nhân viên nào khác để reset.")

    # Render Chatbot (Dedicated Fullscreen Tab when section == "💬 Tuyết Vương AI", or Floating Bottom-Right Button otherwise).
    render_chat(agent, role_key, user_name)

# Server time of this run, in the server log (Render → Logs), to tell slow code from a slow network/phone.
_run_ms = (time.perf_counter() - _RUN_STARTED) * 1000
if _run_ms > 700:
    print(f"[timing] page={st.session_state.get('main_navigation', '?')} server={_run_ms:.0f}ms", flush=True)
