"""
Local testing script for Lambda function.
Run this to test the function locally before deploying to AWS.
"""

import json
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

from lambda_function import lambda_handler


def test_basic_query():
    """Test basic chatbot query"""
    event = {
        'body': json.dumps({
            'query': 'Show me all 4K renders from the lighting project',
            'user_id': 'test_user'
        })
    }
    
    context = {}  # Mock context
    
    print("Testing basic query...")
    print(f"Query: {json.loads(event['body'])['query']}")
    print("\nResponse:")
    print("-" * 80)
    
    try:
        response = lambda_handler(event, context)
        
        if response['statusCode'] == 200:
            # Handle streaming response
            if callable(response['body']):
                for chunk in response['body']:
                    print(chunk, end='', flush=True)
            else:
                print(response['body'])
        else:
            print(f"Error: {response['statusCode']}")
            print(response['body'])
            
    except Exception as e:
        print(f"Error during test: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "-" * 80)


def test_database_connection():
    """Test database connectivity"""
    from database import get_connection, release_connection
    
    print("Testing database connection...")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Database connected successfully!")
        print(f"PostgreSQL version: {version[0]}")
        cursor.close()
        release_connection(conn)
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")


def test_bedrock_connection():
    """Test Bedrock API connectivity"""
    import boto3
    
    print("Testing Bedrock connection...")
    
    try:
        bedrock = boto3.client('bedrock-runtime', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
        
        # Simple test prompt
        test_prompt = "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\nHello!<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        
        response = bedrock.invoke_model(
            modelId=os.environ.get('BEDROCK_MODEL_ID', 'meta.llama3-2-11b-instruct-v1:0'),
            body=json.dumps({
                "prompt": test_prompt,
                "max_gen_len": 50,
                "temperature": 0.7
            })
        )
        
        print("✅ Bedrock connected successfully!")
        print(f"Model: {os.environ.get('BEDROCK_MODEL_ID')}")
        
    except Exception as e:
        print(f"❌ Bedrock connection failed: {str(e)}")


if __name__ == '__main__':
    print("=" * 80)
    print("Lambda Function Local Testing")
    print("=" * 80)
    print()
    
    # Check environment variables
    required_vars = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'AWS_REGION']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("Please create a .env file based on .env.example")
        print()
    
    # Run tests
    print("\n1. Database Connection Test")
    print("-" * 80)
    test_database_connection()
    
    print("\n2. Bedrock Connection Test")
    print("-" * 80)
    test_bedrock_connection()
    
    print("\n3. Full Lambda Function Test")
    print("-" * 80)
    test_basic_query()
    
    print("\n" + "=" * 80)
    print("Testing complete!")
    print("=" * 80)
