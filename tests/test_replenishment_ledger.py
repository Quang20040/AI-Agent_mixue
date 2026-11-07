"""Purchase suggestions read the stock ledger and count goods already on the way."""
from datetime import date

from src.engine.daily_stock_service import ledger_balances, update_stock_cell_manually
from src.engine.optimizer import MIXUE_CARTON_SPECS




def test_ledger_balance_follows_the_stock_sheet():
    from src.engine.daily_stock_service import get_stock_matrix_df
    sheet = get_stock_matrix_df(2026, 11)
    balances = ledger_balances(date(2026, 11, 30))
    for _, row in sheet.iterrows():
        if row['Tồn sổ sách'] != '—':
            assert abs(balances[str(row['Mã NL'])] - float(row['Tồn sổ sách'])) < 1e-9


def test_more_stock_on_the_ledger_means_fewer_cartons_to_order():
    from src.agent.config import AgentSettings
    from src.agent.mixue_agent import MixueOperationsAgent
    agent = MixueOperationsAgent(settings=AgentSettings.from_env())

    def packs(ing):
        res = agent.tool_optimize_replenishment(target_date='2026-11-07', persist_draft=False)
        line = next((x for x in res['top_orders'] if str(x['ingredient_id']) == ing), None)
        return (line or {}).get('packs_to_order', 0), line

    ok, msg = update_stock_cell_manually('10', 'Tồn cuối T10/2026', 0, 'chucuahang', year=2026, month=11)
    assert ok, msg
    empty, line = packs('10')
    assert line and line['on_hand_source'] == 'sổ kho' and empty > 0
    full_stock = empty + 50
    update_stock_cell_manually('10', 'Tồn cuối T10/2026', full_stock, 'chucuahang', year=2026, month=11)
    assert packs('10')[0] < empty
    update_stock_cell_manually('10', 'Tồn cuối T10/2026', '', 'chucuahang', year=2026, month=11)
    assert MIXUE_CARTON_SPECS['10']['carton_unit'] == 'kiện'


def test_goods_on_the_way_are_not_ordered_twice():
    from src.agent.config import AgentSettings
    from src.agent.mixue_agent import MixueOperationsAgent
    from src.engine.plan_service import get_plan, save_plan
    agent = MixueOperationsAgent(settings=AgentSettings.from_env())
    update_stock_cell_manually('10', 'Tồn cuối T10/2026', 0, 'chucuahang', year=2026, month=11)
    first = agent.tool_optimize_replenishment(target_date='2026-11-07')
    need = next(x for x in first['top_orders'] if str(x['ingredient_id']) == '10')['packs_to_order']
    plan = get_plan(first['draft_plan_id'])
    plan.update(status='APPROVED', approved_at='2026-11-06T10:00:00', approved_by='Chi (ADMIN)')
    save_plan(plan)
    again = agent.tool_optimize_replenishment(target_date='2026-11-07', persist_draft=False)
    line = next((x for x in again['top_orders'] if str(x['ingredient_id']) == '10'), None)
    assert line is None or (line['coming_packs'] >= need and line['packs_to_order'] < need)
    plan.update(status='REJECTED')
    save_plan(plan)
    update_stock_cell_manually('10', 'Tồn cuối T10/2026', '', 'chucuahang', year=2026, month=11)


def test_recipe_codes_are_ordered_as_stock_sheet_items():
    from src.agent.config import AgentSettings
    from src.agent.mixue_agent import MixueOperationsAgent
    agent = MixueOperationsAgent(settings=AgentSettings.from_env())
    update_stock_cell_manually('10', 'Tồn cuối T10/2026', 0, 'chucuahang', year=2026, month=11)   # make sure it is needed
    lines = {str(x['ingredient_id']): x for x in agent.tool_optimize_replenishment(target_date='2026-11-07', persist_draft=False)['top_orders']}
    assert 'NL01' not in lines and '10' in lines and 'NL01' in lines['10']['recipe_ids']   # Đường mật on the sheet's row
    assert lines['10']['carton_unit'] == 'kiện'
    unmapped = [x for x in lines.values() if x['on_hand_source'] == 'chưa ghép với sổ kho']
    assert all(str(x['ingredient_id']).startswith('NL') for x in unmapped)
    update_stock_cell_manually('10', 'Tồn cuối T10/2026', '', 'chucuahang', year=2026, month=11)


def test_shop_confirmed_mappings():
    from src.engine.optimizer import MIXUE_CARTON_SPECS
    from src.engine.stock_mapping import BOUGHT_PER_BOX, NOT_PURCHASED, stock_id
    assert stock_id('NL11') == '23'                        # mứt xoài = syrup xoài, 20 lon/thùng
    assert stock_id('NL12') == stock_id('NL13') == '16'    # đào mật và đào vàng là cùng syrup đào, 20 hộp/thùng
    assert MIXUE_CARTON_SPECS['NL11']['carton_size'] == 17000.0 and MIXUE_CARTON_SPECS['NL12'] is MIXUE_CARTON_SPECS['16']
    assert 'NL09' in NOT_PURCHASED and stock_id('NL09') is None   # vụn ốc quế lấy từ thùng ốc quế
    assert 'NL22' in BOUGHT_PER_BOX and 'NL22' not in MIXUE_CARTON_SPECS   # cà phê hòa tan mua theo hộp, không phải cafe rang


def test_cone_crumbs_never_ordered_and_peach_merged():
    from src.agent.config import AgentSettings
    from src.agent.mixue_agent import MixueOperationsAgent
    agent = MixueOperationsAgent(settings=AgentSettings.from_env())
    result = agent.tool_optimize_replenishment(target_date='2026-11-07', persist_draft=False)
    every = result.get('all_lines') or result['top_orders']
    ids = [str(x['ingredient_id']) for x in every]
    assert 'NL09' not in ids and 'NL11' not in ids and 'NL12' not in ids
    assert len(ids) == len(set(ids))
