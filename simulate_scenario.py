import boto3
import json

def simulate_stockout():
    print("Connecting to DynamoDB: BiscuitAI_Inventory...")
    dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
    table = dynamodb.Table('BiscuitAI_Inventory')
    
    # We will simulate a massive festive spike where SKU-101 and SKU-201 almost run out of stock
    updates = [
        {"store_id": "STR-001", "sku_id": "SKU-101", "new_stock": 10}, # Critical!
        {"store_id": "STR-001", "sku_id": "SKU-102", "new_stock": 250}, # Healthy
        {"store_id": "STR-002", "sku_id": "SKU-201", "new_stock": 5}   # Critical!
    ]
    
    for u in updates:
        table.update_item(
            Key={'store_id': u['store_id'], 'sku_id': u['sku_id']},
            UpdateExpression="SET current_stock_units = :val",
            ExpressionAttributeValues={':val': u['new_stock']}
        )
        print(f"Updated {u['store_id']} | {u['sku_id']} -> Current Stock: {u['new_stock']}")

    print("\nSimulation complete! Go back to your frontend UI and:")
    print("1. Refresh the page to see the Critical alerts on the Dashboard.")
    print("2. Navigate to the Auto-PO tab and click 'Generate New PO' to see OmniStock AI create emergency replenishment orders.")

if __name__ == "__main__":
    simulate_stockout()
