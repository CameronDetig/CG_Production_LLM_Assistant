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

@app.route('/chat', methods=['POST'])
def chat():
    """Wraper for lambda_handler"""
    print("\n" + "="*50)
    print("📨 Received request from frontend")
    
    # Construct Lambda event from Flask request
    event = {
        'body': json.dumps(request.json),
        'httpMethod': 'POST',
        'path': '/chat',
        'headers': dict(request.headers),
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
        print("✅ Sending JSON response")
        return Response(
            response['body'],
            status=response['statusCode'],
            content_type='application/json'
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
