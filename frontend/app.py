"""
Gradio frontend for CG Production LLM Assistant.
Provides a chat interface to interact with the Lambda backend.
"""

import gradio as gr
import requests
import os
import json
from typing import Generator, List, Tuple
import time

# Configuration
API_ENDPOINT = os.getenv("API_ENDPOINT", "http://localhost:8000/chat")
USE_STREAMING = os.getenv("USE_STREAMING", "true").lower() == "true"


def parse_sse_stream(response) -> Generator[str, None, None]:
    """
    Parse Server-Sent Events stream from Lambda backend.
    
    Yields:
        Text chunks from the AI response
    """
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])  # Remove 'data: ' prefix
                    
                    if data.get('type') == 'chunk':
                        yield data.get('text', '')
                    elif data.get('type') == 'error':
                        yield f"\n\n❌ Error: {data.get('message', 'Unknown error')}"
                        break
                    elif data.get('type') == 'end':
                        break
                        
                except json.JSONDecodeError:
                    continue


def chat_with_backend(message: str, history: List[Tuple[str, str]]) -> Generator[str, None, None]:
    """
    Send message to Lambda backend and stream response.
    
    Args:
        message: User's message
        history: Chat history (not used currently, but available for context)
        
    Yields:
        Accumulated response text
    """
    if not message.strip():
        yield "Please enter a question about your CG assets."
        return
    
    try:
        # Prepare request
        payload = {
            "query": message,
            "user_id": "gradio_user"
        }
        
        # Send request to Lambda backend
        response = requests.post(
            API_ENDPOINT,
            json=payload,
            stream=USE_STREAMING,
            timeout=60
        )
        
        if response.status_code != 200:
            yield f"❌ Error: API returned status {response.status_code}\n\n{response.text}"
            return
        
        # Stream response
        full_response = ""
        if USE_STREAMING:
            for chunk in parse_sse_stream(response):
                full_response += chunk
                yield full_response
                time.sleep(0.01)  # Small delay for smooth streaming
        else:
            # Non-streaming fallback
            result = response.json()
            yield result.get('response', 'No response from backend')
            
    except requests.exceptions.Timeout:
        yield "❌ Request timed out. The backend may be processing a large query."
    except requests.exceptions.ConnectionError:
        yield f"❌ Could not connect to backend at {API_ENDPOINT}\n\nMake sure the Lambda API is deployed or run local backend for testing."
    except Exception as e:
        yield f"❌ Unexpected error: {str(e)}"


def create_demo():
    """Create and configure the Gradio interface."""
    
    # Create interface
    with gr.Blocks(title="CG Production Assistant") as demo:
        
        gr.Markdown(
            """
            # 🎨 CG Production LLM Assistant
            
            Ask questions about your Blender files, renders, and production assets.
            The assistant uses semantic search to find relevant files and provides intelligent answers.
            
            **Example queries:**
            - "Show me all Cycles renders from this week"
            - "Find 4K resolution Blender files"
            - "What files use the Eevee render engine?"
            - "Show me files with dark moody lighting"
            """
        )
        
        # Chat interface
        chatbot = gr.ChatInterface(
            fn=chat_with_backend,
            examples=[
                "Show me all Blender files with Cycles renders",
                "Find 4K resolution files",
                "What files were modified this week?",
                "Show me files with dark moody lighting",
                "List all video files with their durations"
            ],
        )
        
        # Footer with connection status
        with gr.Row():
            gr.Markdown(
                f"""
                ---
                **Backend:** `{API_ENDPOINT}` | **Streaming:** {'✅ Enabled' if USE_STREAMING else '❌ Disabled'}
                
                💡 **Tip:** The first query may take 10-15 seconds as the Lambda function loads embedding models.
                """
            )
    
    return demo


if __name__ == "__main__":
    # Custom CSS for better styling
    custom_css = """
    .gradio-container {
        max-width: 900px !important;
    }
    .message-wrap {
        font-size: 16px !important;
    }
    """
    
    demo = create_demo()
    
    # Launch configuration (theme and css moved here for Gradio 6.0)
    demo.launch(
        server_name="0.0.0.0",  # Allow external connections
        server_port=7860,
        share=False,  # Set to True to create public link
        show_error=True
    )
