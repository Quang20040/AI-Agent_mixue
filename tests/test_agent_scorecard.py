from experiments.agent_scorecard import score_response


def test_right_words_with_wrong_tool_or_status_must_fail():
    case = {'tool_groups': [['get_daily_sales']], 'required_text': ['100'], 'evidence_required': True}
    response = {'text': '100 ly', 'tool_called': 'forecast_demand', 'raw_result': {'status': 'SUCCESS'},
                'evidence_refs': ['table:sales_daily']}
    assert not score_response(case, response)['passed']
    response['tool_called'] = 'get_daily_sales'
    assert score_response(case, response)['passed']
    response['raw_result']['status'] = 'MODEL_ERROR'
    assert not score_response(case, response)['passed']


def test_compound_question_checks_all_tool_groups():
    case = {'tool_groups': [['forecast_demand'], ['get_weather_forecast']]}
    response = {'text': 'Dự báo', 'tool_called': 'forecast_demand'}
    assert not score_response(case, response)['passed']
    response['tool_called'] += ',get_weather_forecast'
    assert score_response(case, response)['passed']
