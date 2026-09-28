import boto3
import uuid
import json

def setup_resources():
    print("Initializing AWS boto3 clients (ap-south-1)...")
    dynamodb = boto3.client('dynamodb', region_name='ap-south-1')
    s3 = boto3.client('s3', region_name='ap-south-1')
    
    # 1. Create DynamoDB Table (Zero Cost: PAY_PER_REQUEST)
    table_name = 'BiscuitAI_Inventory'
    try:
        print(f"Creating DynamoDB Table: {table_name}...")
        dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'store_id', 'KeyType': 'HASH'},  # Partition key
                {'AttributeName': 'sku_id', 'KeyType': 'RANGE'}    # Sort key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'store_id', 'AttributeType': 'S'},
                {'AttributeName': 'sku_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print("Waiting for table to become ACTIVE...")
        waiter = dynamodb.get_waiter('table_exists')
        waiter.wait(TableName=table_name)
        print("DynamoDB Table created successfully!")
    except dynamodb.exceptions.ResourceInUseException:
        print(f"DynamoDB Table '{table_name}' already exists.")

    # 2. Create S3 Bucket (Globally unique name)
    # Using a deterministic uuid based on project to avoid recreating on rerun
    bucket_suffix = uuid.uuid5(uuid.NAMESPACE_DNS, 'biscuitai.hackathon').hex[:12]
    bucket_name = f"biscuitai-ml-predictions-{bucket_suffix}"
    
    try:
        print(f"Creating S3 Bucket: {bucket_name}...")
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': 'ap-south-1'}
        )
        print("S3 Bucket created successfully!")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        print(f"S3 Bucket '{bucket_name}' already exists and is owned by you.")
    except Exception as e:
        print(f"Error creating S3 bucket: {e}")
        
    print("\n--- CONFIGURATION SUMMARY ---")
    print(f"DYNAMODB_TABLE = '{table_name}'")
    print(f"S3_BUCKET      = '{bucket_name}'")
    print("-----------------------------")
    
    # Save config to a local JSON file so our backend knows the bucket name
    config = {
        "DYNAMODB_TABLE": table_name,
        "S3_BUCKET": bucket_name
    }
    with open("backend/aws_config.json", "w") as f:
        json.dump(config, f, indent=4)
        
if __name__ == "__main__":
    setup_resources()
