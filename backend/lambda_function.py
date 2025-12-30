"""
AWS Lambda function for AI chatbot with Bedrock (Llama) and PostgreSQL integration.
Handles streaming responses for real-time chat experience.
Uses semantic search with text and image embeddings.
"""

import json
import os
import logging
from typing import Dict, Any, Generator
from database import get_relevant_metadata, init_db_connection
from bedrock_client import stream_bedrock_response, build_prompt

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize database connection (reused across invocations)
# For local testing, this can be skipped if SKIP_DB_INIT is set
if not os.environ.get('SKIP_DB_INIT'):
    init_db_connection()

# Optional: Preload embedding models to reduce cold start time
# Uncomment if using containerized deployment (models are large ~500MB)
# from embeddings import preload_models
# preload_models()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for chatbot requests.
    
    Args:
        event: API Gateway event with 'body' containing JSON payload
        context: Lambda context object
        
    Returns:
        Streaming response in SSE format
    """
    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        query = body.get('query', '')
        user_id = body.get('user_id', 'anonymous')
        
        if not query:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Query is required'})
            }
        
        logger.info(f"Processing query from user {user_id}: {query[:100]}")
        
        # Check if this is a statistics/count query
        count_keywords = ['how many', 'count', 'total', 'number of', 'statistics', 'stats']
        is_count_query = any(keyword in query.lower() for keyword in count_keywords)
        
        # Step 1: Retrieve relevant metadata from PostgreSQL
        metadata_results = get_relevant_metadata(query, limit=50)
        logger.info(f"Found {len(metadata_results)} relevant metadata entries")
        
        # If it's a count query, also get database statistics
        db_stats = None
        if is_count_query:
            from database import get_database_stats
            db_stats = get_database_stats()
            logger.info(f"Retrieved database stats: {db_stats.get('total_files', 0)} total files")
        
        # Step 2: Build prompt with context
        prompt = build_prompt(query, metadata_results, db_stats)

        
        # Step 3: Stream response from Bedrock
        def generate_sse_stream() -> Generator[str, None, None]:
            """Generate Server-Sent Events stream"""
            try:
                # Send start event
                yield format_sse_event({
                    'type': 'start',
                    'metadata_count': len(metadata_results)
                })
                
                # Stream Bedrock response
                full_response = ""
                for chunk in stream_bedrock_response(prompt):
                    full_response += chunk
                    yield format_sse_event({
                        'type': 'chunk',
                        'text': chunk
                    })
                
                # Send metadata context (optional - for UI to display sources)
                if metadata_results:
                    # Convert datetime objects to strings for JSON serialization
                    serializable_metadata = []
                    for item in metadata_results[:5]:
                        serializable_item = dict(item)
                        # Convert datetime fields to ISO format strings
                        if 'created_date' in serializable_item and serializable_item['created_date']:
                            serializable_item['created_date'] = serializable_item['created_date'].isoformat()
                        if 'modified_date' in serializable_item and serializable_item['modified_date']:
                            serializable_item['modified_date'] = serializable_item['modified_date'].isoformat()
                        serializable_metadata.append(serializable_item)
                    
                    yield format_sse_event({
                        'type': 'metadata',
                        'files': serializable_metadata
                    })
                
                # Send end event
                yield format_sse_event({'type': 'end'})
                
                logger.info(f"Successfully streamed response ({len(full_response)} chars)")
                
                # Future: Store conversation in DynamoDB
                # store_conversation(user_id, query, full_response, metadata_results)
                
            except Exception as e:
                logger.error(f"Error during streaming: {str(e)}", exc_info=True)
                yield format_sse_event({
                    'type': 'error',
                    'message': f'Streaming error: {str(e)}'
                })
        
        # Return streaming response
        return {
            'statusCode': 200,
            'headers': {
                **get_cors_headers(),
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
            },
            'body': generate_sse_stream()
        }
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }


def format_sse_event(data: Dict[str, Any]) -> str:
    """Format data as Server-Sent Event"""
    return f"data: {json.dumps(data)}\n\n"


def get_cors_headers() -> Dict[str, str]:
    """Get CORS headers for API responses"""
    return {
        'Access-Control-Allow-Origin': '*',  # Update with your Hugging Face Space URL
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key',
        'Access-Control-Allow-Methods': 'POST,OPTIONS'
    }


def store_conversation(user_id: str, query: str, response: str, metadata: list):
    """
    Store conversation in DynamoDB (future implementation).
    
    Args:
        user_id: User identifier
        query: User's query
        response: AI's response
        metadata: Metadata context used
    """
    # TODO: Implement DynamoDB storage
    # import boto3
    # from datetime import datetime
    # import uuid
    # 
    # dynamodb = boto3.resource('dynamodb')
    # table = dynamodb.Table(os.environ.get('CONVERSATIONS_TABLE', 'conversations'))
    # 
    # table.put_item(
    #     Item={
    #         'conversation_id': str(uuid.uuid4()),
    #         'user_id': user_id,
    #         'timestamp': datetime.utcnow().isoformat(),
    #         'query': query,
    #         'response': response,
    #         'metadata_used': metadata,
    #         'model': os.environ.get('BEDROCK_MODEL_ID', 'llama-3.2-11b')
    #     }
    # )
    pass
