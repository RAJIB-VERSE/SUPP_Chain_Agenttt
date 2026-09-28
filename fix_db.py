import boto3

def fix_db():
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
            UpdateExpression="SET current_stock_units = :val REMOVE current_stock",
            ExpressionAttributeValues={':val': u['new_stock']}
        )
        print(f"Fixed {u['store_id']} | {u['sku_id']} -> Current Stock Units: {u['new_stock']}")

if __name__ == "__main__":
    fix_db()
