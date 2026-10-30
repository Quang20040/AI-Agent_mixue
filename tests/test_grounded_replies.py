"""Regressions observed with the real OpenRouter free-model route."""
import pytest

from src.agent.response_policy import grounded_result_reply


@pytest.fixture
def sales():
    return [{'tool': 'get_data_coverage', 'result': {'last_date': '2026-10-15'}},
            {'tool': 'get_daily_sales', 'result': {'status': 'SUCCESS', 'period': '15/10/2026',
                'total_quantity_sold': 1574, 'total_revenue_vnd': 36455000,
                'source_refs': ['table:sales_daily'], 'all_items': []}}]


def test_cups_question_does_not_add_revenue_or_top_products(sales):
    reply = grounded_result_reply('Ngày gần nhất có dữ liệu bán được bao nhiêu ly?', sales)
    assert reply['text'] == '15/10/2026: **1,574 ly**.'
    assert reply['evidence_refs'] == ['table:sales_daily']


def test_revenue_question_does_not_add_cups(sales):
    reply = grounded_result_reply('Doanh thu ngày 15/10?', sales)
    assert '36,455,000' in reply['text']
    assert 'ly' not in reply['text']


@pytest.mark.parametrize('query', ['So sánh doanh thu', 'Phân tích doanh thu', 'Doanh thu và tồn kho?',
                                   'Tại sao doanh thu tăng?', 'Doanh thu món TS1?', 'Top 5 món bán chạy'])
def test_complex_questions_retain_model_synthesis(query, sales):
    assert grounded_result_reply(query, sales) is None


def test_comparison_using_two_results_is_not_reduced_to_one_day(sales):
    assert grounded_result_reply('Số ly hai ngày?', [*sales, sales[-1]]) is None


def test_sop_uses_actual_half_batch_water_quantity():
    from src.agent.multi_agent.operations_bom_agent import OperationsBOMAgent
    guide = OperationsBOMAgent().get_sop_prep_guide('trân châu nguyên vị')
    reply = grounded_result_reply('Cách nấu trân châu nửa mẻ?', [{'tool': 'get_sop_prep_guide', 'result': guide}])
    assert '**3000 ml**' in reply['text']
    assert '**500 g**' in reply['text']
    assert '**250 g**' in reply['text']
    assert '35 phút' in reply['text']
    assert '4 giờ' in reply['text']
    assert '4000 ml' not in reply['text']


def test_no_data_does_not_become_zero_sales():
    reply = grounded_result_reply('Hôm nay bán bao nhiêu ly?', [{'tool': 'get_daily_sales', 'result': {
        'status': 'NO_DATA', 'message': 'Không có dữ liệu ngày này.'}}])
    assert reply['raw_result']['status'] == 'NO_DATA'
    assert reply['text'] == 'Không có dữ liệu ngày này.'


def test_hallucinated_sop_without_tool_is_never_shown(tmp_path):
    from langchain_core.messages import AIMessage
    from langgraph.checkpoint.memory import InMemorySaver

    from src.agent.config import AgentSettings
    from src.agent.mixue_agent import MixueOperationsAgent
    class ModelWithoutTools:
        def bind_tools(self, tools, **kwargs):
            assert kwargs['tool_choice'] == 'required'
            return self
        def invoke(self, messages):
            return AIMessage(content='Ngâm trân châu 3 giờ và bảo quản lạnh 24 giờ.')
    service = MixueOperationsAgent(settings=AgentSettings(audit_path=str(tmp_path / 'audit.jsonl')),
                                   model=ModelWithoutTools(), checkpointer=InMemorySaver())
    try:
        result = service.process_query('Cách nấu trân châu nguyên vị?', 'MANAGER', 'Test')
        assert result['raw_result']['status'] == 'MISSING_EVIDENCE'
        assert '24 giờ' not in result['text']
        assert not result['evidence_refs']
    finally:
        service.close()


def test_forecast_question_requires_forecast_not_actual_sales():
    from src.agent.response_policy import required_evidence_tools
    assert required_evidence_tools('Dự báo số ly ngày mai') == {'forecast_demand'}
    assert required_evidence_tools('Hôm nay cần nấu trân châu bao nhiêu?') == {'optimize_topping_prep'}


def test_forecast_reply_keeps_missing_weather_and_sales_warning():
    result = {'status': 'SUCCESS', 'target_date': '2026-10-17', 'total_forecasted_cups': 1454,
              'daily_forecasts': [{'target_date': '2026-10-17', 'total_cups': 1454}],
              'source_refs': ['table:sales_daily'], 'forecast_context': {'status': 'MISSING_RECENT_SALES',
                  'warnings': ['Chưa có doanh số ngày 2026-10-16.', 'Chưa điều chỉnh theo thời tiết.']}}
    reply = grounded_result_reply('Dự báo số ly ngày mai', [{'tool': 'forecast_demand', 'result': result}])
    assert '1,454 ly' in reply['text']
    assert 'Chưa có doanh số ngày 2026-10-16' in reply['text']
    assert 'Chưa điều chỉnh theo thời tiết' in reply['text']


def test_preparation_reply_distinguishes_raw_and_finished_quantities():
    result = {'status': 'SUCCESS', 'target_date': '2026-10-16', 'yield_assumption': 'Định mức ước lượng.',
              'prep_policy': 'Không nấu hết cả ngày đầu ca.', 'recommendations': [
                  {'ingredient_name': 'Trân châu đã nấu', 'unit': 'g', 'recommended_prep_qty': 6000,
                   'num_batches': 3, 'initial_prep_qty': 2000, 'estimated_raw_input_g': 3000, 'initial_raw_input_g': 1000}]}
    reply = grounded_result_reply('Nguyên liệu cần nấu hôm nay', [{'tool': 'optimize_topping_prep', 'result': result}])
    assert '6,000 g thành phẩm' in reply['text']
    assert 'hạt khô' in reply['text'] and '3,000 g' in reply['text']
    assert 'ước lượng' in reply['text']
    assert 'chưa phê duyệt' in reply['text']
