"""Machine-learning forecast benchmark: does a learned model beat the statistical baselines?

Same rolling-origin, 1-day-ahead backtest as ForecastingEngine.run_backtest (start_eval_day=15): for every
evaluation day d and every menu item, each model only sees sales before d. Learned models are refit every
7 evaluation days on all rows before d (walk-forward), so no future data leaks into training.

Models
- seasonal_naive, moving_average, day_of_week_ma: the engine's baselines (same numbers as the app).
- gradient_boosting: HistGradientBoostingRegressor (Poisson loss, item as a categorical feature), one global
  model across all 39 items.
- neural_net (MLP): 2 hidden layers (64, 32), ReLU, Adam, early stopping, log1p target, item + weekday one-hot,
  average of 3 seeds, output capped at 1.5x the item's best day so far.

Features per (day, item): weekday, lags 1/2/7/14, rolling means 7/14/28, same-weekday mean of the last
3 weeks, store-wide cups yesterday and its 7-day mean, item id.

Usage: python experiments/ml_forecast_benchmark.py [out.json]
"""
from __future__ import annotations

import json
import sys
import warnings
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.engine.forecasting import ForecastingEngine  # noqa: E402

warnings.filterwarnings('ignore')
START_EVAL_DAY, REFIT_EVERY, SEED = 15, 7, 42
FEATURES = ['dow', 'lag1', 'lag2', 'lag7', 'lag14', 'ma7', 'ma14', 'ma28', 'dow_ma3', 'store_lag1', 'store_ma7']


def build_panel(fe: ForecastingEngine) -> tuple[pd.DataFrame, list, list]:
    dates, skus = list(fe.dates), list(fe.skus)
    y = pd.DataFrame({s: [float(fe._actuals.get((s, d), 0.0)) for d in dates] for s in skus}, index=dates)
    shifted = y.shift(1)  # everything below uses data up to the day before
    store = y.sum(axis=1).shift(1)
    rows = []
    for s in skus:
        col = y[s]
        f = pd.DataFrame({
            'date': dates, 'sku': s, 'y': col.values,
            'dow': [d.weekday() for d in dates],
            'lag1': shifted[s].values, 'lag2': col.shift(2).values,
            'lag7': col.shift(7).values, 'lag14': col.shift(14).values,
            'ma7': shifted[s].rolling(7, min_periods=1).mean().values,
            'ma14': shifted[s].rolling(14, min_periods=1).mean().values,
            'ma28': shifted[s].rolling(28, min_periods=1).mean().values,
            'dow_ma3': ((col.shift(7) + col.shift(14) + col.shift(21)) / 3).fillna(col.shift(7)).values,
            'store_lag1': store.values,
            'store_ma7': store.rolling(7, min_periods=1).mean().values,
        })
        rows.append(f)
    panel = pd.concat(rows, ignore_index=True)
    panel['sku_code'] = panel['sku'].map({s: i for i, s in enumerate(skus)})
    return panel, dates, skus


def metrics(actual: np.ndarray, pred: np.ndarray) -> dict:
    total = actual.sum()
    return {'MAE': round(float(np.mean(np.abs(actual - pred))), 2),
            'WAPE_pct': round(float(np.abs(actual - pred).sum() / total * 100), 2),
            'Bias_pct': round(float((pred.sum() - total) / total * 100), 2)}


