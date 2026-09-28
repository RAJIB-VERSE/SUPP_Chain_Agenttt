"""
forecasting.py - Demand Forecasting & Festive Spike Multiplier Engine
Part of BiscuitAI (Chunk 1)

Mental Model:
Predicts biscuit SKU demand for local kirana retail stores.
Takes historical daily sales, applies exponential smoothing to capture recent velocity,
and scales demand by an upcoming festive multiplier (e.g. Durga Puja, Diwali) based on
the 56-page FMCG distributor research.
"""

from typing import List, Dict, Any, Union
import math

# Festive Calendar with documented spike multipliers for Eastern India FMCG markets
FESTIVE_CALENDAR = {
    "DURGA_PUJA": {
        "name": "Durga Puja",
        "multiplier_default": 2.4,
        "sku_multipliers": {
            "Marie": 2.6,        # High tea-stall & household hosting consumption
            "Butter Cookie": 2.8, # Gifting & guest offerings
            "Cream Biscuit": 2.2, # Children consumption during festive outings
            "Glucose": 1.6        # Steady staple baseline
        }
    },
    "DIWALI": {
        "name": "Diwali & Kali Puja",
        "multiplier_default": 2.8,
        "sku_multipliers": {
            "Marie": 1.8,
            "Butter Cookie": 3.2, # Peak gifting
            "Cream Biscuit": 2.4,
            "Glucose": 1.4
        }
    },
    "REGULAR": {
        "name": "Regular Non-Festive",
        "multiplier_default": 1.0,
        "sku_multipliers": {}
    }
}


def calculate_average_daily_demand(sales_history: List[float], alpha: float = 0.3) -> float:
    """
    Calculates weighted average daily demand using Single Exponential Smoothing.
    
    Formula: S_t = alpha * Y_t + (1 - alpha) * S_{t-1}
    Gives more weight to recent days while preserving historical baseline.
    
    Args:
        sales_history: List of sales figures (oldest to newest), e.g. [12, 14, 15, 18, 16]
        alpha: Smoothing factor between 0.0 and 1.0 exclusive (default 0.3)
        
    Returns:
        Smoothed daily demand estimate (float, rounded to 2 decimals)
    """
    if not sales_history:
        return 0.0

    # Bug fix: alpha must be strictly between 0 and 1 for smoothing to be meaningful
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be between 0.0 and 1.0 exclusive, got {alpha}")

    # Guard against invalid negative numbers in historical data
    cleaned = [max(0.0, float(x)) for x in sales_history]
    
    # Initialize smoothed value with first observation
    smoothed = cleaned[0]
    for actual in cleaned[1:]:
        smoothed = (alpha * actual) + ((1.0 - alpha) * smoothed)
        
    return round(smoothed, 2)


def get_festive_multiplier(festival_key: str, category: str = "General") -> float:
    """
    Retrieves the multiplier factor based on upcoming festive season and biscuit category.
    """
    if not isinstance(festival_key, str) or not festival_key.strip():
        festival_key = "REGULAR"
    festival = FESTIVE_CALENDAR.get(festival_key.upper(), FESTIVE_CALENDAR["REGULAR"])
    sku_multipliers = festival.get("sku_multipliers", {})
    
    # Look for matching SKU category
    for cat_name, mult in sku_multipliers.items():
        if cat_name.lower() in category.lower():
            return mult
            
    return festival.get("multiplier_default", 1.0)


def forecast_demand(
    sales_history: List[float],
    forecast_days: int = 7,
    festival_key: str = "REGULAR",
    category: str = "General"
) -> Dict[str, Any]:
    """
    Generates forecasted unit demand for an SKU over a forward window.
    
    Args:
        sales_history: Daily units sold in the past 7-30 days
        forecast_days: Number of days into future to predict (1 to 30)
        festival_key: "DURGA_PUJA", "DIWALI", or "REGULAR"
        category: "Marie", "Butter Cookie", "Cream Biscuit", "Glucose", etc.
        
    Returns:
        Dictionary containing daily demand, multiplier applied, total forecasted units,
        and projected daily breakdown.
    """
    if forecast_days <= 0 or forecast_days > 90:
        raise ValueError("forecast_days must be between 1 and 90")
        
    base_daily = calculate_average_daily_demand(sales_history)
    multiplier = get_festive_multiplier(festival_key, category)
    
    adjusted_daily = round(base_daily * multiplier, 2)
    total_forecasted = round(adjusted_daily * forecast_days, 1)
    
    return {
        "base_daily_demand": base_daily,
        "festival": FESTIVE_CALENDAR.get(festival_key.upper(), FESTIVE_CALENDAR["REGULAR"])["name"],
        "multiplier_applied": multiplier,
        "adjusted_daily_demand": adjusted_daily,
        "forecast_days": forecast_days,
        "total_forecasted_units": total_forecasted
    }


def assess_stockout_risk(
    current_stock: Union[int, float],
    adjusted_daily_demand: float,
    lead_time_days: int = 2,
    unit_price: float = 30.0
) -> Dict[str, Any]:
    """
    Calculates how many days of stock remain before a complete stockout occurs,
    and calculates lost revenue exposure.
    
    Args:
        current_stock: Current inventory count in store/warehouse (units or cartons)
        adjusted_daily_demand: Daily demand including festive surge
        lead_time_days: Days required for distributor delivery (typically 1-3 days)
        unit_price: Selling price per unit in INR
        
    Returns:
        Risk metrics dictionary: days_left, risk_level ('CRITICAL', 'WARNING', 'HEALTHY'),
        units_short, and estimated_revenue_loss.
    """
    # Guard: stock and price must never be negative
    current_stock = max(0, current_stock)
    unit_price = max(0.0, unit_price)

    if adjusted_daily_demand <= 0:
        days_of_inventory = 999.0
    else:
        days_of_inventory = round(current_stock / adjusted_daily_demand, 1)
        
    # Lead-time stock needed to survive until delivery arrives
    lead_time_demand = math.ceil(adjusted_daily_demand * lead_time_days)
    
    if days_of_inventory <= lead_time_days:
        risk_level = "CRITICAL"  # Stockout will happen before next delivery arrives!
        units_short = max(0, lead_time_demand - current_stock)
    elif days_of_inventory <= (lead_time_days * 2):
        risk_level = "WARNING"   # Reorder window approaching
        units_short = 0
    else:
        risk_level = "HEALTHY"
        units_short = 0
        
    projected_revenue_loss = round(units_short * unit_price, 2)
    
    return {
        "current_stock": current_stock,
        "days_of_inventory": days_of_inventory,
        "lead_time_days": lead_time_days,
        "lead_time_demand": lead_time_demand,
        "risk_level": risk_level,
        "units_short": units_short,
        "projected_revenue_loss_inr": projected_revenue_loss
    }
