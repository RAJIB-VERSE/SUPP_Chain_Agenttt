"""
seed_data.py - Grounded Seed Data for Kolkata & Howrah FMCG Biscuit Distribution
Part of BiscuitAI (Chunk 1)

Mental Model:
Provides authentic test data representing regional retail kirana stores, popular biscuit SKUs,
and historical daily sales data matching the 56-page FMCG supply chain study.
"""

from typing import List, Dict, Any

STORES: List[Dict[str, Any]] = [
    {
        "store_id": "STR-001",
        "name": "Ghosh Brothers General Store",
        "owner": "Subrata Ghosh",
        "cluster": "Shyambazar",
        "city": "North Kolkata",
        "phone": "+91 98301 23451",
        "daily_footfall": 320,
        "lead_time_days": 1,
        "lat": 22.6025,
        "lng": 88.3732
    },
    {
        "store_id": "STR-002",
        "name": "Bhowmick Variety Stores",
        "owner": "Alok Bhowmick",
        "cluster": "Gariahat",
        "city": "South Kolkata",
        "phone": "+91 98302 34562",
        "daily_footfall": 450,
        "lead_time_days": 2,
        "lat": 22.5195,
        "lng": 88.3653
    },
    {
        "store_id": "STR-003",
        "name": "Mondal Kirana Corner",
        "owner": "Prabir Mondal",
        "cluster": "Howrah Station Road",
        "city": "Howrah",
        "phone": "+91 98303 45673",
        "daily_footfall": 580,
        "lead_time_days": 1,
        "lat": 22.5850,
        "lng": 88.3426
    },
    {
        "store_id": "STR-004",
        "name": "Sen & Co Grocery",
        "owner": "Anirban Sen",
        "cluster": "Salt Lake Sector 1",
        "city": "East Kolkata",
        "phone": "+91 98304 56784",
        "daily_footfall": 290,
        "lead_time_days": 2,
        "lat": 22.5867,
        "lng": 88.4178
    },
    {
        "store_id": "STR-005",
        "name": "Das Departmental",
        "owner": "Tapan Das",
        "cluster": "Behala Tram Depot",
        "city": "South West Kolkata",
        "phone": "+91 98305 67895",
        "daily_footfall": 380,
        "lead_time_days": 2,
        "lat": 22.4988,
        "lng": 88.3149
    },
    {
        "store_id": "STR-006",
        "name": "Roy Provision Store",
        "owner": "Debabrata Roy",
        "cluster": "New Town Action Area 1",
        "city": "New Town",
        "phone": "+91 98306 78906",
        "daily_footfall": 410,
        "lead_time_days": 2,
        "lat": 22.5898,
        "lng": 88.4716
    }
]

SKUS: List[Dict[str, Any]] = [
    {
        "sku_id": "SKU-001",
        "name": "Biskfarm Marie Classic",
        "brand": "Biskfarm",
        "category": "Marie",
        "weight_grams": 250,
        "unit_price_inr": 30.0,
        "units_per_carton": 24,
        "carton_price_inr": 720.0
    },
    {
        "sku_id": "SKU-002",
        "name": "Britannia Marie Gold",
        "brand": "Britannia",
        "category": "Marie",
        "weight_grams": 300,
        "unit_price_inr": 35.0,
        "units_per_carton": 24,
        "carton_price_inr": 840.0
    },
    {
        "sku_id": "SKU-003",
        "name": "Parle-G Gold",
        "brand": "Parle",
        "category": "Glucose",
        "weight_grams": 250,
        "unit_price_inr": 25.0,
        "units_per_carton": 30,
        "carton_price_inr": 750.0
    },
    {
        "sku_id": "SKU-004",
        "name": "Biskfarm Top Butter Cookie",
        "brand": "Biskfarm",
        "category": "Butter Cookie",
        "weight_grams": 200,
        "unit_price_inr": 40.0,
        "units_per_carton": 20,
        "carton_price_inr": 800.0
    },
    {
        "sku_id": "SKU-005",
        "name": "Britannia Good Day Butter",
        "brand": "Britannia",
        "category": "Butter Cookie",
        "weight_grams": 200,
        "unit_price_inr": 45.0,
        "units_per_carton": 20,
        "carton_price_inr": 900.0
    },
    {
        "sku_id": "SKU-006",
        "name": "Sunfeast Dark Fantasy Choco Fills",
        "brand": "ITC Sunfeast",
        "category": "Cream Biscuit",
        "weight_grams": 150,
        "unit_price_inr": 50.0,
        "units_per_carton": 16,
        "carton_price_inr": 800.0
    },
    {
        "sku_id": "SKU-007",
        "name": "Oreo Original Vanilla",
        "brand": "Cadbury",
        "category": "Cream Biscuit",
        "weight_grams": 120,
        "unit_price_inr": 30.0,
        "units_per_carton": 24,
        "carton_price_inr": 720.0
    },
    {
        "sku_id": "SKU-008",
        "name": "Anmol Dream Lite",
        "brand": "Anmol",
        "category": "Salty Biscuit",
        "weight_grams": 200,
        "unit_price_inr": 25.0,
        "units_per_carton": 30,
        "carton_price_inr": 750.0
    },
    {
        "sku_id": "SKU-009",
        "name": "Priya Marie",
        "brand": "Priya",
        "category": "Marie",
        "weight_grams": 250,
        "unit_price_inr": 28.0,
        "units_per_carton": 24,
        "carton_price_inr": 672.0
    },
    {
        "sku_id": "SKU-010",
        "name": "Britannia 50-50 Maska Chaska",
        "brand": "Britannia",
        "category": "Salty Biscuit",
        "weight_grams": 120,
        "unit_price_inr": 20.0,
        "units_per_carton": 36,
        "carton_price_inr": 720.0
    }
]

