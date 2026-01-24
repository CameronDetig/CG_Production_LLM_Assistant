"""
HTTP API client for CG Production Assistant addon.
Handles authentication, chat, and conversation management.
Uses threading for non-blocking requests.
"""

import json
import urllib.request
import urllib.error
import ssl
import threading
import queue
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass


@dataclass
class APIResponse:
    """Response from an API call."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    status_code: int = 0


class APIClient:
    """HTTP client for backend communication."""
    
    def __init__(self, base_url: str, token: str = ""):
        """
        Initialize API client.
        
        Args:
            base_url: Backend API base URL
            token: Authentication token
        """
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.timeout = 120  # Increased for Lambda cold starts
        
        # Create SSL context that doesn't verify certificates (for development)
        self._ssl_context = ssl.create_default_context()
    
    def set_token(self, token: str):
        """Set the authentication token."""
        self.token = token
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> APIResponse:
        """
        Make a synchronous HTTP request.
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint
            data: Request body data
            headers: Additional headers
            
        Returns:
            APIResponse with result
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Build headers
        req_headers = {
            'Content-Type': 'application/json',
        }
        if self.token:
            req_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            req_headers.update(headers)
        
        # Build request
        body = json.dumps(data).encode('utf-8') if data else None
        req = urllib.request.Request(
            url,
            data=body,
            headers=req_headers,
            method=method
        )
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._ssl_context) as response:
                response_data = response.read().decode('utf-8')
                return APIResponse(
                    success=True,
                    data=json.loads(response_data) if response_data else {},
                    status_code=response.status
                )
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ""
            try:
                error_data = json.loads(error_body)
                error_msg = error_data.get('error', str(e))
            except json.JSONDecodeError:
                error_msg = error_body or str(e)
            return APIResponse(
                success=False,
                error=error_msg,
                status_code=e.code
            )
        except urllib.error.URLError as e:
            return APIResponse(
                success=False,
                error=f"Connection error: {str(e.reason)}",
                status_code=0
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                status_code=0
            )
    
    def authenticate(self, email: str, password: str) -> APIResponse:
        """
        Authenticate user with backend.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            APIResponse with token on success
        """
        return self._make_request(
            'POST',
            '/auth',
            data={'email': email, 'password': password}
        )
    
    def signup(self, email: str, password: str) -> APIResponse:
        """
        Create new user account.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            APIResponse with result
        """
        return self._make_request(
            'POST',
            '/signup',
            data={'email': email, 'password': password}
        )
    
    def get_conversations(self) -> APIResponse:
        """
        Get user's conversations.
        
        Returns:
            APIResponse with conversations list
        """
        return self._make_request('GET', '/conversations')
    
    def get_conversation(self, conversation_id: str) -> APIResponse:
        """
        Get a specific conversation with messages.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            APIResponse with conversation data
        """
        return self._make_request('GET', f'/conversations/{conversation_id}')
    
    def delete_conversation(self, conversation_id: str) -> APIResponse:
        """
        Delete a conversation.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            APIResponse with result
        """
        return self._make_request('DELETE', f'/conversations/{conversation_id}')
    
    def chat_stream(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        image_base64: Optional[str] = None,
        on_chunk: Optional[Callable[[str], None]] = None
    ) -> APIResponse:
        """
        Send a chat message and stream the response.
        
        Args:
            query: User's query
            conversation_id: Optional conversation ID
            image_base64: Optional base64-encoded image
            on_chunk: Callback for each response chunk
            
        Returns:
            APIResponse with final result
        """
        url = f"{self.base_url}/chat"
        
        # Build payload
        payload = {'query': query}
        if conversation_id:
            payload['conversation_id'] = conversation_id
        if image_base64:
            payload['uploaded_image_base64'] = image_base64
        
        # Build headers
        headers = {
            'Content-Type': 'application/json',
        }
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        # Build request
        body = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method='POST'
        )
        
        accumulated_text = ""
        events = []
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._ssl_context) as response:
                current_event = None
                
                # Read line by line for SSE
                for line in response:
                    line = line.decode('utf-8').strip()
                    if not line:
                        continue
                    
                    if line.startswith('event:'):
                        current_event = line.split(':', 1)[1].strip()
                    elif line.startswith('data:'):
                        try:
                            data = json.loads(line.split(':', 1)[1].strip())
                            events.append({'event': current_event, 'data': data})
                            
                            # Process event for text accumulation
                            if current_event == 'enhanced_query':
                                chunk = f"\n[Enhanced Query]: {data.get('query', '')}\n"
                                accumulated_text += chunk
                                if on_chunk:
                                    on_chunk(chunk)
                            
                            elif current_event == 'sql_query':
                                sql = data.get('query', '')
                                attempt = data.get('attempt', 1)
                                if attempt > 1:
                                    chunk = f"\n[SQL Query (Attempt {attempt})]:\n{sql}\n"
                                else:
                                    chunk = f"\n[SQL Query]:\n{sql}\n"
                                accumulated_text += chunk
                                if on_chunk:
                                    on_chunk(chunk)
                            
                            elif current_event == 'query_results':
                                count = data.get('count', 0)
                                chunk = f"\nFound {count} results\n"
                                accumulated_text += chunk
                                if on_chunk:
                                    on_chunk(chunk)
                            
                            elif current_event == 'answer_start':
                                chunk = "\n--- Answer ---\n"
                                accumulated_text += chunk
                                if on_chunk:
                                    on_chunk(chunk)
                            
                            elif current_event == 'answer_chunk':
                                chunk = data.get('text', '')
                                accumulated_text += chunk
                                if on_chunk:
                                    on_chunk(chunk)
                            
                            elif current_event == 'done':
                                # Final event
                                pass
                            
                        except json.JSONDecodeError:
                            continue
                
                return APIResponse(
                    success=True,
                    data={
                        'text': accumulated_text,
                        'events': events
                    },
                    status_code=200
                )
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ""
            return APIResponse(
                success=False,
                error=f"HTTP Error {e.code}: {error_body}",
                status_code=e.code
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                status_code=0
            )


