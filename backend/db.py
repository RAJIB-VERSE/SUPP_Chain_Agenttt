import boto3
import json
import csv
import os
from boto3.dynamodb.conditions import Key
from decimal import Decimal

# Load AWS Config created during resource setup
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "aws_config.json")
try:
    with open(CONFIG_PATH, "r") as f:
        AWS_CONFIG = json.load(f)
except FileNotFoundError:
    AWS_CONFIG = {
        "DYNAMODB_TABLE": "BiscuitAI_Inventory",
        "S3_BUCKET": ""
    }

# Initialize boto3 clients for us-east-1
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
s3_client = boto3.client('s3', region_name='ap-south-1')

# In-memory cache for ML forecasts to avoid fetching S3 CSV on every request
_ml_forecast_cache = None

def float_to_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: float_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [float_to_decimal(x) for x in obj]
    return obj

def decimal_to_float(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [decimal_to_float(x) for x in obj]
    return obj

def get_inventory(store_id=None, sku_id=None):
    """
    Fetches live inventory records from DynamoDB.
    - If store_id and sku_id: gets specific item (O(1))
    - If store_id only: queries all SKUs for that store (O(N))
    - If neither: scans entire table (O(Total))
    """
    table = dynamodb.Table(AWS_CONFIG["DYNAMODB_TABLE"])
    
    if store_id and sku_id:
        response = table.get_item(Key={'store_id': store_id, 'sku_id': sku_id})
        item = response.get('Item')
        return [decimal_to_float(item)] if item else []
        
    elif store_id:
        response = table.query(
            KeyConditionExpression=Key('store_id').eq(store_id)
        )
        return decimal_to_float(response.get('Items', []))
        
    else:
        # Scan entire table
        response = table.scan()
        return decimal_to_float(response.get('Items', []))

def fetch_ml_predictions_from_s3():
    """
    Downloads the ML forecasts CSV from S3 and parses it into memory.
    """
    global _ml_forecast_cache
    if not AWS_CONFIG["S3_BUCKET"]:
        return []
        
    try:
        response = s3_client.get_object(
            Bucket=AWS_CONFIG["S3_BUCKET"],
            Key="forecasts/ml_forecasts.csv"
        )
        lines = response['Body'].read().decode('utf-8').splitlines()
        reader = csv.DictReader(lines)
        
        cache = []
        for row in reader:
            cache.append({
                "store_id": row["store_id"],
                "sku_id": row["sku_id"],
                "festival_key": row["festival_key"],
                "ml_predicted_cartons": float(row["ml_predicted_cartons"]),
                "generated_at": row["generated_at"]
            })
        _ml_forecast_cache = cache
        return cache
    except Exception as e:
        print(f"Failed to fetch ML predictions from S3: {e}")
        return []

def get_ml_prediction(store_id, sku_id, festival_key):
    """
    Retrieves the ML prediction for a specific store/sku/festival.
    Uses the cached S3 CSV if available.
    """
    global _ml_forecast_cache
    if _ml_forecast_cache is None:
        fetch_ml_predictions_from_s3()
        
    if not _ml_forecast_cache:
        return None
        
    for record in _ml_forecast_cache:
        if (record["store_id"] == store_id and 
            record["sku_id"] == sku_id and 
            record["festival_key"] == festival_key):
            return record["ml_predicted_cartons"]
            
    return None
