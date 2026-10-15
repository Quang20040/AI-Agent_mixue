"""Phase 3 Regression Tests — Verifying P0/P1/P2 fixes and non-regression.

Covers:
1. Password Security: PBKDF2-HMAC-SHA256, constant-time comparison, no plaintext backdoor, legacy migration.
2. Shift Closing: JSON persistence preserving POS reconciliation audit fields.
3. Inventory & Daily Stock: Idempotency / duplicate request detection within 3 seconds.
4. BOM Engine: Opening inventory (initial_stock) inclusion in reconciliation formula.
5. Forecasting Performance: Caching mechanism ensuring sub-second response times.
"""

import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.auth import check_password, hash_password
from src.engine.bom_engine import BOMEngine
from src.engine.daily_stock_service import create_stock_request, delete_stock_movement
from src.engine.forecasting import ForecastingEngine
from src.engine.shift_service import delete_shift_report, save_or_update_shift_report


def test_password_security_pbkdf2_and_no_backdoors():
    """Verify PBKDF2 salted hashing, timing-safe check, and elimination of plaintext fallback."""
    raw_password = "SecretPassword123!"
    hashed = hash_password(raw_password)

    # 1. Must use pbkdf2_sha256 format with 100,000 iterations
    assert hashed.startswith("pbkdf2_sha256$100000$")
    parts = hashed.split("$")
    assert len(parts) == 4
    salt, hash_val = parts[2], parts[3]
    assert len(salt) == 32  # 16-byte hex
    assert len(hash_val) == 64  # sha256 hex digest

    # 2. Correct password verifies successfully
    assert check_password(raw_password, hashed) is True

    # 3. Wrong password fails
    assert check_password("WrongPassword123!", hashed) is False

    # 4. Plaintext fallback backdoor is completely eliminated
    # Passing the exact string as both password and stored_hash must return False (not True)
    assert check_password("my_plain_pass", "my_plain_pass") is False

    # 5. Legacy SHA-256 hash backward compatibility
    import hashlib
    legacy_sha256 = hashlib.sha256(b"legacy123").hexdigest()
    assert check_password("legacy123", legacy_sha256) is True
    assert check_password("wrong", legacy_sha256) is False


def test_shift_report_preserves_reconciliation_fields():
    """Verify that updating a shift report merges fields and preserves POS reconciliation."""
    test_shift_id = "SHIFT_TEST_REGRESSION_P3"
    
    # 1. Create initial report with POS reconciliation fields
    initial_report = {
        "shift_id": test_shift_id,
        "date": "2026-10-15",
        "shift_type": "CA_CHIEU",
        "leader": "TestLeader",
        "signed_by": "TestLeader",
        "total_revenue": 5000000,
        "pos_collected_vnd": 4950000,
        "cash_collected_vnd": 3000000,
        "banking_transfer_vnd": 1950000,
        "variance_pos_vnd": -50000,
        "reconciliation_status": "KHỚP LỆCH NHẸ",
        "status": "DRAFT"
    }
    ok, _msg, saved_initial = save_or_update_shift_report(initial_report)
    assert ok is True
    assert saved_initial["shift_id"] == test_shift_id
    assert saved_initial["pos_collected_vnd"] == 4950000

    # 2. Update only status and notes (simulating an edit from UI)
    update_payload = {
        "shift_id": test_shift_id,
        "status": "APPROVED",
        "notes": "Đã duyệt bởi Quản lý"
    }
    ok_up, _msg_up, saved_updated = save_or_update_shift_report(update_payload)
    assert ok_up is True

    # 3. Verify POS audit fields were preserved
    assert saved_updated["status"] == "APPROVED"
    assert saved_updated["notes"] == "Đã duyệt bởi Quản lý"
    assert saved_updated["pos_collected_vnd"] == 4950000
    assert saved_updated["signed_by"] == "TestLeader"
    assert saved_updated["variance_pos_vnd"] == -50000

    # Cleanup test report from JSON
    delete_shift_report(test_shift_id)


def test_stock_request_duplicate_prevention():
    """Verify that identical stock requests within 3 seconds are rejected as DUPLICATE."""
    test_date = date(2026, 10, 25)
    test_ing = "1"
    
    # 1. First submission succeeds
    res1 = create_stock_request(
        business_date=test_date,
        ingredient_id=test_ing,
        movement_type="IN",
        quantity=5.0,
        recorded_by="test_user_dup",
        user_role="STAFF",
        notes="First submission"
    )
    assert res1["status"] == "SUCCESS"
    req_id = res1["request_id"]

    try:
        # 2. Immediate second submission with identical params returns DUPLICATE
        res2 = create_stock_request(
            business_date=test_date,
            ingredient_id=test_ing,
            movement_type="IN",
            quantity=5.0,
            recorded_by="test_user_dup",
            user_role="STAFF",
            notes="Rapid double click"
        )
        assert res2["status"] == "DUPLICATE"
        assert "tránh trùng lặp" in res2["message"]
    finally:
        # Cleanup created movement
        delete_stock_movement(req_id, "admin")


def test_bom_inventory_reconciliation_with_initial_stock():
    """Verify that BOM inventory reconciliation incorporates initial stock."""
    bom_engine = BOMEngine()
    reconciliation_df = bom_engine.calculate_inventory_reconciliation()
    assert not reconciliation_df.empty
    assert len(reconciliation_df) > 0

    # Verify required reconciliation audit columns exist
    expected_cols = [
        "ingredient_id", "ingredient_name", "initial_stock",
        "theoretical_usage", "total_purchased", "actual_stock_count",
        "expected_stock", "variance", "variance_pct"
    ]
    for col in expected_cols:
        assert col in reconciliation_df.columns, f"Missing column: {col}"

    # Verify expected_stock formula: initial_stock + total_purchased - theoretical_usage
    row = reconciliation_df.iloc[0]
    expected_calc = round(row["initial_stock"] + row["total_purchased"] - row["theoretical_usage"], 2)
    assert abs(row["expected_stock"] - expected_calc) < 1e-2

    # Variance formula: actual_stock_count - expected_stock
    calc_variance = round(row["actual_stock_count"] - row["expected_stock"], 2)
    assert abs(row["variance"] - calc_variance) < 1e-2


def test_forecasting_caching_and_subsecond_latency():
    """Verify that forecasting engine caches backtest results and responds within sub-seconds."""
    fc_engine = ForecastingEngine()

    # First call (populates cache)
    t0 = time.time()
    res1 = fc_engine.run_backtest(start_eval_day=15)
    t_first = time.time() - t0
    assert t_first >= 0
    assert "aggregate_metrics" in res1
    assert "best_model" in res1

    # Second call (must be served from cache in under 0.1s)
    t1 = time.time()
    res2 = fc_engine.run_backtest(start_eval_day=15)
    t_second = time.time() - t1
    assert res2 == res1
    assert t_second < 0.1, f"Cached backtest took too long: {t_second:.4f}s"
