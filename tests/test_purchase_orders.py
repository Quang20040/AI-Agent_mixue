"""Purchase order: manager edits AI cartons, approves, records the delivery → stock-in slips."""
from datetime import date

import pytest

from src.engine import purchase_orders
from src.engine.plan_service import get_plan, save_plan


def _draft(plan_id='PLAN_PO_TEST0001'):
    save_plan({'plan_id': plan_id, 'plan_type': 'REPLENISHMENT_PO', 'target_date': '2026-11-07', 'status': 'PENDING_APPROVAL',
               'created_at': '2026-11-07T09:00:00', 'lead_time_days': 2, 'verification': {'is_valid': True, 'violations': []},
               'lines': [
                   {'ingredient_id': '1', 'ingredient_name': 'Ốc quế', 'unit': 'pcs', 'pack_size': 400.0, 'carton_unit': 'thùng',
                    'packs_to_order': 5, 'recommended_order_qty': 2000.0, 'display_order': '5 thùng', 'priority': 'REORDER'},
                   {'ingredient_id': '2', 'ingredient_name': 'Bột kem', 'unit': 'g', 'pack_size': 24000.0, 'carton_unit': 'thùng',
                    'packs_to_order': 0, 'recommended_order_qty': 0.0, 'display_order': '0 thùng', 'priority': 'OK'}]})
    return plan_id


def _movements(plan_id):
    from src.database import SessionLocal
    from src.models import DailyStockMovement
    with SessionLocal() as db:
        return [(m.ingredient_id, m.movement_type, m.quantity, m.status) for m in db.query(DailyStockMovement)
                .filter(DailyStockMovement.notes.like(f'%{plan_id}%')).all()]


def test_manager_changes_ai_quantity_and_adds_an_item():
    plan_id = _draft()
    ok, msg = purchase_orders.update_quantities(plan_id, {'1': 7, '2': 1}, 'Quang', 'ADMIN')
    assert ok and '5 → 7' in msg
    lines = {line['ingredient_id']: line for line in get_plan(plan_id)['lines']}
    assert lines['1']['packs_to_order'] == 7 and lines['1']['ai_packs'] == 5 and lines['1']['recommended_order_qty'] == 2800
    assert lines['2']['packs_to_order'] == 1 and lines['2']['edited']
    assert get_plan(plan_id)['edits'][0]['by'].startswith('Quang')


@pytest.mark.parametrize('value', [-1, 2.5, 'abc', 1000])
def test_bad_quantities_are_refused(value):
    plan_id = _draft('PLAN_PO_TEST0002')
    ok, _ = purchase_orders.update_quantities(plan_id, {'1': value}, 'Quang', 'ADMIN')
    assert not ok and get_plan(plan_id)['lines'][0]['packs_to_order'] == 5


def test_staff_cannot_edit_and_approved_orders_are_frozen():
    plan_id = _draft('PLAN_PO_TEST0003')
    assert not purchase_orders.update_quantities(plan_id, {'1': 9}, 'Thảo', 'STAFF_OFFICIAL')[0]
    plan = get_plan(plan_id)
    plan.update(status='APPROVED', approved_at='2026-11-07T10:00:00', approved_by='Quang (ADMIN)')
    save_plan(plan)
    assert not purchase_orders.update_quantities(plan_id, {'1': 9}, 'Quang', 'ADMIN')[0]
    assert purchase_orders.expected_arrival(get_plan(plan_id)) == date(2026, 11, 9)


def test_receiving_adds_stock_once_with_the_actual_cartons():
    plan_id = _draft('PLAN_PO_TEST0004')
    assert not purchase_orders.receive(plan_id, {'1': 5}, date.today(), 'quanly', 'ADMIN')[0]   # not approved yet
    plan = get_plan(plan_id)
    plan.update(status='APPROVED', approved_at='2026-11-07T10:00:00', approved_by='Quang (ADMIN)')
    save_plan(plan)
    ok, msg, slips = purchase_orders.receive(plan_id, {'1': 4}, date.today(), 'quanly', 'ADMIN', 'thiếu 1 thùng')
    assert ok and 'Thiếu' in msg and slips[0]['received'] == 4
    assert _movements(plan_id) == [('1', 'IN', 4.0, 'APPROVED')]
    assert get_plan(plan_id)['status'] == 'RECEIVED'
    assert not purchase_orders.receive(plan_id, {'1': 4}, date.today(), 'quanly', 'ADMIN')[0]   # never twice
    assert len(_movements(plan_id)) == 1


def test_delivery_recorded_by_staff_waits_for_the_manager():
    plan_id = _draft('PLAN_PO_TEST0005')
    plan = get_plan(plan_id)
    plan.update(status='APPROVED', approved_at='2026-11-07T10:00:00', approved_by='Quang (ADMIN)')
    save_plan(plan)
    ok, msg, _ = purchase_orders.receive(plan_id, {'1': 5}, date.today(), 'nhanvien', 'STAFF_OFFICIAL')
    assert ok and 'chờ Quản lý duyệt' in msg
    assert _movements(plan_id) == [('1', 'IN', 5.0, 'PENDING')]


def test_purchase_page_draft_approve_then_receive_buttons():
    from test_e2e_staff_manager import _open
    app = _open('quick_login_owner')   # other tests reset the manager's password
    app.radio(key='main_navigation').set_value('Nhập hàng').run()
    app.button(key='calc_po_btn_vi').click().run()
    assert not app.exception, app.exception
    plan_id = app.session_state['po_plan_vi']['draft_plan_id']
    assert any(b.key == 'po_save_new' for b in app.button)
    # other tests' approved orders count as "đang về", so the AI may suggest 0 everywhere: the manager types a number
    first = str(get_plan(plan_id)['lines'][0]['ingredient_id'])
    assert purchase_orders.update_quantities(plan_id, {first: 3}, 'Quang', "ADMIN")[0]
    app.run()
    app.button(key='po_approve_new').click().run()
    assert not app.exception, app.exception
    assert get_plan(plan_id)['status'] == 'APPROVED'
    assert any(b.key == f'po_recv_go_{plan_id}' for b in app.button)   # "Đã nhận hàng" shows on the approved order
    app.button(key=f'po_recv_go_{plan_id}').click().run()
    assert not app.exception, app.exception
    assert get_plan(plan_id)['status'] == 'RECEIVED', [e.value for e in app.error]
    assert _movements(plan_id)


def test_cannot_approve_an_all_zero_order():
    from test_e2e_staff_manager import _open
    app = _open('quick_login_owner')
    app.radio(key='main_navigation').set_value('Nhập hàng').run()
    app.button(key='calc_po_btn_vi').click().run()
    plan = app.session_state['po_plan_vi']
    plan_id = plan['draft_plan_id']
    stored = get_plan(plan_id)
    for line in stored['lines']:
        line['packs_to_order'] = 0
    save_plan(stored)
    app.run()
    app.button(key='po_approve_new').click().run()
    assert get_plan(plan_id)['status'] == 'PENDING_APPROVAL'
    assert any('chưa có mặt hàng' in e.value for e in app.error)
