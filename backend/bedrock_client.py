"""
Bedrock client for streaming Llama model responses.
"""

import os
import json
import logging
import boto3
from typing import Generator, List, Dict, Any

logger = logging.getLogger()

# Initialize Bedrock client (reused across invocations)
bedrock_runtime = boto3.client(
    service_name='bedrock-runtime',
    region_name=os.environ.get('AWS_REGION', 'us-east-1')
)


def stream_bedrock_response(prompt: str) -> Generator[str, None, None]:
    """
    Stream response from Bedrock Llama model.
    
    Args:
        prompt: Full prompt with context and user query
        
    Yields:
        Text chunks from the model
    """
    model_id = os.environ.get('BEDROCK_MODEL_ID', 'meta.llama3-2-11b-instruct-v1:0')
    
    # Llama 3.2 request format
    request_body = {
        "prompt": prompt,
        "max_gen_len": 2048,  # Maximum tokens to generate
        "temperature": 0.7,   # Creativity (0.0-1.0)
        "top_p": 0.9,         # Nucleus sampling
    }
    
    try:
        logger.info(f"Calling Bedrock model: {model_id}")
        
        response = bedrock_runtime.invoke_model_with_response_stream(
            modelId=model_id,
            body=json.dumps(request_body)
        )
        
        # Process streaming response
        stream = response.get('body')
        if stream:
            for event in stream:
                chunk = event.get('chunk')
                if chunk:
                    chunk_data = json.loads(chunk.get('bytes').decode())
                    
                    # Extract text from Llama response
                    if 'generation' in chunk_data:
                        text = chunk_data['generation']
                        if text:
                            yield text
                    
                    # Check for completion
                    if chunk_data.get('stop_reason') == 'stop':
                        break
        
    except Exception as e:
        logger.error(f"Error streaming from Bedrock: {str(e)}", exc_info=True)
        yield f"\n\n[Error: Unable to generate response - {str(e)}]"


def build_prompt(query: str, metadata_results: List[Dict[str, Any]]) -> str:
    """
    Build prompt with metadata context for Llama model.
    
    Args:
        query: User's query
        metadata_results: List of relevant metadata entries from database
        
    Returns:
        Formatted prompt string
    """
    # Format metadata context
    context_parts = []
    for idx, item in enumerate(metadata_results, 1):
        context_parts.append(
            f"{idx}. {item.get('file_name', 'Unknown')} - "
            f"Resolution: {item.get('resolution', 'N/A')}, "
            f"Color Space: {item.get('color_space', 'N/A')}, "
            f"Project: {item.get('project_name', 'N/A')}, "
            f"Tags: {item.get('tags', 'N/A')}"
        )
    
    context = "\n".join(context_parts) if context_parts else "No relevant files found."
    
    # Llama 3.2 prompt format (instruction-following)
    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an AI assistant helping artists and production teams find and understand their CG production assets. You have access to a database of Blender files with technical metadata.

Your role is to:
- Answer questions about file locations, specifications, and project organization
- Translate technical metadata into creative insights
- Help artists make informed decisions about asset usage
- Be concise, helpful, and production-focused

Available file metadata:
{context}
<|eot_id|><|start_header_id|>user<|end_header_id|>

{query}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
    
    return prompt


def select_model(query: str) -> str:
    """
    Select appropriate Llama model based on query complexity (future enhancement).
    
    Args:
        query: User's query
        
    Returns:
        Model ID to use
    """
    # Simple heuristic: use larger model for complex queries
    complex_keywords = ['compare', 'analyze', 'explain', 'difference', 'why', 'how']
    
    if any(keyword in query.lower() for keyword in complex_keywords):
        # Use larger model for complex reasoning
        return os.environ.get('BEDROCK_LARGE_MODEL_ID', 'meta.llama3-1-70b-instruct-v1:0')
    
    # Default to smaller, faster model
    return os.environ.get('BEDROCK_MODEL_ID', 'meta.llama3-2-11b-instruct-v1:0')
