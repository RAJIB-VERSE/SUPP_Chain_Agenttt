import boto3
import json
from decimal import Decimal

# Import our hardcoded seed data
from backend.seed_data import STORE_INVENTORY_SEED

def float_to_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: float_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [float_to_decimal(x) for x in obj]
    return obj

def seed_dynamodb():
    print("Connecting to DynamoDB...")
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    
    with open("backend/aws_config.json", "r") as f:
        config = json.load(f)
        
    table = dynamodb.Table(config["DYNAMODB_TABLE"])
    
    print(f"Seeding {len(STORE_INVENTORY_SEED)} records into {config['DYNAMODB_TABLE']}...")
    with table.batch_writer() as batch:
        for record in STORE_INVENTORY_SEED:
            # DynamoDB requires floats to be Decimal
            dec_record = float_to_decimal(record)
            batch.put_item(Item=dec_record)
            
    print("Seeding complete! DynamoDB now holds the live inventory data.")

if __name__ == "__main__":
    seed_dynamodb()
