"""
Gradio frontend for CG Production LLM Assistant.
Optimized for Hugging Face Spaces deployment with auto-login to demo account.
Features: Backend authentication, conversation management, image upload, thumbnail display.
"""

import gradio as gr
import requests
import os
import json
import base64
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
from typing import Generator, List, Tuple, Optional, Dict, Any
from PIL import Image
from io import BytesIO

# Configuration - Use environment variables or HF Spaces secrets
API_ENDPOINT = os.getenv("API_ENDPOINT", "https://your-api-gateway-url.amazonaws.com/prod")
DEMO_EMAIL = os.getenv("DEMO_EMAIL", "demo@cgassistant.com")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "DemoPass10!")

print(f"Accessing API_ENDPOINT: {API_ENDPOINT}\n")

# Global state
current_token = None
current_user_id = None
current_conversation_id = None


def authenticate_via_backend(email: str, password: str) -> Tuple[Optional[str], str]:
    """
    Authenticate user via backend /auth endpoint.
    
    Returns:
        (id_token, message)
    """
    global current_token, current_user_id
    
    try:
        response = requests.post(
            f"{API_ENDPOINT}/auth",
            json={
                'email': email,
                'password': password
            },
            timeout=120  # Increased to handle Lambda cold starts
        )
        
        if response.status_code == 200:
            data = response.json()
            current_token = data['id_token']
            current_user_id = data.get('user_id', email)
            
            return current_token, f"✅ Logged in as {current_user_id}"
        elif response.status_code == 401:
            return None, "❌ Invalid email or password"
        else:
            return None, f"❌ Authentication error: {response.status_code}"
            
    except Exception as e:
        return None, f"❌ Error: {str(e)}"


def demo_login() -> Tuple[Optional[str], str]:
    """Quick login with demo account."""
    # For local testing, skip actual authentication
    global current_token, current_user_id
    
    if 'localhost' in API_ENDPOINT or '127.0.0.1' in API_ENDPOINT:
        # Local testing mode - skip Cognito auth
        current_token = 'local-test-token'
        current_user_id = DEMO_EMAIL
        return current_token, f"✅ Logged in as {current_user_id} (local mode)"
    
    # Production mode - use real Cognito auth
    token, message = authenticate_via_backend(DEMO_EMAIL, DEMO_PASSWORD)
    return token, message


def logout() -> str:
    """Logout current user."""
    global current_token, current_user_id, current_conversation_id
    
    current_token = None
    current_user_id = None
    current_conversation_id = None
    
    return "Logged out successfully"