def main(out: str | None):
    fe = ForecastingEngine()
    panel, dates, skus = build_panel(fe)
    eval_dates = dates[START_EVAL_DAY:]
    preds = {m: [] for m in ('seasonal_naive', 'moving_average', 'day_of_week_ma', 'gradient_boosting', 'neural_net')}
    actuals = []
    gbm = mlp = scaler = None
    n_sku = len(skus)

    def design(df, for_mlp=False):
        x = df[FEATURES].fillna(df['ma7']).fillna(0).to_numpy(dtype=float)
        if not for_mlp:
            return np.column_stack([x, df['sku_code'].to_numpy()])
        onehot = np.eye(n_sku)[df['sku_code'].to_numpy()]
        dow = np.eye(7)[df['dow'].to_numpy()]
        return np.column_stack([scaler.transform(np.log1p(x)), onehot, dow])

    for k, d in enumerate(eval_dates):
        if k % REFIT_EVERY == 0:  # walk-forward refit on everything before d
            train = panel[(panel['date'] < d) & (panel['date'] >= dates[1])]
            gbm = HistGradientBoostingRegressor(loss='poisson', learning_rate=0.05, max_iter=300, max_leaf_nodes=15,
                                                min_samples_leaf=20, l2_regularization=1.0,
                                                categorical_features=[len(FEATURES)], random_state=SEED)
            gbm.fit(design(train), train['y'])
            scaler = StandardScaler().fit(np.log1p(train[FEATURES].fillna(train['ma7']).fillna(0).to_numpy(dtype=float)))
            # small ensemble of 3 seeds: one MLP alone varies a lot from seed to seed on 3k rows
            mlp = [MLPRegressor(hidden_layer_sizes=(64, 32), alpha=1e-3, learning_rate_init=1e-3, max_iter=600,
                                early_stopping=True, n_iter_no_change=25, random_state=SEED + i)
                   .fit(design(train, True), np.log1p(train['y'])) for i in range(3)]
        today = panel[panel['date'] == d].set_index('sku').loc[skus].reset_index()
        g = np.clip(gbm.predict(design(today)), 0, None)
        # a neural net extrapolates wildly on unusual inputs (e.g. the half-day 14/10): cap each item at
        # 1.5x the most it ever sold before d, the same guard a production forecast would use
        cap = 1.5 * panel[panel['date'] < d].groupby('sku')['y'].max().reindex(skus).to_numpy()
        n = np.clip(np.expm1(np.mean([m.predict(design(today, True)) for m in mlp], axis=0)), 0, cap)
        for i, s in enumerate(skus):
            hist = fe.get_sku_history(s, up_to_date=d - timedelta(days=1))
            preds['seasonal_naive'].append(fe.predict_seasonal_naive(hist, d, 7))
            preds['moving_average'].append(fe.predict_moving_average(hist, 7))
            preds['day_of_week_ma'].append(fe.predict_day_of_week_ma(hist, d, 3))
            preds['gradient_boosting'].append(float(g[i]))
            preds['neural_net'].append(float(n[i]))
            actuals.append(float(fe._actuals.get((s, d), 0.0)))
    fe.close()

    a = np.array(actuals)
    result = {
        'evaluation_period': f'{eval_dates[0]} to {eval_dates[-1]} ({len(eval_dates)} days)',
        'items': len(skus), 'rows_evaluated': len(a),
        'refit_every_days': REFIT_EVERY, 'features': FEATURES + ['sku'],
        'metrics': {m: metrics(a, np.array(p)) for m, p in preds.items()},
    }
    # Is the learned model really better than the moving average? Paired day-level comparison + bootstrap CI.
    per_day = len(skus)
    def daily_abs(m):
        return np.abs(np.array(preds[m]) - a).reshape(-1, per_day).sum(axis=1)
    act_day = a.reshape(-1, per_day).sum(axis=1)
    rng = np.random.default_rng(SEED)
    for m in ('gradient_boosting', 'neural_net'):
        diff = daily_abs(m) - daily_abs('moving_average')
        boots = []
        for _ in range(2000):
            idx = rng.integers(0, len(diff), len(diff))
            boots.append(diff[idx].sum() / act_day[idx].sum() * 100)
        result['metrics'][m]['days_better_than_moving_average'] = f'{int((diff < 0).sum())}/{len(diff)}'
        result['metrics'][m]['wape_change_vs_ma_pct_points_95ci'] = [round(float(np.percentile(boots, 2.5)), 2),
                                                                     round(float(np.percentile(boots, 97.5)), 2)]
    print(json.dumps(result, ensure_ascii=False, indent=1))
    if out:
        Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
