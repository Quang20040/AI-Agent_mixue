import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import date
import pytest
import pandas as pd
from src.engine.forecasting import ForecastingEngine


@pytest.fixture(scope="module")
def fc_engine():
    engine = ForecastingEngine()
    yield engine
    engine.close()


def test_forecast_demand_all_skus(fc_engine):
    target_d = date(2026, 10, 13)
    preds = fc_engine.forecast_demand(target_date=target_d, horizon_days=1, model="auto")
    assert not preds.empty, "Forecast dataframe must not be empty"
    assert len(preds) == 39, f"Forecast must cover all 39 menu items, got {len(preds)}"
    assert (preds["predicted_qty"] >= 0).all(), "Predictions must be non-negative"
    assert (preds["lower_bound"] <= preds["predicted_qty"]).all(), "Lower bound must be <= prediction"
    assert (preds["upper_bound"] >= preds["predicted_qty"]).all(), "Upper bound must be >= prediction"


def test_backtest_metrics_validity(fc_engine):
    bt = fc_engine.run_backtest(start_eval_day=15)
    assert "aggregate_metrics" in bt
    assert "best_model" in bt
    for model_name, m in bt["aggregate_metrics"].items():
        assert m["MAE"] >= 0, f"{model_name} MAE must be non-negative"
        assert m["WAPE_pct"] >= 0, f"{model_name} WAPE must be non-negative"
        assert m["Total_Actual"] > 0, "Actual sales in backtest must be positive"
