"""
Local Flask server to wrap the Lambda function for frontend integration testing.
Exposes the lambda_handler at http://localhost:5000/chat
"""

import json
import os
import sys
from flask import Flask, request, Response, stream_with_context
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(backend_dir, '.env'))

# Add backend directory to path
sys.path.insert(0, backend_dir)

from lambda_function import lambda_handler

app = Flask(__name__)
CORS(app)  # Enable CORS for local testing

@app.route('/chat', methods=['POST', 'OPTIONS'])
@app.route('/auth', methods=['POST', 'OPTIONS'])
@app.route('/conversations', methods=['GET', 'OPTIONS'])
@app.route('/conversations/<conversation_id>', methods=['GET', 'DELETE', 'OPTIONS'])
def handle_request(conversation_id=None):
    """Handle all Lambda function routes"""
    
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return Response('', status=200)
    
    print("\n" + "="*50)
    print(f"📨 Received {request.method} request to {request.path}")
    
    # Construct Lambda event from Flask request
    event = {
        'body': json.dumps(request.json) if request.json else None,
        'httpMethod': request.method,
        'path': request.path,
        'headers': dict(request.headers),
        'pathParameters': {'id': conversation_id} if conversation_id else None,
        'requestContext': {
            'identity': {
                'sourceIp': request.remote_addr
            }
        }
    }
    
    context = {}  # Mock context
    
    try:
        # Call Lambda handler
        response = lambda_handler(event, context)
        
        # Handle streaming response
        if response['statusCode'] == 200 and callable(response.get('body')):
            print("🌊 Streaming response...")
            return Response(
                stream_with_context(response['body']),
                content_type='text/event-stream'
            )
            
        # Handle standard JSON response
        print(f"✅ Sending {response['statusCode']} response")
        return Response(
            response['body'],
            status=response['statusCode'],
            content_type='application/json',
            headers=response.get('headers', {})
        )
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return Response(
            json.dumps({'error': str(e)}),
            status=500,
            content_type='application/json'
        )

if __name__ == '__main__':
    print(f"🚀 Starting local Lambda server on http://localhost:5000")
    print(f"📂 Backend: {backend_dir}")
    app.run(host='0.0.0.0', port=5000, debug=True)
