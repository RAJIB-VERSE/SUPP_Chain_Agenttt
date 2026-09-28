"""
test_core_logic.py - Unit Tests for Chunk 1 (Forecasting, Auto-PO & Promotions)
Part of BiscuitAI

Mental Model:
Runs deterministic checks verifying that our mathematical formulas,
festive calendar multipliers, safety stock calculations, and draft PO generators
operate flawlessly before we attach any API or cloud layer.
Includes edge case and security regression tests added during cross-verification.
"""

import sys
import os

# Add backend to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from forecasting import (
    calculate_average_daily_demand,
    get_festive_multiplier,
    forecast_demand,
    assess_stockout_risk
)
from auto_po import (
    calculate_demand_std_dev,
    calculate_safety_stock,
    calculate_reorder_point,
    calculate_recommended_order_quantity,
    generate_draft_purchase_order
)
from promotions import generate_promotional_message


# ─── CORE LOGIC TESTS ────────────────────────────────────────────────────────

def test_exponential_smoothing_demand():
    history = [10, 12, 14, 16, 18]
    smoothed = calculate_average_daily_demand(history, alpha=0.3)
    assert smoothed > 10.0 and smoothed <= 18.0, f"Expected smoothed between 10 and 18, got {smoothed}"
    print("PASS: test_exponential_smoothing_demand")


def test_festive_multipliers():
    dp_marie = get_festive_multiplier("DURGA_PUJA", "Marie Classic")
    assert dp_marie == 2.6, f"Expected 2.6, got {dp_marie}"

    diwali_butter = get_festive_multiplier("DIWALI", "Butter Cookie")
    assert diwali_butter == 3.2, f"Expected 3.2, got {diwali_butter}"

    regular = get_festive_multiplier("REGULAR", "Marie Classic")
    assert regular == 1.0, f"Expected 1.0, got {regular}"

    # Unknown festival key should fall back gracefully to REGULAR (1.0)
    unknown = get_festive_multiplier("CHRISTMAS", "Marie")
    assert unknown == 1.0, f"Expected 1.0 fallback for unknown festival, got {unknown}"
    print("PASS: test_festive_multipliers")


def test_stockout_risk_assessment():
    risk = assess_stockout_risk(
        current_stock=15,
        adjusted_daily_demand=20.0,
        lead_time_days=2,
        unit_price=30.0
    )
    assert risk["risk_level"] == "CRITICAL", f"Expected CRITICAL, got {risk['risk_level']}"
    assert risk["days_of_inventory"] == 0.8
    assert risk["units_short"] == 25
    assert risk["projected_revenue_loss_inr"] == 750.0
    print("PASS: test_stockout_risk_assessment")


def test_safety_stock_and_reorder_point():
    sales = [20, 25, 22, 28, 24, 26, 23]
    std_dev = calculate_demand_std_dev(sales)
    assert std_dev > 0.0

    ss = calculate_safety_stock(std_dev, lead_time_days=2, service_level=0.95)
    assert ss >= 1

    daily_demand = 25.0
    rop = calculate_reorder_point(daily_demand, lead_time_days=2, safety_stock=ss)
    assert rop == 50 + ss
    print("PASS: test_safety_stock_and_reorder_point")


def test_auto_po_generation():
    items = [
        {
            "sku_id": "SKU-001",
            "sku_name": "Biskfarm Marie Classic",
            "category": "Marie",
            "cartons_to_order": 10,
            "units_to_order": 240,
            "price_per_carton": 720.0
        },
        {
            "sku_id": "SKU-004",
            "sku_name": "Biskfarm Top Butter Cookie",
            "category": "Butter Cookie",
            "cartons_to_order": 20,
            "units_to_order": 400,
            "price_per_carton": 800.0
        }
    ]
    po = generate_draft_purchase_order(
        store_id="STR-001",
        store_name="Ghosh Brothers General Store",
        distributor_name="Maa Tara FMCG Distributors",
        sku_items=items
    )
    assert po["po_id"].startswith("PO-")
    assert po["total_cartons"] == 30
    assert po["gross_amount_inr"] == (10 * 720.0) + (20 * 800.0)
    assert po["discount_percent"] == 1.5
    assert po["net_amount_inr"] == round(23200 - (23200 * 0.015), 2)
    assert po["status"] == "DRAFT"
    print("PASS: test_auto_po_generation")


def test_multilingual_promotions():
    promo = generate_promotional_message(
        sku_name="Biskfarm Marie Classic",
        recommended_cartons=15,
        festival_key="DURGA_PUJA",
        discount_pct=5.0
    )
    assert "Durga Puja" in promo["english"]
    assert "দুর্গাপূজা" in promo["bengali"]
    assert "दुर्गा पूजा" in promo["hindi"]
    assert "15" in promo["english"]
    print("PASS: test_multilingual_promotions")


# ─── EDGE CASE & SECURITY REGRESSION TESTS ───────────────────────────────────

def test_alpha_boundary_guard():
    """Alpha = 0 or 1 are degenerate values and must be rejected with ValueError."""
    try:
        calculate_average_daily_demand([10, 12], alpha=0.0)
        assert False, "Should have raised ValueError for alpha=0.0"
    except ValueError:
        pass

    try:
        calculate_average_daily_demand([10, 12], alpha=1.0)
        assert False, "Should have raised ValueError for alpha=1.0"
    except ValueError:
        pass
    print("PASS: test_alpha_boundary_guard")


def test_negative_stock_guard():
    """Negative stock values must be clamped to 0, not cause negative risk results."""
    risk = assess_stockout_risk(
        current_stock=-50,
        adjusted_daily_demand=20.0,
        lead_time_days=2,
        unit_price=30.0
    )
    assert risk["current_stock"] == 0, "Negative stock must be clamped to 0"
    assert risk["risk_level"] == "CRITICAL"
    print("PASS: test_negative_stock_guard")


def test_zero_demand_order_quantity_guard():
    """Zero demand must return a safe no-order response, not crash."""
    result = calculate_recommended_order_quantity(
        current_stock=50,
        reorder_point=20,
        adjusted_daily_demand=0.0,
        target_cover_days=14
    )
    assert result["cartons_to_order"] == 0
    assert result["should_reorder"] is False
    print("PASS: test_zero_demand_order_quantity_guard")


def test_template_injection_sanitisation():
    """Malicious sku_name with braces must not hijack str.format() template."""
    promo = generate_promotional_message(
        sku_name="{english}",
        recommended_cartons=5,
        festival_key="REGULAR"
    )
    assert "{english}" not in promo["english"]
    assert "{english}" not in promo["bengali"]
    assert "{english}" not in promo["hindi"]
    # After stripping braces, name becomes "english", not the literal injection
    assert promo["sku_name"] == "english"
    print("PASS: test_template_injection_sanitisation")


if __name__ == "__main__":
    print("--- RUNNING CHUNK 1 UNIT TESTS (CROSS-VERIFICATION) ---")
    # Core logic
    test_exponential_smoothing_demand()
    test_festive_multipliers()
    test_stockout_risk_assessment()
    test_safety_stock_and_reorder_point()
    test_auto_po_generation()
    test_multilingual_promotions()
    # Edge cases & security regression
    test_alpha_boundary_guard()
    test_negative_stock_guard()
    test_zero_demand_order_quantity_guard()
    test_template_injection_sanitisation()
    print("--- ALL 10 CHUNK 1 TESTS PASSED SUCCESSFULLY! ---")