# Baseline store inventory state and 14-day sales history for simulation
STORE_INVENTORY_SEED: List[Dict[str, Any]] = [
    {
        "store_id": "STR-001",
        "sku_id": "SKU-001",
        "current_stock_units": 18,  # Critical: Low stock for high-demand Marie
        "sales_history_14d": [20, 22, 19, 25, 23, 24, 21, 26, 28, 24, 27, 25, 29, 30]
    },
    {
        "store_id": "STR-001",
        "sku_id": "SKU-004",
        "current_stock_units": 12,  # Critical for Butter Cookie during festive
        "sales_history_14d": [10, 11, 12, 14, 13, 15, 12, 16, 17, 15, 18, 16, 19, 20]
    },
    {
        "store_id": "STR-001",
        "sku_id": "SKU-003",
        "current_stock_units": 45,
        "sales_history_14d": [15, 16, 14, 18, 17, 20, 16, 19, 21, 18, 22, 19, 23, 24]
    },
    {
        "store_id": "STR-001",
        "sku_id": "SKU-005",
        "current_stock_units": 8,  # Critical: Low stock
        "sales_history_14d": [5, 6, 7, 5, 8, 6, 9, 8, 10, 7, 9, 11, 8, 12]
    },
    {
        "store_id": "STR-001",
        "sku_id": "SKU-006",
        "current_stock_units": 32,
        "sales_history_14d": [8, 9, 7, 10, 11, 9, 12, 10, 13, 11, 14, 12, 15, 14]
    },
    {
        "store_id": "STR-001",
        "sku_id": "SKU-007",
        "current_stock_units": 55,
        "sales_history_14d": [10, 12, 11, 14, 13, 15, 12, 16, 14, 15, 18, 16, 19, 20]
    },
    {
        "store_id": "STR-001",
        "sku_id": "SKU-008",
        "current_stock_units": 15, # Critical: Low stock
        "sales_history_14d": [12, 14, 13, 16, 15, 18, 14, 19, 17, 16, 21, 18, 22, 24]
    },
    {
        "store_id": "STR-001",
        "sku_id": "SKU-010",
        "current_stock_units": 40,
        "sales_history_14d": [20, 19, 22, 21, 24, 23, 25, 24, 27, 26, 28, 27, 30, 29]
    },
    {
        "store_id": "STR-002",
        "sku_id": "SKU-002",
        "current_stock_units": 65,  # Warning: Moderate stock
        "sales_history_14d": [30, 32, 28, 35, 34, 38, 32, 36, 40, 35, 39, 41, 42, 45]
    },
    {
        "store_id": "STR-002",
        "sku_id": "SKU-005",
        "current_stock_units": 24,  # Warning
        "sales_history_14d": [18, 19, 22, 21, 24, 23, 20, 25, 28, 26, 29, 31, 30, 32]
    },
    {
        "store_id": "STR-003",
        "sku_id": "SKU-001",
        "current_stock_units": 8,   # Critical: Almost empty at Howrah Station
        "sales_history_14d": [35, 38, 40, 42, 39, 45, 41, 48, 50, 46, 52, 49, 55, 58]
    },
    {
        "store_id": "STR-003",
        "sku_id": "SKU-003",
        "current_stock_units": 150, # Healthy stock of Glucose
        "sales_history_14d": [25, 24, 26, 28, 25, 27, 26, 28, 30, 27, 29, 28, 31, 32]
    },
    {
        "store_id": "STR-004",
        "sku_id": "SKU-006",
        "current_stock_units": 10,  # Critical: Dark Fantasy in Salt Lake
        "sales_history_14d": [12, 14, 15, 16, 13, 17, 15, 19, 21, 18, 22, 20, 24, 25]
    }
]
