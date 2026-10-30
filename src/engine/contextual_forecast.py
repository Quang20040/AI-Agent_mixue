"""Small regularized demand model; weather effect must beat temporal holdouts.

Weather coefficients are learned from this store, never invented by the LLM.
Historical target-day weather must be archived D+1 forecasts, not future actuals.
"""
from datetime import timedelta

import numpy as np


def _fit_predict(x, y, target):
    x = np.asarray(x, dtype=float)
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale < 1e-8] = 1
    z = np.column_stack([np.ones(len(x)), (x - mean) / scale])
    penalty = np.eye(z.shape[1]) * 10.0
    penalty[0, 0] = 0
    weights = np.linalg.solve(z.T @ z + penalty, z.T @ np.log1p(y))
    result = np.expm1(np.r_[1.0, (np.asarray(target) - mean) / scale] @ weights)
    return max(0.0, float(result))


def _features(day, sales, target_weather=None, previous_weather=None):
    prior = day - timedelta(days=1)
    week_ago = day - timedelta(days=7)
    window = [sales.get(day - timedelta(days=i)) for i in range(1, 8)]
    if any(row is None for row in window) or prior not in sales or week_ago not in sales:
        return None
    prev = sales[prior]
    if prev['cups'] <= 0:
        return None
    # Revenue per cup captures price/mix changes, avoiding double-counting cups
    # and revenue as two independent measures of demand.
    basic = [np.log1p(prev['cups']), np.log1p(sales[week_ago]['cups']),
             np.log1p(np.mean([r['cups'] for r in window])),
             np.log1p(prev['revenue'] / prev['cups']),
             np.sin(2 * np.pi * day.weekday() / 7), np.cos(2 * np.pi * day.weekday() / 7)]
    if target_weather is None or previous_weather is None:
        return basic
    return basic + [target_weather['temperature_c'], np.log1p(target_weather['rain_mm']),
                    np.log1p(target_weather['peak_rain_mm']),
                    target_weather['temperature_c'] - previous_weather['temperature_c'],
                    np.log1p(target_weather['peak_rain_mm']) - np.log1p(previous_weather['peak_rain_mm'])]


def contextual_adjustment(sales_frame, target, history_weather, target_weather, baseline_total, baseline_fn):
    daily = sales_frame[sales_frame['business_date'] < target].groupby('business_date').agg(
        cups=('quantity_sold', 'sum'), revenue=('revenue_vnd', 'sum'))
    sales = {day: {'cups': float(row.cups), 'revenue': float(row.revenue)} for day, row in daily.iterrows()}
    reference = history_weather['reference']
    anticipated = history_weather['anticipated']
    rows = []
    for day in sorted(sales):
        if day not in anticipated or day - timedelta(days=1) not in reference:
            continue
        x = _features(day, sales, anticipated[day], reference[day - timedelta(days=1)])
        if x is not None:
            rows.append((day, x, sales[day]['cups']))
    metadata = {'status': 'INSUFFICIENT_HISTORY', 'factor': 1.0, 'training_days': len(rows),
                'baseline_total_cups': round(baseline_total, 1), 'validation': None}
    if len(rows) < 28:
        return metadata
    previous = target - timedelta(days=1)
    if previous not in reference or target_weather is None:
        return {**metadata, 'status': 'MISSING_WEATHER'}
    target_x = _features(target, sales, target_weather, reference[previous])
    if target_x is None:
        return {**metadata, 'status': 'MISSING_RECENT_SALES'}
    actuals, weather_preds, context_preds, baseline_preds = [], [], [], []
    # Every fit uses only rows preceding that validation day. Preprocessing and
    # price/volume lags are recomputed from that prefix, never from future sales.
    first_eval = max(21, len(rows) - 14)
    for i in range(first_eval, len(rows)):
        day, vector, actual = rows[i]
        x, y = [r[1] for r in rows[:i]], [r[2] for r in rows[:i]]
        weather_preds.append(_fit_predict(x, y, vector))
        context_preds.append(_fit_predict([v[:6] for v in x], y, vector[:6]))
        baseline_preds.append(baseline_fn(day))
        actuals.append(actual)
    denominator = sum(actuals)
    if denominator <= 0 or len(actuals) < 7:
        return metadata
    wape = lambda predictions: float(np.abs(np.asarray(predictions) - actuals).sum() / denominator * 100)
    weather_error, context_error, baseline_error = wape(weather_preds), wape(context_preds), wape(baseline_preds)
    validation = {'days': len(actuals), 'first_date': str(rows[first_eval][0]), 'last_date': str(rows[-1][0]),
                  'weather_WAPE_pct': round(weather_error, 2), 'sales_context_WAPE_pct': round(context_error, 2),
                  'baseline_WAPE_pct': round(baseline_error, 2), 'weather_inputs': 'archived_day1_forecasts'}
    x, y = [r[1] for r in rows], [r[2] for r in rows]
    weather_matrix = np.asarray(x)[:, 6:9]
    if np.any(np.asarray(target_x[6:9]) < weather_matrix.min(axis=0)) or np.any(np.asarray(target_x[6:9]) > weather_matrix.max(axis=0)):
        return {**metadata, 'status': 'WEATHER_OUT_OF_RANGE', 'validation': validation}
    if weather_error < min(context_error, baseline_error):
        prediction = _fit_predict(x, y, target_x)
        counterfactual = _features(target, sales, reference[previous], reference[previous])
        weather_delta = prediction - _fit_predict(x, y, counterfactual)
        status = 'WEATHER_VALIDATED'
    elif context_error < baseline_error:
        prediction = _fit_predict([v[:6] for v in x], y, target_x[:6])
        weather_delta = None
        status = 'SALES_CONTEXT_ONLY'
    else:
        prediction, weather_delta, status = baseline_total, None, 'BASELINE_RETAINED'
    unclipped = prediction / baseline_total if baseline_total > 0 else 1.0
    factor = float(np.clip(unclipped, .5, 1.5))
    return {**metadata, 'status': status, 'factor': factor, 'validation': validation,
            'context_total_cups': round(baseline_total * factor, 1),
            'safety_limit_applied': factor != unclipped,
            'weather_scenario_delta_cups': round(weather_delta, 1) if weather_delta is not None else None,
            'previous_day': {'date': str(previous), **sales[previous], 'weather_estimate': reference[previous]},
            'target_weather_forecast': target_weather,
            'confidence_note': 'Kiểm chứng ngắn hạn tại một cửa hàng; chưa phải mức chính xác bảo đảm.'}
