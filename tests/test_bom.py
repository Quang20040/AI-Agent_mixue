import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import pandas as pd
from src.database import SessionLocal
from src.engine.bom_engine import BOMEngine
from src.models import MenuItem, RecipeBOM, Ingredient


@pytest.fixture(scope="module")
def bom_engine():
    engine = BOMEngine()
    yield engine
    engine.close()


def test_sales_summary_non_empty(bom_engine):
    df = bom_engine.get_sales_summary()
    assert not df.empty, "Sales summary should contain records"
    assert "revenue_vnd" in df.columns
    assert "quantity_sold" in df.columns
    assert (df["quantity_sold"] >= 0).all(), "Sold quantity must be non-negative"
    assert (df["revenue_vnd"] >= 0).all(), "Revenue must be non-negative"


def test_theoretical_consumption_units_and_positivity(bom_engine):
    cons = bom_engine.calculate_theoretical_consumption()
    assert not cons.empty, "Theoretical consumption must not be empty"
    allowed_units = {"g", "ml", "pcs", "cái"}
    assert set(cons["unit"].unique()).issubset(allowed_units), f"Invalid units found: {set(cons['unit'].unique())}"
    assert (cons["theoretical_usage"] >= 0).all(), "Theoretical usage must be non-negative"


def test_topping_waste_summary(bom_engine):
    waste = bom_engine.get_topping_waste_summary()
    assert not waste.empty, "Waste summary should not be empty"
    assert (waste["total_prepared"] >= waste["total_wasted"]).all(), "Prepared quantity must be >= wasted quantity"
    assert (waste["waste_rate_pct"] >= 0).all() and (waste["waste_rate_pct"] <= 100).all(), "Waste rate must be in [0, 100]%"


def test_inventory_reconciliation(bom_engine):
    recon = bom_engine.calculate_inventory_reconciliation()
    assert not recon.empty, "Reconciliation dataframe should not be empty"
    assert "variance" in recon.columns
    assert "actual_stock_count" in recon.columns
