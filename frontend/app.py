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

# DEBUG: Print Gradio version to logs
print(f"🚀 Running with Gradio version: {gr.__version__}")

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
conversation_title_to_id = {}  # Maps displayed title to conversation_id


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


def signup_via_backend(email: str, password: str) -> Tuple[Optional[str], str]:
    """
    Create a new user account via backend /signup endpoint.
    
    Returns:
        (id_token, message)
    """
    global current_token, current_user_id
    
    try:
        response = requests.post(
            f"{API_ENDPOINT}/signup",
            json={
                'email': email,
                'password': password
            },
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            # Auto-login after successful signup
            current_token = data.get('id_token')
            current_user_id = data.get('user_id', email)
            
            if current_token:
                return current_token, f"✅ Account created and logged in as {current_user_id}"
            else:
                return None, f"✅ Account created! Please log in with your credentials."
        elif response.status_code == 400:
            error_data = response.json()
            error_msg = error_data.get('error', 'Invalid request')
            return None, f"❌ {error_msg}"
        else:
            return None, f"❌ Signup error: {response.status_code}"
            
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


def load_conversations() -> List[str]:
    """
    Load user's conversations from backend.
    
    Returns:
        List of conversation titles for dropdown display
    """
    global conversation_title_to_id
    
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
            
            # Build mapping of title -> conversation_id
            # Handle duplicate titles by appending a suffix
            conversation_title_to_id = {}
            titles = []
            for c in conversations:
                title = c['title']
                conv_id = c['conversation_id']
                
                # Handle duplicate titles
                display_title = title
                counter = 1
                while display_title in conversation_title_to_id:
                    counter += 1
                    display_title = f"{title} ({counter})"
                
                conversation_title_to_id[display_title] = conv_id
                titles.append(display_title)
            
            return titles
        else:
            return []
            
    except Exception as e:
        print(f"Error loading conversations: {e}")
        return []


def select_conversation(title: str) -> List[Dict[str, str]]:
    """
    Load messages from a conversation by looking up its ID from the title.
    
    Args:
        title: The conversation title selected from dropdown
    
    Returns:
        Chat history in Gradio 6.0 format (list of message dicts)
    """
    global current_conversation_id
    
    if not current_token or not title:
        return []
    
    # Look up conversation_id from title
    conversation_id = conversation_title_to_id.get(title)
    if not conversation_id:
        print(f"No conversation found for title: {title}")
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


def new_conversation() -> Tuple[List[Dict[str, str]], str, Any]:
    """
    Start a new conversation.
    
    Returns:
        (empty_history, status_message, conversations_dropdown_update)
    """
    global current_conversation_id
    current_conversation_id = None
    conversations = load_conversations()
    return [], "Started new conversation", gr.update(choices=conversations, value=None)


def delete_conversation(conversation_id: str) -> Tuple[str, Any]:
    """Delete a conversation and refresh the list."""
    if not current_token or not conversation_id:
        return "No conversation selected", gr.update()
    
    try:
        response = requests.delete(
            f"{API_ENDPOINT}/conversations/{conversation_id}",
            headers={'Authorization': f'Bearer {current_token}'},
            timeout=10
        )
        
        if response.status_code == 200:
            conversations = load_conversations()
            return "Conversation deleted", gr.update(choices=conversations, value=None)
        else:
            return f"Error deleting conversation: {response.status_code}", gr.update()
            
    except Exception as e:
        return f"Error: {str(e)}", gr.update()


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
                        file_name = data.get('file_name', 'thumbnail')
                        thumbnail_url = data.get('thumbnail_url')
                        if thumbnail_url:
                            # Add thumbnail as inline markdown image
                            accumulated_text += f"\n\n![{file_name}]({thumbnail_url})"
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
) -> Generator[Tuple[List[Dict[str, str]], str, Optional[Image.Image], List[Tuple[str, str]]], None, None]:
    """
    Send message to backend and stream response.
    
    Args:
        message: User's message
        history: Chat history (Gradio 6.0 format)
        uploaded_image: Optional uploaded image for search
        
    Yields:
        (updated_history, cleared_input, cleared_image, conversations_list)
    """
    global current_conversation_id
    
    if not message.strip() and not uploaded_image:
        yield history, "", None, gr.update()
        return
    
    # Track if this is a new conversation
    was_new_conversation = current_conversation_id is None
    
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
    
    # Add user message to history with uploaded image if present
    message_content = message if message.strip() else "Find similar images to the uploaded image"
    if uploaded_image:
        # Convert image to base64 JPEG for inline display
        buffer = BytesIO()
        uploaded_image.convert('RGB').save(buffer, format='JPEG', quality=85)
        img_b64 = base64.b64encode(buffer.getvalue()).decode()
        message_content = f"{message_content}\n\n![Uploaded Image](data:image/jpeg;base64,{img_b64})"
    
    history.append({'role': 'user', 'content': message_content})
    yield history, "", None, gr.update()  # Clear inputs immediately
    
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
            yield history, "", None, gr.update()
            return
        
        # Stream response
        accumulated_response = ""
        
        # Add placeholder for assistant response
        history.append({'role': 'assistant', 'content': ''})
        
        for text, thumbs, conv_id in parse_sse_stream(response):
            accumulated_response = text
            
            # Update conversation ID if returned
            if conv_id and not current_conversation_id:
                current_conversation_id = conv_id
            
            # Update the last message (assistant response)
            history[-1] = {'role': 'assistant', 'content': accumulated_response}
            
            yield history, "", None, gr.update()
        
        # If this was a new conversation, refresh the dropdown
        if was_new_conversation and current_conversation_id:
            conversations = load_conversations()
            yield history, "", None, gr.update(choices=conversations)
        
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        if not any(msg.get('role') == 'user' and msg.get('content') == message for msg in history):
            history.append({'role': 'user', 'content': message})
        history.append({'role': 'assistant', 'content': error_msg})
        yield history, "", None, gr.update()