def load_conversations() -> List[Tuple[str, str]]:
    """
    Load user's conversations from backend.
    
    Returns:
        List of (conversation_id, title) tuples
    """
    if not current_token:
        return []
    
    try:
        response = requests.get(
            f"{API_ENDPOINT}/conversations",
            headers={'Authorization': f'Bearer {current_token}'},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            conversations = data.get('conversations', [])
            return [(c['conversation_id'], c['title']) for c in conversations]
        else:
            return []
            
    except Exception as e:
        print(f"Error loading conversations: {e}")
        return []


def select_conversation(conversation_id: str) -> List[Dict[str, str]]:
    """
    Load messages from a conversation.
    
    Returns:
        Chat history in Gradio 6.0 format (list of message dicts)
    """
    global current_conversation_id
    
    if not current_token or not conversation_id:
        return []
    
    current_conversation_id = conversation_id
    
    try:
        response = requests.get(
            f"{API_ENDPOINT}/conversations/{conversation_id}",
            headers={'Authorization': f'Bearer {current_token}'},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            conversation = data.get('conversation', {})
            messages = conversation.get('messages', [])
            
            # Convert to Gradio 6.0 chat format (list of dicts with role and content)
            history = []
            for msg in messages:
                history.append({
                    'role': msg['role'],
                    'content': msg['content']
                })
            
            return history
        else:
            return []
            
    except Exception as e:
        print(f"Error loading conversation: {e}")
        return []


def new_conversation() -> Tuple[List[Dict[str, str]], str]:
    """
    Start a new conversation.
    
    Returns:
        (empty_history, status_message)
    """
    global current_conversation_id
    current_conversation_id = None
    return [], "Started new conversation"


def delete_conversation(conversation_id: str) -> str:
    """Delete a conversation."""
    if not current_token or not conversation_id:
        return "No conversation selected"
    
    try:
        response = requests.delete(
            f"{API_ENDPOINT}/conversations/{conversation_id}",
            headers={'Authorization': f'Bearer {current_token}'},
            timeout=10
        )
        
        if response.status_code == 200:
            return "Conversation deleted"
        else:
            return f"Error deleting conversation: {response.status_code}"
            
    except Exception as e:
        return f"Error: {str(e)}"


def resize_image_to_base64(image: Image.Image) -> str:
    """
    Resize image to 512x512 and convert to base64.
    
    Args:
        image: PIL Image
        
    Returns:
        Base64-encoded JPEG string
    """
    # Resize to 512x512
    image = image.resize((512, 512), Image.Resampling.LANCZOS)
    
    # Convert to JPEG bytes
    buffer = BytesIO()
    image.convert('RGB').save(buffer, format='JPEG', quality=85)
    image_bytes = buffer.getvalue()
    
    # Encode to base64
    return base64.b64encode(image_bytes).decode('utf-8')


def parse_sse_stream(response) -> Generator[Tuple[str, List[str], Optional[str]], None, None]:
    """
    Parse Server-Sent Events stream from backend.
    
    Yields:
        (accumulated_text, thumbnail_urls, conversation_id)
    """
    accumulated_text = ""
    thumbnail_urls = []
    conversation_id = None
    current_event = None
    
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            
            if line.startswith('event:'):
                current_event = line.split(':', 1)[1].strip()
            elif line.startswith('data:'):
                try:
                    data = json.loads(line.split(':', 1)[1].strip())
                    
                    # Handle enhanced query display
                    if current_event == 'enhanced_query':
                        enhanced = data.get('query', '')
                        accumulated_text += f"\n💭 **Enhanced Query:** {enhanced}\n"
                        yield accumulated_text, thumbnail_urls, conversation_id
                    
                    # Handle SQL query display
                    elif current_event == 'sql_query':
                        sql = data.get('query', '')
                        attempt = data.get('attempt', 1)
                        if attempt > 1:
                            accumulated_text += f"\n\n🔄 **SQL Query (Attempt {attempt}):**\n```sql\n{sql}\n```\n"
                        else:
                            accumulated_text += f"\n\n🔍 **SQL Query:**\n```sql\n{sql}\n```\n"
                        yield accumulated_text, thumbnail_urls, conversation_id
                    
                    # Handle query results
                    elif current_event == 'query_results':
                        count = data.get('count', 0)
                        attempt = data.get('attempt', 1)
                        results = data.get('results', [])
                        
                        if attempt > 1:
                            accumulated_text += f"\n📊 Attempt {attempt}: Found {count} results\n"
                        else:
                            accumulated_text += f"\n📊 Found {count} results\n"
                        
                        # Generate markdown table for results
                        if results and len(results) > 0:
                            # Get column names (exclude internal fields)
                            exclude_cols = {'thumbnail_url', 'thumbnail_path'}
                            cols = [k for k in results[0].keys() if k not in exclude_cols]
                            
                            # Create table
                            accumulated_text += "\n**Results:**\n\n"
                            accumulated_text += "| " + " | ".join(cols) + " |\n"
                            accumulated_text += "| " + " | ".join(["---"] * len(cols)) + " |\n"
                            
                            for row in results:
                                row_values = []
                                for col in cols:
                                    val = row.get(col, '')
                                    if val is None:
                                        val = ''
                                    row_values.append(str(val).replace('|', '\\|'))
                                accumulated_text += "| " + " | ".join(row_values) + " |\n"
                            
                            accumulated_text += "\n"
                        
                        yield accumulated_text, thumbnail_urls, conversation_id
                    
                    # Handle retry feedback
                    elif current_event == 'retry_feedback':
                        feedback = data.get('feedback', '')
                        attempt = data.get('attempt', 1)
                        accumulated_text += f"\n⚠️ **Retry Needed:** {feedback}\n"
                        yield accumulated_text, thumbnail_urls, conversation_id
                    
                    elif current_event == 'thumbnail':
                        thumbnail_url = data.get('thumbnail_url')
                        if thumbnail_url:
                            thumbnail_urls.append(thumbnail_url)
                            yield accumulated_text, thumbnail_urls, conversation_id
                    
                    elif current_event == 'answer_start':
                        accumulated_text += "\n\n**Answer:**\n"
                        yield accumulated_text, thumbnail_urls, conversation_id
                    
                    elif current_event == 'answer_chunk':
                        text = data.get('text', '')
                        accumulated_text += text
                        yield accumulated_text, thumbnail_urls, conversation_id
                    
                    elif current_event == 'done':
                        # Capture conversation ID from done event
                        conversation_id = data.get('conversation_id')
                        yield accumulated_text, thumbnail_urls, conversation_id
                        break
                        
                except json.JSONDecodeError:
                    continue


def chat_with_backend(
    message: str,
    history: List[Dict[str, str]],
    uploaded_image: Optional[Image.Image] = None
) -> Generator[Tuple[List[Dict[str, str]], List[str], str, Optional[Image.Image]], None, None]:
    """
    Send message to backend and stream response.
    
    Args:
        message: User's message
        history: Chat history (Gradio 6.0 format)
        uploaded_image: Optional uploaded image for search
        
    Yields:
        (updated_history, thumbnail_urls, cleared_input, cleared_image)
    """
    global current_conversation_id
    
    if not message.strip() and not uploaded_image:
        yield history, [], "", None
        return
    
    # Prepare payload
    payload = {
        "query": message if message.strip() else "Find similar images to the uploaded image"
    }
    
    if current_conversation_id:
        payload["conversation_id"] = current_conversation_id
    
    # Process uploaded image
    if uploaded_image:
        image_base64 = resize_image_to_base64(uploaded_image)
        payload["uploaded_image_base64"] = image_base64
    
    # Prepare headers
    headers = {'Content-Type': 'application/json'}
    if current_token:
        headers['Authorization'] = f'Bearer {current_token}'
    
    # Add user message to history immediately and yield to show it
    history.append({'role': 'user', 'content': message})
    yield history, [], "", None  # Clear inputs immediately
    
    try:
        # Send request
        response = requests.post(
            f"{API_ENDPOINT}/chat",
            json=payload,
            headers=headers,
            stream=True,
            timeout=120
        )
        
        if response.status_code != 200:
            error_msg = f"❌ Error: API returned status {response.status_code}"
            history.append({'role': 'assistant', 'content': error_msg})
            yield history, [], "", None
            return
        
        # Stream response
        accumulated_response = ""
        thumbnail_urls = []
        
        # Add placeholder for assistant response
        history.append({'role': 'assistant', 'content': ''})
        
        for text, thumbs, conv_id in parse_sse_stream(response):
            accumulated_response = text
            thumbnail_urls = thumbs
            
            # Update conversation ID if returned
            if conv_id and not current_conversation_id:
                current_conversation_id = conv_id
            
            # Update the last message (assistant response)
            history[-1] = {'role': 'assistant', 'content': accumulated_response}
            
            yield history, thumbnail_urls, "", None
        
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        if not any(msg.get('role') == 'user' and msg.get('content') == message for msg in history):
            history.append({'role': 'user', 'content': message})
        history.append({'role': 'assistant', 'content': error_msg})
        yield history, [], "", None


# Build Gradio UI
with gr.Blocks(title="CG Production Assistant") as demo:
    gr.Markdown("# CG Production LLM Assistant")
    gr.Markdown("### Ask questions about assets from Blender Studio's short films")
    
    with gr.Row():
        # Left sidebar - Authentication & Conversations
        with gr.Column(scale=1):
            gr.Markdown("### 🔐 Authentication")
            
            # Collapsible authentication section
            with gr.Accordion("Login Options", open=False):
                with gr.Group():
                    email_input = gr.Textbox(label="Email", placeholder="your-email@example.com")
                    password_input = gr.Textbox(label="Password", type="password")
                    
                    with gr.Row():
                        login_btn = gr.Button("Login", variant="primary")
                    
                    logout_btn = gr.Button("Logout")
            
            auth_status = gr.Textbox(
                label="Authorization Status", 
                interactive=False,
                value="✅ Logged in as demo@cgassistant.com (auto-login)"
            )
            
            gr.Markdown("### 💬 Conversations")
            
            new_conv_btn = gr.Button("➕ New Conversation", variant="primary")
            conversations_list = gr.Dropdown(
                label="Your Conversations",
                choices=[],
                value=None,
                allow_custom_value=True,
                interactive=True
            )
            refresh_convs_btn = gr.Button("🔄 Refresh")
            delete_conv_btn = gr.Button("🗑️ Delete Selected", variant="stop")
        
        # Main chat area
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(
                label="Chat",
                height=500
            )
            
            with gr.Row():
                msg_input = gr.Textbox(
                    label="Message",
                    placeholder="Ask questions about the database...",
                    scale=4
                )
                send_btn = gr.Button("Send", variant="primary", scale=1)
            
            with gr.Row():
                image_upload = gr.Image(
                    label="Upload Image for Visual Search (optional)",
                    type="pil",
                    height=200
                )
                clear_image_btn = gr.Button("Clear Image")
            
            gr.Markdown("### 🖼️ Thumbnails")
            thumbnail_gallery = gr.Gallery(
                label="Results",
                show_label=False,
                columns=5,
                height=300
            )
    
    # Event handlers
    login_btn.click(
        fn=authenticate_via_backend,
        inputs=[email_input, password_input],
        outputs=[gr.State(), auth_status]
    )
    
    logout_btn.click(
        fn=logout,
        outputs=auth_status
    )
    
    refresh_convs_btn.click(
        fn=load_conversations,
        outputs=conversations_list
    )
    
    conversations_list.change(
        fn=select_conversation,
        inputs=conversations_list,
        outputs=chatbot
    )
    
    new_conv_btn.click(
        fn=new_conversation,
        outputs=[chatbot, auth_status]
    )
    
    delete_conv_btn.click(
        fn=delete_conversation,
        inputs=conversations_list,
        outputs=auth_status
    )
    
    # Chat interaction
    msg_input.submit(
        fn=chat_with_backend,
        inputs=[msg_input, chatbot, image_upload],
        outputs=[chatbot, thumbnail_gallery, msg_input, image_upload]
    )
    
    send_btn.click(
        fn=chat_with_backend,
        inputs=[msg_input, chatbot, image_upload],
        outputs=[chatbot, thumbnail_gallery, msg_input, image_upload]
    )
    
    clear_image_btn.click(
        fn=lambda: None,
        outputs=image_upload
    )
    
    # Auto-login on startup and load conversations
    demo.load(
        fn=demo_login,
        outputs=[gr.State(), auth_status]
    ).then(
        fn=load_conversations,
        outputs=conversations_list
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        theme=gr.themes.Ocean()
    )
