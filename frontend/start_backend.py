"""
Startup script for local backend.
Ensures environment variables are loaded before importing Lambda modules.
"""

import os
from dotenv import load_dotenv

# Load environment variables FIRST, before any imports
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"✅ Loaded environment from {env_path}")
else:
    print(f"⚠️  No .env file found at {env_path}")
    print("Creating .env from .env.example...")
    
    example_path = os.path.join(os.path.dirname(__file__), '.env.example')
    if os.path.exists(example_path):
        import shutil
        shutil.copy(example_path, env_path)
        load_dotenv(env_path)
        print(f"✅ Created .env file. Please update it with your credentials.")
    else:
        print(f"❌ No .env.example found. Please create .env manually.")
        exit(1)

# Now import and run the backend
from local_backend import app, test_db_connection, test_bedrock_connection, test_semantic_search

if __name__ == '__main__':
    print("=" * 80)
    print("🚀 CG Production LLM Assistant - Local Backend")
    print("=" * 80)
    print()
    print("This local backend reuses the Lambda function code for consistency.")
    print("Easy transition to AWS: deploy the Lambda function with the same code!")
    print()
    
    # Check environment variables
    required_vars = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'AWS_REGION', 'BEDROCK_MODEL_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print(f"Please update the .env file at: {env_path}")
        print()
        exit(1)
    
    # Run connection tests
    print("Running connection tests...")
    print("-" * 80)
    
    db_ok = test_db_connection()
    bedrock_ok = test_bedrock_connection()
    search_ok = test_semantic_search()
    
    print("-" * 80)
    print()
    
    if not all([db_ok, bedrock_ok]):
        print("⚠️  Some connections failed. Server will start but may not work correctly.")
        print()
    
    print("Starting Flask server...")
    print(f"API endpoint: http://localhost:8000/chat")
    print(f"Health check: http://localhost:8000/health")
    print()
    print("To use with Gradio frontend:")
    print("1. Ensure API_ENDPOINT=http://localhost:8000/chat in frontend/.env")
    print("2. In another terminal, run: python app.py")
    print()
    print("=" * 80)
    print()
    
    # Start Flask server
    app.run(host='0.0.0.0', port=8000, debug=True)
