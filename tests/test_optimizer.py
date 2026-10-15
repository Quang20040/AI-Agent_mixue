import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import date

import pytest

from src.engine.forecasting import ForecastingEngine
from src.engine.optimizer import OptimizerEngine
from src.engine.validator import IndependentPlanValidator


@pytest.fixture(scope="module")
def engines():
    fe = ForecastingEngine()
    opt = OptimizerEngine()
    val = IndependentPlanValidator()
    yield fe, opt, val
    fe.close()
    opt.close()
    val.close()


def test_topping_prep_batch_rounding(engines):
    fe, opt, val = engines
    fc = fe.forecast_demand(date(2026, 10, 13), horizon_days=1, model="auto")
    demand = opt.calculate_ingredient_demand(fc)
    preps = opt.optimize_topping_preparation(date(2026, 10, 13), demand, buffer_pct=0.10)
    
    assert len(preps) > 0, "Topping prep list should not be empty"
    for p in preps:
        batch_sz = p["batch_size"]
        rec_qty = p["recommended_prep_qty"]
        assert rec_qty % batch_sz == 0, f"Prep qty {rec_qty} must be exact multiple of batch size {batch_sz}"
        assert rec_qty >= 0, "Recommended prep qty must be non-negative"

    # Test independent validation
    v_res = val.verify_topping_prep_plan(preps)
    assert v_res["is_valid"] is True, f"Plan verification failed: {v_res.get('violations')}"
    assert v_res["status"] == "VERIFIED"
    assert v_res["requires_manager_approval"] is True


def test_replenishment_po_pack_rounding(engines):
    fe, opt, val = engines
    fc = fe.forecast_demand(date(2026, 10, 13), horizon_days=1, model="auto")
    demand = opt.calculate_ingredient_demand(fc)
    pos = opt.optimize_replenishment(date(2026, 10, 13), demand)

    assert len(pos) > 0, "PO lines should not be empty"
    for po in pos:
        pack_sz = po["pack_size"]
        ord_qty = po["recommended_order_qty"]
        if ord_qty > 0:
            assert ord_qty % pack_sz == 0, f"Order qty {ord_qty} must be exact multiple of pack size {pack_sz}"
        assert ord_qty >= 0, "Order qty must be non-negative"

    v_res = val.verify_replenishment_plan(pos)
    assert v_res["is_valid"] is True
    assert v_res["status"] == "VERIFIED"
    assert v_res["requires_manager_approval"] is True


def test_validator_rejects_negative_or_invalid_unit(engines):
    _, _, val = engines
    invalid_plan = [
        {"ingredient_id": "TP02", "recommended_prep_qty": -5000.0, "batch_size": 5000.0, "unit": "ml"},
        {"ingredient_id": "NL06", "recommended_prep_qty": 1500.0, "batch_size": 1000.0, "unit": "kg"}  # invalid unit and non-multiple
    ]
    res = val.verify_topping_prep_plan(invalid_plan)
    assert res["is_valid"] is False, "Validator must reject invalid plan"
    assert res["status"] == "REJECTED"
    assert len(res["violations"]) >= 2
