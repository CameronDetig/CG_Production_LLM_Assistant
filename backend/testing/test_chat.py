"""
Test script for the chatbot functionality.
Runs the lambda_handler locally with a sample chat event.
"""

import json
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
# Go up one level to find .env (from testing/ to backend/)
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(backend_dir, '.env')
load_dotenv(dotenv_path)

# Add backend directory to path
sys.path.insert(0, backend_dir)

from lambda_function import lambda_handler

def test_chat_query(query_text="Show me the most recent images from the spring show", user_id="test_user"):
    """Test chatbot query with custom text"""
    
    event = {
        'body': json.dumps({
            'query': query_text,
            'user_id': user_id
        })
    }
    
    context = {}  # Mock context
    
    print("=" * 80)
    print("Testing Chat Query")
    print("=" * 80)
    print(f"Query: {query_text}")
    print(f"User:  {user_id}")
    print("-" * 80)
    print("Response:")
    
    try:
        response = lambda_handler(event, context)
        
        if response['statusCode'] == 200:
            # Handle streaming response
            if callable(response.get('body')):
                for chunk in response['body']:
                    print(chunk, end='', flush=True)
            else:
                body = response['body']
                # Try to pretty print JSON if possible
                try:
                    if isinstance(body, str):
                        parsed = json.loads(body)
                        print(json.dumps(parsed, indent=2))
                    else:
                        print(body)
                except:
                    print(body)
        else:
            print(f"Error: {response['statusCode']}")
            print(response['body'])
            
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)


if __name__ == '__main__':
    # Default test
    if len(sys.argv) > 1:
        # Use command line argument as query if provided
        query = " ".join(sys.argv[1:])
        test_chat_query(query)
    else:
        test_chat_query()
