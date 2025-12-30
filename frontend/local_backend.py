"""
Local backend server for testing CG Production LLM Assistant.
This server reuses the Lambda function code to ensure consistency between local and AWS deployment.

Architecture:
- Flask server wraps the Lambda handler
- Reuses database.py, bedrock_client.py, and embeddings.py from backend
- Same SSE streaming as Lambda
- Easy transition to AWS: just deploy the Lambda function

Usage:
    python local_backend.py
"""

import os
import sys
import json
import logging
from flask import Flask, request, Response, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Skip automatic database initialization in lambda_function.py
# We'll initialize it manually after environment is loaded
os.environ['SKIP_DB_INIT'] = '1'

# Add backend directory to path to import Lambda modules
backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.insert(0, os.path.abspath(backend_path))

# Import Lambda function and dependencies
import lambda_function
from lambda_function import format_sse_event
from database import init_db_connection

# Now initialize database with loaded environment variables
init_db_connection()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)


@app.route('/chat', methods=['POST', 'OPTIONS'])
def chat():
    """
    Chat endpoint that wraps the Lambda handler.
    Converts Flask request to Lambda event format and streams response.
    """
    
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = Response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    try:
        # Get request data
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Convert Flask request to Lambda event format
        lambda_event = {
            'body': json.dumps(data),
            'headers': dict(request.headers),
            'httpMethod': 'POST',
            'path': '/chat'
        }
        
        # Mock Lambda context
        class MockContext:
            function_name = 'local-backend'
            memory_limit_in_mb = 512
            invoked_function_arn = 'local'
            aws_request_id = 'local-request'
        
        context = MockContext()
        
        logger.info(f"Processing query: {data.get('query', '')[:100]}")
        
        # Call Lambda handler
        lambda_response = lambda_function.lambda_handler(lambda_event, context)
        
        # Check if response is streaming (body is a generator)
        response_body = lambda_response.get('body')
        
        # Check if it's a generator (streaming response)
        import types
        if isinstance(response_body, types.GeneratorType):
            # Stream SSE response
            def generate():
                try:
                    for chunk in response_body:
                        yield chunk
                except Exception as e:
                    logger.error(f"Error during streaming: {str(e)}", exc_info=True)
                    yield format_sse_event({
                        'type': 'error',
                        'message': f'Streaming error: {str(e)}'
                    })
            
            response = Response(generate(), mimetype='text/event-stream')
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Cache-Control'] = 'no-cache'
            response.headers['Connection'] = 'keep-alive'
            return response
        else:
            # Non-streaming response (error case or string body)
            if isinstance(response_body, str):
                body_data = json.loads(response_body)
            else:
                body_data = response_body
            
            response = jsonify(body_data)
            response.status_code = lambda_response['statusCode']
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response
    
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    try:
        # Test database connection
        from database import get_connection, release_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        release_connection(conn)
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'backend': 'local',
            'bedrock_model': os.getenv('BEDROCK_MODEL_ID', 'not configured')
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


def test_db_connection():
    """Test database connection."""
    try:
        from database import get_connection, release_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Database connected: {version[0]}")
        cursor.close()
        release_connection(conn)
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        return False


def test_bedrock_connection():
    """Test Bedrock connection."""
    try:
        import boto3
        bedrock = boto3.client('bedrock-runtime', region_name=os.getenv('AWS_REGION', 'us-east-1'))
        
        # Simple test with correct inference profile ID
        model_id = os.getenv('BEDROCK_MODEL_ID', 'us.meta.llama3-2-11b-instruct-v1:0')
        test_prompt = "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\nHello!<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        
        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps({
                "prompt": test_prompt,
                "max_gen_len": 20,
                "temperature": 0.7
            })
        )
        
        print(f"✅ Bedrock connected: {model_id}")
        return True
    except Exception as e:
        print(f"❌ Bedrock connection failed: {str(e)}")
        return False


def test_semantic_search():
    """Test semantic search."""
    try:
        from database import get_relevant_metadata
        results = get_relevant_metadata("test query", limit=5)
        print(f"✅ Semantic search working: {len(results)} results")
        return True
    except Exception as e:
        print(f"❌ Semantic search failed: {str(e)}")
        return False


if __name__ == '__main__':
    print("=" * 80)
    print("CG Production LLM Assistant - Local Backend")
    print("=" * 80)
    print()
    print("This local backend reuses the Lambda function code for consistency.")
    print("Easy transition to AWS: deploy the Lambda function with the same code.")
    print()
    
    # Check environment variables
    required_vars = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'AWS_REGION', 'BEDROCK_MODEL_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("Please create a .env file in the frontend directory")
        print()
    
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
    print("1. Set API_ENDPOINT=http://localhost:8000/chat in frontend/.env")
    print("2. Run: python app.py")
    print()
    print("=" * 80)
    print()
    
    # Start Flask server
    app.run(host='0.0.0.0', port=8000, debug=True)
