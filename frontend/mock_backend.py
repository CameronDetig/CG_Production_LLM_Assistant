"""
Mock backend server for local testing without deploying Lambda.
Simulates the Lambda API responses for development.
"""

from flask import Flask, request, Response, jsonify
import json
import time
import random

app = Flask(__name__)


def generate_mock_response(query: str):
    """Generate a mock AI response based on the query."""
    
    # Simulate finding files
    mock_files = [
        {
            "file_name": "scene_lighting_v3.blend",
            "file_type": "blend",
            "render_engine": "Cycles",
            "resolution_x": 3840,
            "resolution_y": 2160,
            "num_frames": 250,
            "similarity": 0.89
        },
        {
            "file_name": "character_rig_final.blend",
            "file_type": "blend",
            "render_engine": "Eevee",
            "resolution_x": 1920,
            "resolution_y": 1080,
            "total_objects": 156,
            "similarity": 0.76
        }
    ]
    
    # Build mock response
    response_parts = [
        f"I found {len(mock_files)} files matching your query:\n\n"
    ]
    
    for idx, file in enumerate(mock_files, 1):
        response_parts.append(
            f"{idx}. **{file['file_name']}** ({file['file_type']})\n"
            f"   - Render Engine: {file.get('render_engine', 'N/A')}\n"
            f"   - Resolution: {file.get('resolution_x', 'N/A')}x{file.get('resolution_y', 'N/A')}\n"
            f"   - Relevance: {file['similarity']:.0%}\n\n"
        )
    
    response_parts.append(
        "These files match your search criteria based on semantic similarity. "
        "Would you like more details about any specific file?"
    )
    
    return "".join(response_parts)


@app.route('/chat', methods=['POST', 'OPTIONS'])
def chat():
    """Mock chat endpoint that simulates Lambda response."""
    
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = Response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    # Get query from request
    data = request.get_json()
    query = data.get('query', '')
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    # Generate mock response
    full_response = generate_mock_response(query)
    
    # Stream response as SSE
    def generate():
        # Start event
        yield f"data: {json.dumps({'type': 'start', 'metadata_count': 2})}\n\n"
        time.sleep(0.1)
        
        # Stream response in chunks (simulate typing)
        words = full_response.split()
        for i, word in enumerate(words):
            chunk = word + (' ' if i < len(words) - 1 else '')
            yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
            time.sleep(random.uniform(0.02, 0.08))  # Simulate natural typing speed
        
        # End event
        yield f"data: {json.dumps({'type': 'end'})}\n\n"
    
    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    
    return response


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'message': 'Mock backend is running'})


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Mock Backend Server Starting")
    print("=" * 60)
    print("\nThis simulates the Lambda backend for local testing.")
    print("The Gradio frontend will connect to: http://localhost:8000/chat")
    print("\nTo use this:")
    print("1. Set API_ENDPOINT=http://localhost:8000/chat in .env")
    print("2. Run this server: python mock_backend.py")
    print("3. Run Gradio app: python app.py")
    print("\n" + "=" * 60 + "\n")
    
    app.run(host='0.0.0.0', port=8000, debug=True)
