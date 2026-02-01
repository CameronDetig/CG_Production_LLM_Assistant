"""
Local testing script for Lambda function.
Run this to test functionality with a local database before deploying to AWS.
"""

import json
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add backend directory to path (parent of testing/)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lambda_function import lambda_handler


def test_database_connection():
    """Test PostgreSQL database connectivity"""
    from src.services.database import get_connection, release_connection
    
    print("Testing PostgreSQL database connection...")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Test basic connection
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ PostgreSQL connected successfully!")
        print(f"   Version: {version[0][:50]}...")
        
        # Test pgvector extension
        cursor.execute("SELECT COUNT(*) FROM files;")
        file_count = cursor.fetchone()[0]
        print(f"   Files in database: {file_count}")
        
        cursor.close()
        release_connection(conn)
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        return False


def test_dynamodb_connection():
    """Test DynamoDB connectivity"""
    import boto3
    from botocore.exceptions import ClientError
    
    print("Testing DynamoDB connection...")
    
    try:
        # Get table name from environment
        table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'cg-chatbot-conversations')
        region = os.environ.get('AWS_REGION', 'us-east-1')
        
        dynamodb = boto3.resource('dynamodb', region_name=region)
        table = dynamodb.Table(table_name)
        
        # Test table access
        response = table.table_status
        print(f"✅ DynamoDB connected successfully!")
        print(f"   Table: {table_name}")
        print(f"   Status: {response}")
        
        # Get item count (approximate)
        item_count = table.item_count
        print(f"   Approximate conversations: {item_count}")
        
        return True
        
    except ClientError as e:
        print(f"❌ DynamoDB connection failed: {str(e)}")
        print(f"   Make sure table '{table_name}' exists in region '{region}'")
        return False
    except Exception as e:
        print(f"❌ DynamoDB connection failed: {str(e)}")
        return False


def test_s3_connection():
    """Test S3 connectivity"""
    import boto3
    from botocore.exceptions import ClientError
    
    print("Testing S3 connection...")
    
    try:
        bucket_name = os.environ.get('S3_BUCKET_NAME')
        if not bucket_name:
            print("⚠️  S3_BUCKET_NAME not set, skipping S3 test")
            return True
        
        region = os.environ.get('AWS_REGION', 'us-east-1')
        s3 = boto3.client('s3', region_name=region)
        
        # Test bucket access
        response = s3.head_bucket(Bucket=bucket_name)
        print(f"✅ S3 connected successfully!")
        print(f"   Bucket: {bucket_name}")
        
        # List a few objects
        objects = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=5)
        if 'Contents' in objects:
            print(f"   Objects found: {objects['KeyCount']}")
        
        return True
        
    except ClientError as e:
        print(f"❌ S3 connection failed: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ S3 connection failed: {str(e)}")
        return False


def test_bedrock_connection():
    """Test Bedrock API connectivity"""
    import boto3
    from botocore.exceptions import ClientError
    
    print("Testing Bedrock connection...")
    
    try:
        region = os.environ.get('AWS_REGION', 'us-east-1')
        model_id = os.environ.get('BEDROCK_MODEL_ID', 'us.meta.llama3-2-11b-instruct-v1:0')
        
        bedrock = boto3.client('bedrock-runtime', region_name=region)
        
        # Simple test prompt (generic structure)
        test_prompt = "Hello! Who are you?"
        
        # Determine parameters and body structure based on model
        if "llama" in model_id.lower():
            # Llama on Bedrock (often uses prompt + max_gen_len)
            # Note: newer Llama 3 on Bedrock might also support/prefer messages, 
            # but legacy/custom setups often use the completion API.
            body = {
                "prompt": test_prompt,
                "max_gen_len": 50,
                "temperature": 0.7
            }
        else:
            # Assume OpenAI-like / Chat format for others (like openai.gpt-oss-...)
            # This expects a "messages" array
            body = {
                "messages": [
                    {"role": "user", "content": test_prompt}
                ],
                "max_tokens": 50,
                "temperature": 0.7
            }

        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps(body)
        )
        
        print(f"✅ Bedrock connected successfully!")
        print(f"   Model: {model_id}")
        
        return True
        
    except ClientError as e:
        print(f"❌ Bedrock connection failed: {str(e)}")
        print(f"   Make sure model '{model_id}' is enabled in Bedrock console")
        return False
    except Exception as e:
        print(f"❌ Bedrock connection failed: {str(e)}")
        return False


def test_embeddings():
    """Test embedding generation"""
    print("Testing embedding generation...")
    
    try:
        from src.services.embeddings import generate_text_embedding, generate_image_embedding_from_text
        
        # Test text embedding
        text_emb = generate_text_embedding("test query")
        print(f"✅ Text embeddings working!")
        print(f"   Dimension: {len(text_emb)}")
        
        # Test CLIP embedding
        clip_emb = generate_image_embedding_from_text("red car")
        print(f"✅ CLIP embeddings working!")
        print(f"   Dimension: {len(clip_emb)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Embedding generation failed: {str(e)}")
        return False




if __name__ == '__main__':
    print("=" * 80)
    print("Lambda Function Local Testing")
    print("=" * 80)
    print()
    
    # Check environment variables
    required_vars = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
    optional_vars = ['AWS_REGION', 'BEDROCK_MODEL_ID', 'DYNAMODB_TABLE_NAME', 'S3_BUCKET_NAME']
    
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"⚠️  Missing required environment variables: {', '.join(missing_vars)}")
        print("Please create a .env file based on .env.example")
        print()
    
    print("Environment variables:")
    for var in required_vars + optional_vars:
        value = os.environ.get(var)
        if value:
            # Mask sensitive values
            if 'PASSWORD' in var or 'SECRET' in var:
                display_value = '***'
            else:
                display_value = value[:50] + '...' if len(value) > 50 else value
            print(f"  ✓ {var}: {display_value}")
        else:
            print(f"  ✗ {var}: not set")
    print()
    
    # Run connectivity tests
    test_results = {}
    
    print("\n1. PostgreSQL Database Test")
    print("-" * 80)
    test_results['database'] = test_database_connection()
    
    print("\n2. DynamoDB Test")
    print("-" * 80)
    test_results['dynamodb'] = test_dynamodb_connection()
    
    print("\n3. S3 Test")
    print("-" * 80)
    test_results['s3'] = test_s3_connection()
    
    print("\n4. Bedrock Test")
    print("-" * 80)
    test_results['bedrock'] = test_bedrock_connection()
    
    print("\n5. Embedding Models Test")
    print("-" * 80)
    test_results['embeddings'] = test_embeddings()
    

    
    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name.upper()}: {status}")
    print("=" * 80)
