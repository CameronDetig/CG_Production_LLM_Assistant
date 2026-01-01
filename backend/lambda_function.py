"""
AWS Lambda function for AI chatbot with LangGraph ReAct agent.
Handles streaming responses, conversation management, and authentication.
"""

import json
import os
import logging
import time
from typing import Dict, Any, Generator, Optional
from database import init_db_connection
from auth import extract_user_from_event
from conversations import (
    create_conversation,
    get_conversation,
    add_message,
    get_conversation_context,
    update_conversation_title,
    generate_title_from_query
)
from agent import run_agent
from bedrock_client import stream_bedrock_response

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize database connection (reused across invocations)
if not os.environ.get('SKIP_DB_INIT'):
    init_db_connection()

# Preload embedding models to reduce cold start time
from embeddings import preload_models
preload_models()


def make_json_serializable(obj: Any) -> Any:
    """
    Recursively convert objects to DynamoDB-compatible format.
    Handles datetime objects by converting to ISO string.
    Handles float objects by converting to Decimal.
    """
    from datetime import datetime, date
    from decimal import Decimal
    
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [make_json_serializable(i) for i in obj]
    return obj


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for chatbot requests.
    
    Supports multiple endpoints:
    - POST /chat - Main chat endpoint with agent
    - POST /auth - Authenticate user with Cognito
    - GET /conversations - List user's conversations
    - GET /conversations/{id} - Get specific conversation
    - DELETE /conversations/{id} - Delete conversation
    
    Args:
        event: API Gateway event
        context: Lambda context object
        
    Returns:
        API Gateway response
    """
    try:
        # Lambda Function URLs and API Gateway have different event structures
        # Lambda Function URL: event['requestContext']['http']['method'], event['rawPath']
        # API Gateway: event['httpMethod'], event['path']
        
        # Detect event type and extract method and path
        if 'requestContext' in event and 'http' in event.get('requestContext', {}):
            # Lambda Function URL format
            http_method = event['requestContext']['http']['method']
            path = event.get('rawPath', '/')
            logger.info(f"Lambda Function URL request: {http_method} {path}")
        else:
            # API Gateway format
            http_method = event.get('httpMethod', 'POST')
            path = event.get('path', '/chat')
            logger.info(f"API Gateway request: {http_method} {path}")
        
        # Route to appropriate handler
        if path == '/chat' and http_method == 'POST':
            return handle_chat(event, context)
        elif path == '/auth' and http_method == 'POST':
            return handle_auth(event, context)
        elif path == '/conversations' and http_method == 'GET':
            return handle_list_conversations(event, context)
        elif path.startswith('/conversations/') and http_method == 'GET':
            return handle_get_conversation(event, context)
        elif path.startswith('/conversations/') and http_method == 'DELETE':
            return handle_delete_conversation(event, context)
        else:
            logger.warning(f"Endpoint not found: {http_method} {path}")
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': f'Endpoint not found: {http_method} {path}'})
            }
            
    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Internal server error', 'details': str(e)})
        }


def handle_chat(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle /chat endpoint - main agent interaction.
    """
    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        query = body.get('query', '')
        conversation_id = body.get('conversation_id')
        uploaded_image_base64 = body.get('uploaded_image_base64')
        
        if not query:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Query is required'})
            }
        
        # Extract user from JWT token
        user_id = extract_user_from_event(event)
        if not user_id:
            # Allow anonymous for demo (or require auth by returning 401)
            user_id = 'anonymous'
            logger.warning("No valid auth token, using anonymous user")
        
        logger.info(f"Processing query from user {user_id}: {query[:100]}")
        
        # Get or create conversation
        conversation_history = []
        if conversation_id:
            # Load existing conversation
            conversation = get_conversation(conversation_id, user_id)
            if conversation:
                conversation_history = get_conversation_context(conversation_id, user_id, max_messages=10)
                logger.info(f"Loaded conversation {conversation_id} with {len(conversation_history)} messages")
            else:
                logger.warning(f"Conversation {conversation_id} not found, creating new one")
                conversation_id = None
        
        if not conversation_id:
            # Create new conversation
            title = generate_title_from_query(query)
            conversation_id = create_conversation(user_id, title)
            logger.info(f"Created new conversation {conversation_id}: {title}")
        
        # Add user message to conversation
        add_message(conversation_id, user_id, 'user', query)
        
        # Run agent to get tool results and final answer prompt
        start_time = time.time()
        agent_result = run_agent(
            query=query,
            conversation_history=conversation_history,
            uploaded_image_base64=uploaded_image_base64,
            max_iterations=5
        )
        agent_time = time.time() - start_time
        
        logger.info(f"Agent completed in {agent_time:.2f}s with {agent_result['iterations']} iterations and {len(agent_result['tool_results'])} tool calls")
        
        # Check if streaming is enabled (default: true)
        enable_streaming = os.environ.get('ENABLE_STREAMING', 'true').lower() == 'true'
        
        if enable_streaming:
            # Stream final response
            def generate_sse_stream() -> Generator[str, None, None]:
                """Generate Server-Sent Events stream with agent steps and final answer"""
                
                # Stream agent reasoning steps
                yield format_sse_event('agent_start', {
                    'conversation_id': conversation_id,
                    'iterations': agent_result['iterations']
                })
            
                # Stream tool calls
                for tool_result in agent_result['tool_results']:
                    yield format_sse_event('tool_call', {
                        'tool': tool_result['tool'],
                        'args': tool_result['args']
                    })
                    
                    # Stream tool result summary
                    result = tool_result.get('result', [])
                    if isinstance(result, list):
                        yield format_sse_event('tool_result', {
                            'tool': tool_result['tool'],
                            'count': len(result),
                            'results': result[:3]  # First 3 results as preview
                        })
                        
                        # Stream thumbnails if available
                        for item in result[:10]:  # Top 10 with thumbnails
                            if item.get('thumbnail_url'):
                                yield format_sse_event('thumbnail', {
                                    'file_id': item.get('id'),
                                    'file_name': item.get('file_name'),
                                    'thumbnail_url': item['thumbnail_url']
                                })
                    elif isinstance(result, dict):
                        yield format_sse_event('tool_result', {
                            'tool': tool_result['tool'],
                            'result': result
                        })
                
                # Stream final answer from Bedrock
                yield format_sse_event('answer_start', {})
                
                full_response = ""
                final_prompt = agent_result['final_answer']
                
                for chunk in stream_bedrock_response(final_prompt):
                    full_response += chunk
                    yield format_sse_event('answer_chunk', {'text': chunk})
                
                yield format_sse_event('answer_end', {})
                
                # Save assistant response to conversation
                add_message(
                    conversation_id,
                    user_id,
                    'assistant',
                    full_response,
                    tool_calls=agent_result['tool_results']
                )
                
                # Send final event
                yield format_sse_event('done', {
                    'conversation_id': conversation_id,
                    'message_count': len(conversation_history) + 2  # +2 for user query and assistant response
                })
        
            # Return streaming response
            return {
                'statusCode': 200,
                'headers': {
                    **get_cors_headers(),
                    'Content-Type': 'text/event-stream',
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive'
                },
                'body': ''.join(generate_sse_stream())
            }
        
        else:
            # NON-STREAMING MODE: Return complete JSON response
            from bedrock_client import invoke_bedrock_for_reasoning
            
            # Generate complete response (non-streaming)
            final_prompt = agent_result['final_answer']
            full_response = invoke_bedrock_for_reasoning(final_prompt)
            
            # Save assistant response to conversation
            # Ensure tool_results are JSON serializable (convert datetime to string)
            sanitized_tool_results = make_json_serializable(agent_result['tool_results'])
            
            add_message(
                conversation_id,
                user_id,
                'assistant',
                full_response,
                tool_calls=sanitized_tool_results
            )
            
            # Return complete JSON response
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'conversation_id': conversation_id,
                    'iterations': agent_result['iterations'],
                    'tool_calls': agent_result['tool_results'],
                    'answer': full_response,
                    'message_count': len(conversation_history) + 2
                }, indent=2)  # Pretty print for easier reading
            }
        
    except Exception as e:
        logger.error(f"Error in handle_chat: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def handle_list_conversations(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle GET /conversations - list user's conversations.
    """
    try:
        user_id = extract_user_from_event(event)
        if not user_id:
            return {
                'statusCode': 401,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Authentication required'})
            }
        
        from conversations import list_conversations
        conversations = list_conversations(user_id, limit=50)
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({'conversations': conversations})
        }
        
    except Exception as e:
        logger.error(f"Error listing conversations: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def handle_get_conversation(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle GET /conversations/{id} - get specific conversation.
    """
    try:
        user_id = extract_user_from_event(event)
        if not user_id:
            return {
                'statusCode': 401,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Authentication required'})
            }
        
        # Extract conversation_id from path
        path_params = event.get('pathParameters', {})
        conversation_id = path_params.get('id')
        
        if not conversation_id:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Conversation ID required'})
            }
        
        conversation = get_conversation(conversation_id, user_id)
        
        if not conversation:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Conversation not found'})
            }
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({'conversation': conversation})
        }
        
    except Exception as e:
        logger.error(f"Error getting conversation: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def handle_auth(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle POST /auth - authenticate user with Cognito.
    This endpoint allows frontend to authenticate without boto3 client.
    """
    try:
        # Log the entire event for debugging
        logger.info(f"Auth event keys: {list(event.keys())}")
        
        # Parse request body - handle multiple formats
        body_str = event.get('body', '{}')
        
        logger.info(f"Body type: {type(body_str)}, isBase64: {event.get('isBase64Encoded', False)}")
        logger.info(f"Body preview: {str(body_str)[:100]}")
        
        # Handle base64 encoding
        if event.get('isBase64Encoded', False) and isinstance(body_str, str):
            import base64
            try:
                body_str = base64.b64decode(body_str).decode('utf-8')
                logger.info(f"Decoded body: {body_str}")
            except Exception as e:
                logger.error(f"Base64 decode error: {e}")
        
        # Parse JSON with error handling
        try:
            if isinstance(body_str, str):
                # Strip any whitespace
                body_str = body_str.strip()
                logger.info(f"Parsing JSON: {body_str}")
                body = json.loads(body_str)
            elif isinstance(body_str, dict):
                body = body_str
            else:
                logger.error(f"Unexpected body type: {type(body_str)}")
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'error': 'Invalid request body format'})
                }
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}, body was: {repr(body_str)}")
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': f'Invalid JSON: {str(e)}'})
            }
        
        # Extract credentials
        email = body.get('email')
        password = body.get('password')
        
        if not email or not password:
            logger.warning(f"Missing credentials in body: {body}")
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Email and password are required'})
            }
        
        logger.info(f"Authentication attempt for user: {email}")
        
        # Authenticate with Cognito
        from auth import authenticate_user
        tokens = authenticate_user(email, password)
        
        if tokens:
            logger.info(f"Authentication successful for user: {email}")
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'id_token': tokens['id_token'],
                    'access_token': tokens['access_token'],
                    'refresh_token': tokens['refresh_token'],
                    'user_id': email
                })
            }
        else:
            logger.warning(f"Authentication failed for user: {email}")
            return {
                'statusCode': 401,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Invalid email or password'})
            }
        
    except Exception as e:
        logger.error(f"Error in handle_auth: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Authentication service error'})
        }


def handle_delete_conversation(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle DELETE /conversations/{id} - delete conversation.
    """
    try:
        user_id = extract_user_from_event(event)
        if not user_id:
            return {
                'statusCode': 401,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Authentication required'})
            }
        
        # Extract conversation_id from path
        path_params = event.get('pathParameters', {})
        conversation_id = path_params.get('id')
        
        if not conversation_id:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Conversation ID required'})
            }
        
        from conversations import delete_conversation
        success = delete_conversation(conversation_id, user_id)
        
        if success:
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({'message': 'Conversation deleted'})
            }
        else:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Conversation not found'})
            }
        
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """
    Format data as Server-Sent Event.
    
    Args:
        event_type: Type of event (e.g., 'answer_chunk', 'tool_call')
        data: Event data
        
    Returns:
        Formatted SSE string
    """
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def get_cors_headers() -> Dict[str, str]:
    """Get CORS headers for API responses."""
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
    }
