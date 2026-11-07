"""Purchase orders: AI draft → manager edits cartons → approve → goods arrive → stock in."""
from datetime import date

import pandas as pd
import streamlit as st

from src.auth import is_admin_role
from src.engine import purchase_orders
from src.engine.plan_service import get_plan, list_plans, reject_plan

PRIORITY = {"CRITICAL": "🚨 Sắp hết", "REORDER": "📦 Cần nhập", "OK": "✅ Đủ hàng"}
STATUS = {"PENDING_APPROVAL": "⏳ Chờ duyệt", "APPROVED": "🚚 Đã duyệt · chờ hàng về", "RECEIVED": "✅ Đã nhận hàng",
          "REJECTED": "✖ Đã từ chối"}


def _vn(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso and len(str(iso)) >= 10 else (iso or "")


def _sorted_lines(plan):
    order = {"CRITICAL": 0, "REORDER": 1, "OK": 2}
    return sorted(plan["lines"], key=lambda line: (order.get(line.get("priority"), 3), -int(line.get("packs_to_order") or 0)))


def render_draft_editor(agent, plan, role, user_name, username, key):
    """Pending draft: editable cartons (all items, so one the AI left at 0 can be added), save, approve, reject."""
    lines = _sorted_lines(plan)
    frame = pd.DataFrame([{
        "Mã": line["ingredient_id"], "Nguyên liệu": line["ingredient_name"], "Ưu tiên": PRIORITY.get(line.get("priority"), ""),
        "Tồn sổ kho": (f"{line['on_hand_packs']:g} {line.get('carton_unit', 'thùng')}" if "on_hand_packs" in line
                       else f"{line.get('current_on_hand', 0):,.0f} {line.get('unit', '')}")
                      + (" ⚠️ âm" if line.get("negative_book_stock") else "")
                      + ("" if line.get("on_hand_source", "sổ kho") == "sổ kho" else f" ({line.get('on_hand_source')})"),
        "Đang về": int(line.get("coming_packs") or 0),
        "Đủ dùng (ngày)": line.get("days_of_stock_remaining"),
        "AI đề xuất": int(line.get("ai_packs", line.get("packs_to_order") or 0)),
        "Số đặt": int(line.get("packs_to_order") or 0),
        "Đơn vị": line.get("carton_unit", "thùng"), "Quy cách": line.get("carton_spec", ""),
    } for line in lines])
    admin = is_admin_role(role)
    st.caption("Sửa cột **Số đặt** nếu muốn đặt khác AI (ví dụ AI đề xuất 5 thùng, bạn muốn 7). "
               "Mặt hàng AI để 0 vẫn thêm được. Số lượng tính theo nguyên thùng/kiện. "
               "AI tính từ **tồn sổ kho** hôm nay và trừ hàng **đang về** của các đơn đã duyệt chưa nhận.")
    unmapped = [line["ingredient_name"] for line in lines if line.get("on_hand_source") == "chưa ghép với sổ kho"]
    if unmapped:
        st.warning("Chưa ghép với dòng nào của sổ kho nên AI không biết tồn (tính như hết hàng): "
                   + ", ".join(unmapped) + ". Kiểm tra số đặt trước khi duyệt.")
    if any(line.get("negative_book_stock") for line in lines):
        st.warning("Có mặt hàng tồn sổ kho bị âm (xuất nhiều hơn nhập): nên kiểm kê và sửa tồn đầu kỳ trên sổ kho, "
                   "AI đang coi các mặt hàng này là hết hàng.")
    edited = st.data_editor(
        frame, key=f"po_edit_{key}", hide_index=True, width="stretch",
        disabled=True if not admin else [c for c in frame.columns if c != "Số đặt"],
        column_config={"Số đặt": st.column_config.NumberColumn("Số đặt", min_value=0, max_value=999, step=1, format="%d",
                                                               help="Số thùng/kiện sẽ đặt")})
    changed = {row["Mã"]: row["Số đặt"] for _, row in edited.iterrows()
               if int(row["Số đặt"] or 0) != int(frame.loc[frame["Mã"] == row["Mã"], "Số đặt"].iloc[0])}
    total = int(pd.to_numeric(edited["Số đặt"], errors="coerce").fillna(0).sum())
    st.markdown(f"**Tổng: {total} thùng/kiện** · {sum(1 for v in edited['Số đặt'] if v)} mặt hàng"
                + (f" · <span style='color:#B54708'>{len(changed)} dòng chưa lưu</span>" if changed else ""), unsafe_allow_html=True)
    if plan.get("edits"):
        last = plan["edits"][-1]
        st.caption(f"Đã sửa bởi {last['by']} lúc {last['at'][11:16]} {_vn(last['at'])}: " + "; ".join(last["changes"][:4]))
    if not admin:
        st.info("Chỉ Quản lý / Chủ quán được sửa số lượng và duyệt đơn.")
        return
    c1, c2, c3 = st.columns(3)
    if c1.button("💾 Lưu số lượng", key=f"po_save_{key}", disabled=not changed, width="stretch"):
        ok, msg = purchase_orders.update_quantities(plan["plan_id"], changed, user_name, role)
        (st.success if ok else st.error)(msg)
        if ok:
            st.rerun()
    if c2.button("✍️ Lưu & ký duyệt", key=f"po_approve_{key}", type="primary", width="stretch"):
        if total <= 0:
            st.error("Đơn chưa có mặt hàng nào (tổng 0 thùng). Nhập **Số đặt** cho ít nhất một mặt hàng, hoặc bấm Từ chối.")
            return
        if changed:
            ok, msg = purchase_orders.update_quantities(plan["plan_id"], changed, user_name, role)
            if not ok:
                st.error(msg)
                return
        res = agent.tool_approve_plan(plan["plan_id"], user_role=role, user_name=user_name)
        if res.get("is_approved"):
            st.session_state["po_flash"] = ("success", f"Đã duyệt {plan['plan_id']}. Hàng dự kiến về sau "
                                                       f"{plan.get('lead_time_days', 2)} ngày; khi hàng tới bấm “Đã nhận hàng”.")
            st.session_state.pop("po_plan_vi", None)
            st.rerun()
        st.error(res.get("message", "Không duyệt được."))
    if c3.button("✖ Từ chối", key=f"po_reject_{key}", width="stretch"):
        ok, msg = reject_plan(plan["plan_id"], username, "Quản lý từ chối")
        (st.success if ok else st.error)(msg)
        st.session_state.pop("po_plan_vi", None)
        st.rerun()


def render_receive_form(plan, role, username, key):
    """Approved order: cartons actually delivered per line → stock-in slips."""
    expected = purchase_orders.expected_arrival(plan)
    today = date.today()
    if expected:
        late = (today - expected).days
        note = (f"Dự kiến hàng về **{expected:%d/%m/%Y}**"
                + (f" — trễ {late} ngày" if late > 0 else " — hôm nay" if late == 0 else f" — còn {-late} ngày"))
        (st.warning if late > 0 else st.info)(note)
    lines = [line for line in plan["lines"] if int(line.get("packs_to_order") or 0) > 0]
    frame = pd.DataFrame([{"Mã": line["ingredient_id"], "Nguyên liệu": line["ingredient_name"],
                           "Đã đặt": int(line["packs_to_order"]), "Thực nhận": int(line["packs_to_order"]),
                           "Đơn vị": line.get("carton_unit", "thùng")} for line in lines])
    st.caption("Khi hàng tới: kiểm đếm, sửa cột **Thực nhận** nếu thiếu/thừa, rồi xác nhận. Hệ thống tạo phiếu nhập kho cho từng mặt hàng.")
    edited = st.data_editor(frame, key=f"po_recv_{key}", hide_index=True, width="stretch",
                            disabled=[c for c in frame.columns if c != "Thực nhận"],
                            column_config={"Thực nhận": st.column_config.NumberColumn(min_value=0, max_value=999, step=1, format="%d")})
    c1, c2 = st.columns([1, 2])
    received_on = c1.date_input("Ngày nhận", value=today, max_value=today, key=f"po_recv_day_{key}")
    note = c2.text_input("Ghi chú (tuỳ chọn)", key=f"po_recv_note_{key}", placeholder="Ví dụ: thiếu 1 thùng, NCC giao bù sau")
    if st.button("✅ Đã nhận hàng · cộng vào kho", key=f"po_recv_go_{key}", type="primary"):
        received = {row["Mã"]: row["Thực nhận"] for _, row in edited.iterrows()}
        ok, msg, _ = purchase_orders.receive(plan["plan_id"], received, received_on, username, role, note)
        st.session_state["po_flash"] = ("success" if ok else "error", msg)
        st.rerun()


def render_received(plan):
    rows = plan.get("received_lines") or []
    st.success(f"Nhận hàng ngày {_vn(plan.get('received_on'))} · {plan.get('received_by', '')}")
    if rows:
        st.dataframe(pd.DataFrame([{"Nguyên liệu": r["ingredient_name"], "Đã đặt": r["ordered"], "Thực nhận": r["received"],
                                    "Phiếu kho": f"#{r['request_id']}" + ("" if r["approved"] else " (chờ duyệt)")} for r in rows]),
                     hide_index=True, width="stretch")
    if plan.get("receive_note"):
        st.caption("Ghi chú: " + plan["receive_note"])


def render_order_history(agent, role, user_name, username):
    orders = list_plans("REPLENISHMENT_PO")
    waiting = [o for o in orders if o.get("status") == "APPROVED"]
    late = [o for o in waiting if (exp := purchase_orders.expected_arrival(o)) and exp < date.today()]
    if waiting:
        st.info(f"🚚 {len(waiting)} đơn đã duyệt đang chờ hàng về" + (f" — {len(late)} đơn quá ngày dự kiến." if late else "."))
    st.write("#### Đơn đặt hàng")
    if not orders:
        st.info("Chưa có đơn đặt hàng. Tạo dự thảo để lưu đơn đầu tiên.")
        return
    status_filter = st.segmented_control("Lọc", ["Tất cả", "Chờ duyệt", "Chờ hàng về", "Đã nhận"], default="Tất cả",
                                         key="po_filter")
    wanted = {"Chờ duyệt": "PENDING_APPROVAL", "Chờ hàng về": "APPROVED", "Đã nhận": "RECEIVED"}.get(status_filter)
    shown = [o for o in orders if not wanted or o.get("status") == wanted][:10]
    for order in shown:
        status = order.get("status")
        title = f"{order['plan_id']} · {_vn(order['target_date'])} · {STATUS.get(status, status)}"
        with st.expander(title, expanded=status == "APPROVED"):
            st.caption(f"Tạo lúc {str(order['created_at'])[:16].replace('T', ' ')} · giao trong {order.get('lead_time_days', 2)} ngày"
                       + (f" · duyệt bởi {order['approved_by']}" if order.get("approved_by") else ""))
            if status == "PENDING_APPROVAL":
                render_draft_editor(agent, get_plan(order["plan_id"]), role, user_name, username, order["plan_id"])
            elif status == "APPROVED":
                render_receive_form(order, role, username, order["plan_id"])
            elif status == "RECEIVED":
                render_received(order)
            else:
                st.caption(order.get("rejection_reason") or "")