class AsyncAPIClient:
    """
    Async wrapper for API client using threading.
    Provides non-blocking API calls for Blender operators.
    """
    
    def __init__(self, base_url: str, token: str = ""):
        """
        Initialize async API client.
        
        Args:
            base_url: Backend API base URL
            token: Authentication token
        """
        self.client = APIClient(base_url, token)
        self.response_queue = queue.Queue()
        self._current_thread = None
    
    def set_token(self, token: str):
        """Set the authentication token."""
        self.client.set_token(token)
    
    def _run_in_thread(self, func: Callable, *args, **kwargs):
        """Run a function in a background thread."""
        def wrapper():
            try:
                result = func(*args, **kwargs)
                self.response_queue.put(('success', result))
            except Exception as e:
                self.response_queue.put(('error', str(e)))
        
        self._current_thread = threading.Thread(target=wrapper, daemon=True)
        self._current_thread.start()
    
    def is_busy(self) -> bool:
        """Check if a request is in progress."""
        return self._current_thread is not None and self._current_thread.is_alive()
    
    def get_response(self) -> Optional[tuple]:
        """
        Get response from queue (non-blocking).
        
        Returns:
            Tuple of (status, result) or None if no response
        """
        try:
            return self.response_queue.get_nowait()
        except queue.Empty:
            return None
    
    def authenticate_async(self, email: str, password: str):
        """Start async authentication."""
        self._run_in_thread(self.client.authenticate, email, password)
    
    def get_conversations_async(self):
        """Start async get conversations."""
        self._run_in_thread(self.client.get_conversations)
    
    def get_conversation_async(self, conversation_id: str):
        """Start async get conversation."""
        self._run_in_thread(self.client.get_conversation, conversation_id)
    
    def delete_conversation_async(self, conversation_id: str):
        """Start async delete conversation."""
        self._run_in_thread(self.client.delete_conversation, conversation_id)
    
    def chat_stream_async(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        image_base64: Optional[str] = None,
        on_chunk: Optional[Callable[[str], None]] = None
    ):
        """Start async chat with streaming."""
        self._run_in_thread(
            self.client.chat_stream,
            query,
            conversation_id,
            image_base64,
            on_chunk
        )


# Global client instance (initialized when addon loads)
_global_client: Optional[AsyncAPIClient] = None


def get_api_client(context) -> AsyncAPIClient:
    """
    Get or create the global API client.
    
    Args:
        context: Blender context
        
    Returns:
        AsyncAPIClient instance
    """
    global _global_client
    
    prefs = context.preferences.addons[__package__].preferences
    
    if _global_client is None:
        _global_client = AsyncAPIClient(prefs.api_endpoint, prefs.auth_token)
    else:
        # Update endpoint and token if changed
        _global_client.client.base_url = prefs.api_endpoint.rstrip('/')
        _global_client.client.token = prefs.auth_token
    
    return _global_client


def reset_api_client():
    """Reset the global API client (e.g., on logout)."""
    global _global_client
    _global_client = None