# Custom CSS to fix password input styling
custom_css = """
/* Fix password and text inputs showing white background before focus */
input[type="password"],
input[type="text"],
.gradio-container input {
    background-color: var(--input-background-fill) !important;
}

/* Ensure inputs inside accordions are styled correctly */
.accordion input {
    background-color: var(--input-background-fill) !important;
}
"""

# Build Gradio UI
with gr.Blocks(title="CG Production Assistant") as demo:
    gr.Markdown("# CG Production LLM Assistant")
    gr.Markdown("### Ask questions about assets from Blender Studio's short films")
    
    with gr.Row():
        # Left sidebar - Authentication & Conversations
        with gr.Column(scale=1):
            gr.Markdown("### 🔐 Authentication")
            
            # Collapsible authentication section
            with gr.Accordion("Login / Signup Options", open=False):
                with gr.Tabs():
                    with gr.Tab("Login"):
                        with gr.Group():
                            login_email_input = gr.Textbox(label="Email", placeholder="your-email@example.com")
                            login_password_input = gr.Textbox(label="Password", type="password")
                            login_btn = gr.Button("Login", variant="primary")
                    
                    with gr.Tab("Sign Up"):
                        with gr.Group():
                            signup_email_input = gr.Textbox(label="Email", placeholder="your-email@example.com")
                            signup_password_input = gr.Textbox(
                                label="Password", 
                                type="password",
                                placeholder="Min 8 chars, 1 uppercase, 1 lowercase, 1 number, 1 special char"
                            )
                            signup_confirm_password = gr.Textbox(label="Confirm Password", type="password")
                            signup_btn = gr.Button("Create Account", variant="primary")
                
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
                # Left: Image upload with clear button below
                with gr.Column(scale=1):
                    image_upload = gr.Image(
                        label="Upload Image for Visual Search",
                        type="pil",
                        height=150
                    )
                    clear_image_btn = gr.Button("Clear Image", size="sm")
                
                # Right: Message box with send button
                with gr.Column(scale=4):
                    msg_input = gr.Textbox(
                        label="Message",
                        placeholder="Ask questions about the database...",
                        lines=3
                    )
                    send_btn = gr.Button("Send", variant="primary")
    
    # Helper function for signup with password confirmation
    def signup_with_confirmation(email: str, password: str, confirm_password: str) -> Tuple[Optional[str], str]:
        if not email or not password:
            return None, "❌ Email and password are required"
        if password != confirm_password:
            return None, "❌ Passwords do not match"
        if len(password) < 8:
            return None, "❌ Password must be at least 8 characters"
        return signup_via_backend(email, password)
    
    # Event handlers
    login_btn.click(
        fn=authenticate_via_backend,
        inputs=[login_email_input, login_password_input],
        outputs=[gr.State(), auth_status]
    ).then(
        fn=load_conversations,
        outputs=conversations_list
    )
    
    signup_btn.click(
        fn=signup_with_confirmation,
        inputs=[signup_email_input, signup_password_input, signup_confirm_password],
        outputs=[gr.State(), auth_status]
    ).then(
        fn=load_conversations,
        outputs=conversations_list
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
        outputs=[chatbot, auth_status, conversations_list]
    )
    
    delete_conv_btn.click(
        fn=delete_conversation,
        inputs=conversations_list,
        outputs=[auth_status, conversations_list]
    )
    
    # Chat interaction
    msg_input.submit(
        fn=chat_with_backend,
        inputs=[msg_input, chatbot, image_upload],
        outputs=[chatbot, msg_input, image_upload, conversations_list]
    )
    
    send_btn.click(
        fn=chat_with_backend,
        inputs=[msg_input, chatbot, image_upload],
        outputs=[chatbot, msg_input, image_upload, conversations_list]
    )
    
    clear_image_btn.click(
        fn=lambda: None,
        outputs=image_upload
    )
    
    # Auto-login on startup and load conversations (with no selection)
    def load_conversations_no_selection():
        """Load conversations but don't auto-select any."""
        conversations = load_conversations()
        return gr.update(choices=conversations, value=None)
    
    demo.load(
        fn=demo_login,
        outputs=[gr.State(), auth_status]
    ).then(
        fn=load_conversations_no_selection,
        outputs=conversations_list
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        css=custom_css
    )
