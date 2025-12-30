"""
DynamoDB conversation management.
Handles CRUD operations for conversation history and messages.
"""

import os
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Initialize DynamoDB client (reused across Lambda invocations)
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Configuration
TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'cg-chatbot-conversations')
table = dynamodb.Table(TABLE_NAME)


def create_conversation(user_id: str, title: str = "New Conversation") -> str:
    """
    Create a new conversation.
    
    Args:
        user_id: User identifier from Cognito
        title: Conversation title (auto-generated from first query)
        
    Returns:
        conversation_id (UUID string)
        
    Example:
        >>> conv_id = create_conversation('demo', 'Search for 4K renders')
        >>> print(conv_id)
        '550e8400-e29b-41d4-a716-446655440000'
    """
    conversation_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat() + 'Z'
    
    try:
        table.put_item(
            Item={
                'conversation_id': conversation_id,
                'user_id': user_id,
                'title': title,
                'messages': [],
                'created_at': timestamp,
                'updated_at': timestamp,
                'message_count': 0
            }
        )
        
        logger.info(f"Created conversation {conversation_id} for user {user_id}")
        return conversation_id
        
    except ClientError as e:
        logger.error(f"Error creating conversation: {str(e)}", exc_info=True)
        raise


def get_conversation(conversation_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a conversation by ID.
    
    Args:
        conversation_id: UUID of conversation
        user_id: User identifier (for access control)
        
    Returns:
        Conversation dict or None if not found
        
    Example:
        >>> conv = get_conversation('550e8400-...', 'demo')
        >>> print(conv['title'])
        'Search for 4K renders'
    """
    try:
        response = table.get_item(
            Key={
                'conversation_id': conversation_id,
                'user_id': user_id
            }
        )
        
        return response.get('Item')
        
    except ClientError as e:
        logger.error(f"Error getting conversation {conversation_id}: {str(e)}", exc_info=True)
        return None


def list_conversations(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    List all conversations for a user, sorted by creation date (newest first).
    
    Args:
        user_id: User identifier
        limit: Maximum number of conversations to return
        
    Returns:
        List of conversation dicts (without full message history)
        
    Example:
        >>> conversations = list_conversations('demo', limit=10)
        >>> for conv in conversations:
        ...     print(f"{conv['title']} - {conv['message_count']} messages")
    """
    try:
        response = table.query(
            IndexName='user_id-created_at-index',
            KeyConditionExpression='user_id = :uid',
            ExpressionAttributeValues={
                ':uid': user_id
            },
            ScanIndexForward=False,  # Descending order (newest first)
            Limit=limit,
            ProjectionExpression='conversation_id, user_id, title, created_at, updated_at, message_count'
        )
        
        return response.get('Items', [])
        
    except ClientError as e:
        logger.error(f"Error listing conversations for user {user_id}: {str(e)}", exc_info=True)
        return []


def add_message(
    conversation_id: str,
    user_id: str,
    role: str,
    content: str,
    tool_calls: Optional[List[Dict]] = None
) -> bool:
    """
    Add a message to a conversation.
    
    Args:
        conversation_id: UUID of conversation
        user_id: User identifier
        role: Message role ('user', 'assistant', 'system')
        content: Message content
        tool_calls: Optional list of tool calls (for assistant messages)
        
    Returns:
        True if successful, False otherwise
        
    Example:
        >>> add_message('550e8400-...', 'demo', 'user', 'Show me 4K renders')
        >>> add_message('550e8400-...', 'demo', 'assistant', 'I found 5 renders...', 
        ...             tool_calls=[{'tool': 'filter_by_metadata', 'args': {...}}])
    """
    timestamp = datetime.utcnow().isoformat() + 'Z'
    
    message = {
        'role': role,
        'content': content,
        'timestamp': timestamp
    }
    
    if tool_calls:
        message['tool_calls'] = tool_calls
    
    try:
        # Append message to messages list and update metadata
        table.update_item(
            Key={
                'conversation_id': conversation_id,
                'user_id': user_id
            },
            UpdateExpression='SET messages = list_append(if_not_exists(messages, :empty_list), :new_message), '
                           'updated_at = :timestamp, '
                           'message_count = if_not_exists(message_count, :zero) + :one',
            ExpressionAttributeValues={
                ':new_message': [message],
                ':empty_list': [],
                ':timestamp': timestamp,
                ':zero': 0,
                ':one': 1
            }
        )
        
        logger.info(f"Added {role} message to conversation {conversation_id}")
        return True
        
    except ClientError as e:
        logger.error(f"Error adding message to conversation {conversation_id}: {str(e)}", exc_info=True)
        return False


def delete_conversation(conversation_id: str, user_id: str) -> bool:
    """
    Delete a conversation.
    
    Args:
        conversation_id: UUID of conversation
        user_id: User identifier (for access control)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        table.delete_item(
            Key={
                'conversation_id': conversation_id,
                'user_id': user_id
            }
        )
        
        logger.info(f"Deleted conversation {conversation_id}")
        return True
        
    except ClientError as e:
        logger.error(f"Error deleting conversation {conversation_id}: {str(e)}", exc_info=True)
        return False


def get_conversation_context(conversation_id: str, user_id: str, max_messages: int = 10) -> List[Dict[str, Any]]:
    """
    Get recent messages from a conversation for LLM context.
    Returns the last N messages to keep context window manageable.
    
    Args:
        conversation_id: UUID of conversation
        user_id: User identifier
        max_messages: Maximum number of recent messages to return
        
    Returns:
        List of recent messages (oldest to newest)
        
    Example:
        >>> context = get_conversation_context('550e8400-...', 'demo', max_messages=5)
        >>> for msg in context:
        ...     print(f"{msg['role']}: {msg['content'][:50]}...")
    """
    conversation = get_conversation(conversation_id, user_id)
    
    if not conversation:
        return []
    
    messages = conversation.get('messages', [])
    
    # Return last N messages
    return messages[-max_messages:] if len(messages) > max_messages else messages


def update_conversation_title(conversation_id: str, user_id: str, title: str) -> bool:
    """
    Update conversation title (e.g., auto-generate from first query).
    
    Args:
        conversation_id: UUID of conversation
        user_id: User identifier
        title: New title
        
    Returns:
        True if successful, False otherwise
    """
    try:
        table.update_item(
            Key={
                'conversation_id': conversation_id,
                'user_id': user_id
            },
            UpdateExpression='SET title = :title',
            ExpressionAttributeValues={
                ':title': title
            }
        )
        
        logger.info(f"Updated title for conversation {conversation_id}")
        return True
        
    except ClientError as e:
        logger.error(f"Error updating conversation title: {str(e)}", exc_info=True)
        return False


def generate_title_from_query(query: str, max_length: int = 50) -> str:
    """
    Generate a conversation title from the first user query.
    
    Args:
        query: User's first query
        max_length: Maximum title length
        
    Returns:
        Generated title
        
    Example:
        >>> title = generate_title_from_query('Show me all 4K renders from the lighting project')
        >>> print(title)
        '4K Renders from Lighting Project'
    """
    # Simple title generation - capitalize and truncate
    # In production, could use LLM to generate better titles
    
    # Remove common question words
    query_lower = query.lower()
    for word in ['show me', 'find', 'get', 'what', 'where', 'how', 'can you']:
        query_lower = query_lower.replace(word, '')
    
    # Clean up and capitalize
    title = query_lower.strip().capitalize()
    
    # Truncate if too long
    if len(title) > max_length:
        title = title[:max_length-3] + '...'
    
    return title if title else "New Conversation"
