"""
AWS Lambda function for AI chatbot with LangGraph chat agent.
Handles streaming responses, conversation management, and authentication.
"""

import json
import os
import logging
import time
from typing import Dict, Any, Generator, Optional
from src.services.database import init_db_connection
from src.auth.cognito import extract_user_from_event
from src.services.conversations import (
    create_conversation,
    get_conversation,
    add_message,
    get_conversation_context,
    update_conversation_title,
    generate_title_from_query
)
from src.core.chat_agent import run_chat_agent
from src.services.bedrock_client import stream_bedrock_response

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize database connection (reused across invocations)
if not os.environ.get('SKIP_DB_INIT'):
    init_db_connection()

# Preload embedding models to reduce cold start time
from src.services.embeddings import preload_models
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



def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively convert objects to JSON-serializable format.
    - Decimal -> float/int
    - datetime -> string
    """
    from datetime import datetime, date
    from decimal import Decimal
    
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(i) for i in obj]
    return obj


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for chatbot requests.
    
    Supports multiple endpoints:
    - POST /chat - Main chat endpoint with agent
    - POST /auth - Authenticate user with Cognito
    - POST /signup - Create new user account
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
        elif path == '/signup' and http_method == 'POST':
            return handle_signup(event, context)
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
        
        # Run chat agent to get SQL query results and final answer
        start_time = time.time()
        agent_result = run_chat_agent(
            query=query,
            conversation_history=conversation_history,
            uploaded_image_base64=uploaded_image_base64,
            max_attempts=2
        )
        agent_time = time.time() - start_time
        
        logger.info(f"Chat agent completed in {agent_time:.2f}s with {agent_result['attempts']} SQL attempts and {len(agent_result.get('query_results', []))} results")
        
        # Check if streaming is enabled (default: true)
        enable_streaming = os.environ.get('ENABLE_STREAMING', 'true').lower() == 'true'
        
        if enable_streaming:
            # Stream final response
            def generate_sse_stream() -> Generator[str, None, None]:
                """Generate Server-Sent Events stream with agent steps and final answer"""
                
                # Stream agent start
                yield format_sse_event('agent_start', {
                    'conversation_id': conversation_id,
                    'attempts': agent_result['attempts']
                })
                
                # Stream enhanced query if available
                if agent_result.get('enhanced_query'):
                    yield format_sse_event('enhanced_query', {
                        'query': agent_result['enhanced_query']
                    })
            
                # Stream ALL SQL queries (including retries) with their results and feedback
                all_sql_queries = agent_result.get('all_sql_queries', [])
                if all_sql_queries:
                    for query_info in all_sql_queries:
                        # Send SQL query
                        yield format_sse_event('sql_query', {
                            'query': query_info['sql'],
                            'attempt': query_info.get('attempt', 1)
                        })
                        
                        # Send query results if available
                        if query_info.get('results') is not None:
                            yield format_sse_event('query_results', {
                                'count': query_info.get('result_count', 0),
                                'attempt': query_info.get('attempt', 1),
                                'results': sanitize_for_json(query_info['results'][:5])  # First 5 as preview
                            })
                        
                        # Send feedback if this attempt was unsatisfactory
                        if query_info.get('feedback'):
                            yield format_sse_event('retry_feedback', {
                                'feedback': query_info['feedback'],
                                'attempt': query_info.get('attempt', 1)
                            })
                elif agent_result.get('sql_query'):
                    # Fallback to single query if history not available
                    yield format_sse_event('sql_query', {
                        'query': agent_result['sql_query'],
                        'attempt': 1
                    })
                
                # Stream final query results (for backward compatibility)
                query_results = agent_result.get('query_results', [])
                if query_results and not all_sql_queries:
                    yield format_sse_event('query_results', {
                        'count': len(query_results),
                        'results': sanitize_for_json(query_results[:5])  # First 5 results as preview
                    })
                    
                    # Stream thumbnails if available
                    for item in query_results[:10]:  # Top 10 with thumbnails
                        if item.get('thumbnail_url'):
                            yield format_sse_event('thumbnail', {
                                'file_id': item.get('id'),
                                'file_name': item.get('file_name'),
                                'thumbnail_url': item['thumbnail_url']
                            })
                
                # Stream final answer
                yield format_sse_event('answer_start', {})
                
                full_response = agent_result.get('final_answer', 'No answer generated.')
                
                # If final_answer is a prompt (old behavior), stream from Bedrock
                # Otherwise, just send the answer directly
                if full_response and full_response.startswith('<|begin_of_text|>'):
                    # It's a prompt, stream from Bedrock
                    streamed_response = ""
                    for chunk in stream_bedrock_response(full_response):
                        streamed_response += chunk
                        yield format_sse_event('answer_chunk', {'text': chunk})
                    full_response = streamed_response
                else:
                    # It's already the final answer, send it
                    yield format_sse_event('answer_chunk', {'text': full_response})
                
                yield format_sse_event('answer_end', {})
                
                # Save assistant response to conversation
                # Make sure to use DynamoDB format (Decimals)
                dynamo_query_results = make_json_serializable(query_results)
                add_message(
                    conversation_id,
                    user_id,
                    'assistant',
                    full_response,
                    tool_calls=[{
                        'sql_query': agent_result.get('sql_query'),
                        'result_count': len(query_results),
                        'results': dynamo_query_results[:10]  # Store top 10
                    }]
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
            from src.services.bedrock_client import invoke_bedrock_for_reasoning
            
            # Get final response
            full_response = agent_result.get('final_answer', 'No answer generated.')
            
            # If final_answer is a prompt, generate response from Bedrock
            if full_response and full_response.startswith('<|begin_of_text|>'):
                full_response = invoke_bedrock_for_reasoning(full_response)
            
            # Save assistant response to conversation (DynamoDB format)
            query_results = agent_result.get('query_results', [])
            dynamo_query_results = make_json_serializable(query_results)
            
            add_message(
                conversation_id,
                user_id,
                'assistant',
                full_response,
                tool_calls=[{
                    'sql_query': agent_result.get('sql_query'),
                    'result_count': len(query_results),
                    'results': dynamo_query_results[:10]
                }]
            )
            
            # Prepare JSON response (JSON format)
            json_query_results = sanitize_for_json(query_results)
            
            # Return complete JSON response
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'conversation_id': conversation_id,
                    'attempts': agent_result['attempts'],
                    'sql_query': agent_result.get('sql_query'),
                    'query_results': json_query_results,
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
        
        from src.services.conversations import list_conversations
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
        from src.auth.cognito import authenticate_user
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


def handle_signup(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle POST /signup - create new user account in Cognito.
    """
    try:
        # Parse request body
        body_str = event.get('body', '{}')
        
        # Handle base64 encoding
        if event.get('isBase64Encoded', False) and isinstance(body_str, str):
            import base64
            try:
                body_str = base64.b64decode(body_str).decode('utf-8')
            except Exception as e:
                logger.error(f"Base64 decode error: {e}")
        
        # Parse JSON
        try:
            if isinstance(body_str, str):
                body = json.loads(body_str.strip())
            elif isinstance(body_str, dict):
                body = body_str
            else:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'error': 'Invalid request body format'})
                }
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': f'Invalid JSON: {str(e)}'})
            }
        
        # Extract credentials
        email = body.get('email')
        password = body.get('password')
        
        if not email or not password:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Email and password are required'})
            }
        
        logger.info(f"Signup attempt for user: {email}")
        
        # Create user in Cognito
        from src.auth.cognito import signup_user
        result = signup_user(email, password)
        
        if result['success']:
            logger.info(f"Signup successful for user: {email}")
            
            # If user is auto-confirmed and we have tokens, return them
            if result.get('user_confirmed') and result.get('tokens'):
                return {
                    'statusCode': 200,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'message': result['message'],
                        'user_confirmed': True,
                        'id_token': result['tokens']['id_token'],
                        'access_token': result['tokens']['access_token'],
                        'refresh_token': result['tokens']['refresh_token'],
                        'user_id': email
                    })
                }
            else:
                # User needs to confirm email
                return {
                    'statusCode': 200,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'message': result['message'],
                        'user_confirmed': False
                    })
                }
        else:
            logger.warning(f"Signup failed for user: {email} - {result['message']}")
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': result['message']})
            }
        
    except Exception as e:
        logger.error(f"Error in handle_signup: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Signup service error'})
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
        
        from src.services.conversations import delete_conversation
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
        event_type: Type of event (e.g., 'sql_query', 'query_results', 'answer_chunk', 'thumbnail')
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
