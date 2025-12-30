"""
Gradio frontend for CG Production LLM Assistant.
Features: Authentication, conversation management, image upload, thumbnail display.
"""

import gradio as gr
import requests
import os
import json
import base64
from typing import Generator, List, Tuple, Optional, Dict, Any
from PIL import Image
from io import BytesIO
import boto3
from botocore.exceptions import ClientError

# Configuration
API_ENDPOINT = os.getenv("API_ENDPOINT", "https://your-api-gateway-url.amazonaws.com/prod")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "your-client-id")
COGNITO_REGION = os.getenv("COGNITO_REGION", "us-east-1")

# Demo account credentials
DEMO_EMAIL = "demo@cgassistant.com"
DEMO_PASSWORD = "DemoPass10!"

# Global state
current_token = None
current_user_id = None
current_conversation_id = None

# Cognito client
cognito_client = boto3.client('cognito-idp', region_name=COGNITO_REGION)


def authenticate(email: str, password: str) -> Tuple[Optional[str], str]:
    """
    Authenticate user with Cognito.
    
    Returns:
        (id_token, message)
    """
    global current_token, current_user_id
    
    try:
        response = cognito_client.initiate_auth(
            ClientId=COGNITO_CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': email,
                'PASSWORD': password
            }
        )
        
        current_token = response['AuthenticationResult']['IdToken']
        current_user_id = email
        
        return current_token, f"✅ Logged in as {email}"
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NotAuthorizedException':
            return None, "❌ Invalid email or password"
        else:
            return None, f"❌ Authentication error: {error_code}"
    except Exception as e:
        return None, f"❌ Error: {str(e)}"


def demo_login() -> Tuple[Optional[str], str]:
    """Quick login with demo account."""
    return authenticate(DEMO_EMAIL, DEMO_PASSWORD)


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


def select_conversation(conversation_id: str) -> List[Tuple[str, str]]:
    """
    Load messages from a conversation.
    
    Returns:
        Chat history in Gradio format
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
            
            # Convert to Gradio chat format
            history = []
            for i in range(0, len(messages), 2):
                if i + 1 < len(messages):
                    user_msg = messages[i]['content']
                    assistant_msg = messages[i + 1]['content']
                    history.append((user_msg, assistant_msg))
            
            return history
        else:
            return []
            
    except Exception as e:
        print(f"Error loading conversation: {e}")
        return []


def new_conversation() -> Tuple[List, str]:
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


def parse_sse_stream(response) -> Generator[Tuple[str, List[str]], None, None]:
    """
    Parse Server-Sent Events stream from backend.
    
    Yields:
        (accumulated_text, thumbnail_urls)
    """
    accumulated_text = ""
    thumbnail_urls = []
    current_event = None
    
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            
            if line.startswith('event:'):
                current_event = line.split(':', 1)[1].strip()
            elif line.startswith('data:'):
                try:
                    data = json.loads(line.split(':', 1)[1].strip())
                    
                    if current_event == 'tool_call':
                        tool_name = data.get('tool', 'unknown')
                        accumulated_text += f"\n\n🔧 **Using tool:** {tool_name}\n"
                        yield accumulated_text, thumbnail_urls
                    
                    elif current_event == 'tool_result':
                        count = data.get('count', 0)
                        if count > 0:
                            accumulated_text += f"Found {count} results\n"
                            yield accumulated_text, thumbnail_urls
                    
                    elif current_event == 'thumbnail':
                        thumbnail_url = data.get('thumbnail_url')
                        if thumbnail_url:
                            thumbnail_urls.append(thumbnail_url)
                            yield accumulated_text, thumbnail_urls
                    
                    elif current_event == 'answer_start':
                        accumulated_text += "\n\n**Answer:**\n"
                        yield accumulated_text, thumbnail_urls
                    
                    elif current_event == 'answer_chunk':
                        text = data.get('text', '')
                        accumulated_text += text
                        yield accumulated_text, thumbnail_urls
                    
                    elif current_event == 'done':
                        break
                        
                except json.JSONDecodeError:
                    continue


def chat_with_backend(
    message: str,
    history: List[Tuple[str, str]],
    uploaded_image: Optional[Image.Image] = None
) -> Generator[Tuple[List[Tuple[str, str]], List[str]], None, None]:
    """
    Send message to backend and stream response.
    
    Args:
        message: User's message
        history: Chat history
        uploaded_image: Optional uploaded image for search
        
    Yields:
        (updated_history, thumbnail_urls)
    """
    global current_conversation_id
    
    if not message.strip() and not uploaded_image:
        yield history, []
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
            history.append((message, error_msg))
            yield history, []
            return
        
        # Stream response
        accumulated_response = ""
        thumbnail_urls = []
        
        for text, thumbs in parse_sse_stream(response):
            accumulated_response = text
            thumbnail_urls = thumbs
            
            # Update history with current response
            if history and history[-1][0] == message:
                history[-1] = (message, accumulated_response)
            else:
                history.append((message, accumulated_response))
            
            yield history, thumbnail_urls
        
        # Update conversation ID if new conversation
        # (Would be returned in 'done' event, but we'll handle it in next iteration)
        
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        history.append((message, error_msg))
        yield history, []


# Build Gradio UI
with gr.Blocks(title="CG Production Assistant", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🎬 CG Production LLM Assistant")
    gr.Markdown("AI-powered search for your CG production assets with conversation memory")
    
    with gr.Row():
        # Left sidebar - Authentication & Conversations
        with gr.Column(scale=1):
            gr.Markdown("### 🔐 Authentication")
            
            with gr.Group():
                email_input = gr.Textbox(label="Email", placeholder="demo@cgassistant.com")
                password_input = gr.Textbox(label="Password", type="password", placeholder="DemoPass10!")
                
                with gr.Row():
                    login_btn = gr.Button("Login", variant="primary")
                    demo_login_btn = gr.Button("🎭 Demo Login")
                
                logout_btn = gr.Button("Logout")
                auth_status = gr.Textbox(label="Status", interactive=False)
            
            gr.Markdown("### 💬 Conversations")
            
            new_conv_btn = gr.Button("➕ New Conversation", variant="primary")
            conversations_list = gr.Dropdown(
                label="Your Conversations",
                choices=[],
                interactive=True
            )
            refresh_convs_btn = gr.Button("🔄 Refresh")
            delete_conv_btn = gr.Button("🗑️ Delete Selected", variant="stop")
        
        # Main chat area
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(
                label="Chat",
                height=500,
                show_copy_button=True
            )
            
            with gr.Row():
                msg_input = gr.Textbox(
                    label="Message",
                    placeholder="Ask about your CG assets... (e.g., 'Show me 4K renders')",
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
        fn=authenticate,
        inputs=[email_input, password_input],
        outputs=[gr.State(), auth_status]
    )
    
    demo_login_btn.click(
        fn=demo_login,
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
        outputs=[chatbot, thumbnail_gallery]
    ).then(
        fn=lambda: ("", None),
        outputs=[msg_input, image_upload]
    )
    
    send_btn.click(
        fn=chat_with_backend,
        inputs=[msg_input, chatbot, image_upload],
        outputs=[chatbot, thumbnail_gallery]
    ).then(
        fn=lambda: ("", None),
        outputs=[msg_input, image_upload]
    )
    
    clear_image_btn.click(
        fn=lambda: None,
        outputs=image_upload
    )
    
    # Load conversations on startup
    demo.load(
        fn=load_conversations,
        outputs=conversations_list
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )
