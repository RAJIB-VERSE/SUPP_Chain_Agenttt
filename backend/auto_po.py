"""
auto_po.py - Automated Purchase Order & Safety Stock Optimization Engine
Part of BiscuitAI (Chunk 1)

Mental Model:
Computes the exact replenishment order quantity so a kirana store or regional distributor
never stocks out during festive surges without over-ordering.
Uses standard supply chain Operations Research formulas:
1. Demand Standard Deviation (\u03c3_D)
2. Safety Stock: SS = Z * sqrt(LeadTime) * \u03c3_D
3. Reorder Point: ROP = (Adjusted Daily Demand * LeadTime) + Safety Stock
4. Recommended Order: Order up to target inventory level, rounded to master carton size.
"""

from typing import List, Dict, Any
import math
import uuid
from datetime import datetime, timezone

# Standard Normal Distribution Z-values for target Service Levels
SERVICE_LEVEL_Z = {
    0.90: 1.28,
    0.95: 1.65,  # Default FMCG service level (95% non-stockout guarantee)
    0.98: 2.05,
    0.99: 2.33   # High-priority festive top SKUs
}


def calculate_demand_std_dev(sales_history: List[float]) -> float:
    """
    Calculates sample standard deviation of daily demand.
    """
    if len(sales_history) < 2:
        return 0.0
        
    n = len(sales_history)
    mean = sum(sales_history) / n
    variance = sum((x - mean) ** 2 for x in sales_history) / (n - 1)
    return round(math.sqrt(variance), 2)


def calculate_safety_stock(
    demand_std_dev: float,
    lead_time_days: int = 2,
    service_level: float = 0.95
) -> int:
    """
    Calculates required buffer safety stock to protect against demand volatility and lead-time delays.
    Formula: SS = Z * sqrt(LeadTime) * demand_std_dev
    """
    z_score = SERVICE_LEVEL_Z.get(service_level, 1.65)
    ss = z_score * math.sqrt(max(1, lead_time_days)) * demand_std_dev
    return max(1, math.ceil(ss))


def calculate_reorder_point(
    adjusted_daily_demand: float,
    lead_time_days: int,
    safety_stock: int
) -> int:
    """
    Calculates the inventory trigger level. When current stock <= ROP, a PO must be placed.
    Formula: ROP = (Daily Demand * Lead Time) + Safety Stock
    """
    lead_time_demand = adjusted_daily_demand * lead_time_days
    return math.ceil(lead_time_demand + safety_stock)


def calculate_recommended_order_quantity(
    current_stock: int,
    reorder_point: int,
    adjusted_daily_demand: float,
    target_cover_days: int = 14,
    units_per_carton: int = 24
) -> Dict[str, Any]:
    """
    Calculates cartons to order to bring inventory up to the target cover level.
    Rounds up to full master carton units.
    """
    # Guard: demand and cover days must be positive for a meaningful order calculation
    if adjusted_daily_demand <= 0 or target_cover_days <= 0:
        return {
            "should_reorder": False,
            "target_inventory": reorder_point,
            "cartons_to_order": 0,
            "units_to_order": 0,
            "units_per_carton": units_per_carton
        }

    target_inventory = math.ceil(adjusted_daily_demand * target_cover_days) + reorder_point
    deficit = max(0, target_inventory - current_stock)
    
    if deficit == 0:
        cartons_to_order = 0
        total_units = 0
        should_reorder = False
    else:
        # Round up to full master carton packages
        cartons_to_order = math.ceil(deficit / units_per_carton)
        total_units = cartons_to_order * units_per_carton
        should_reorder = current_stock <= reorder_point

    return {
        "should_reorder": should_reorder,
        "target_inventory": target_inventory,
        "cartons_to_order": cartons_to_order,
        "units_to_order": total_units,
        "units_per_carton": units_per_carton
    }


def generate_draft_purchase_order(
    store_id: str,
    store_name: str,
    distributor_name: str,
    sku_items: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generates a consolidated Purchase Order containing all SKUs that need replenishment.
    
    Args:
        store_id: ID of the retail store placing/receiving the order
        store_name: Name of kirana/retail outlet
        distributor_name: Assigned regional FMCG distributor
        sku_items: List of evaluated SKU dictionaries with quantities and prices
        
    Returns:
        Structured PO dictionary ready for approval and transmission
    """
    now = datetime.now(timezone.utc)
    po_id = f"PO-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    line_items = []
    total_cartons = 0
    gross_amount = 0.0
    
    for item in sku_items:
        cartons = item.get("cartons_to_order", 0)
        if cartons > 0:
            price_per_carton = item.get("price_per_carton", 720.0)
            line_total = round(cartons * price_per_carton, 2)
            
            line_items.append({
                "sku_id": item.get("sku_id"),
                "sku_name": item.get("sku_name"),
                "category": item.get("category"),
                "cartons": cartons,
                "units": item.get("units_to_order", cartons * 24),
                "price_per_carton": price_per_carton,
                "line_total": line_total
            })
            total_cartons += cartons
            gross_amount += line_total
            
    # Apply standard distributor slab discount (e.g. 3% for orders > 50 cartons)
    discount_pct = 3.0 if total_cartons >= 50 else (1.5 if total_cartons >= 25 else 0.0)
    discount_amount = round(gross_amount * (discount_pct / 100.0), 2)
    net_amount = round(gross_amount - discount_amount, 2)
    
    return {
        "po_id": po_id,
        "created_at": now.isoformat(),
        "store_id": store_id,
        "store_name": store_name,
        "distributor_name": distributor_name,
        "line_items": line_items,
        "item_count": len(line_items),
        "total_cartons": total_cartons,
        "gross_amount_inr": gross_amount,
        "discount_percent": discount_pct,
        "discount_amount_inr": discount_amount,
        "net_amount_inr": net_amount,
        "status": "DRAFT"  # Transitions to 'APPROVED' -> 'DISPATCHED'
    }
