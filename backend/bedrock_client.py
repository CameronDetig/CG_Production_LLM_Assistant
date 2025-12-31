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
    region_name=os.environ.get('AWS_REGION', 'us-east-1')  # AWS_REGION is auto-set by Lambda
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


def invoke_bedrock_for_reasoning(prompt: str) -> str:
    """
    Invoke Bedrock model for reasoning (non-streaming).
    Used by the agent for tool selection and reasoning steps.
    
    Args:
        prompt: ReAct-style prompt for reasoning
        
    Returns:
        Model's response text
    """
    model_id = os.environ.get('BEDROCK_MODEL_ID', 'meta.llama3-2-11b-instruct-v1:0')
    
    request_body = {
        "prompt": prompt,
        "max_gen_len": 512,  # Shorter for reasoning steps
        "temperature": 0.3,  # Lower temperature for more focused reasoning
        "top_p": 0.9,
    }
    
    try:
        logger.info(f"Calling Bedrock for reasoning: {model_id}")
        
        response = bedrock_runtime.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response.get('body').read())
        text = response_body.get('generation', '')
        
        logger.info(f"Reasoning response length: {len(text)} chars")
        return text
        
    except Exception as e:
        logger.error(f"Error invoking Bedrock for reasoning: {str(e)}", exc_info=True)
        return f"Error: {str(e)}"


def build_prompt(query: str, metadata_results: List[Dict[str, Any]], db_stats: Dict[str, Any] = None) -> str:
    """
    Build prompt with metadata context for Llama model.
    
    Args:
        query: User's query
        metadata_results: List of relevant metadata entries from database
        db_stats: Optional database statistics for count queries
        
    Returns:
        Formatted prompt string
    """
    # Format metadata context based on actual database schema
    context_parts = []
    for idx, item in enumerate(metadata_results, 1):
        file_type = item.get('file_type', 'unknown')
        
        # Build context based on file type
        if file_type == 'blend':
            context_parts.append(
                f"{idx}. **{item.get('file_name', 'Unknown')}** (Blender File)\n"
                f"   - Path: {item.get('file_path', 'N/A')}\n"
                f"   - Resolution: {item.get('resolution_x', 'N/A')}x{item.get('resolution_y', 'N/A')}\n"
                f"   - Render Engine: {item.get('render_engine', 'N/A')}\n"
                f"   - Frames: {item.get('num_frames', 'N/A')}\n"
                f"   - Objects: {item.get('total_objects', 'N/A')}\n"
                f"   - Modified: {item.get('modified_date', 'N/A')}"
            )
        elif file_type == 'image':
            context_parts.append(
                f"{idx}. **{item.get('file_name', 'Unknown')}** (Image)\n"
                f"   - Path: {item.get('file_path', 'N/A')}\n"
                f"   - Dimensions: {item.get('image_width', 'N/A')}x{item.get('image_height', 'N/A')}\n"
                f"   - Mode: {item.get('image_mode', 'N/A')}\n"
                f"   - Size: {_format_file_size(item.get('file_size', 0))}\n"
                f"   - Modified: {item.get('modified_date', 'N/A')}"
            )
        elif file_type == 'video':
            context_parts.append(
                f"{idx}. **{item.get('file_name', 'Unknown')}** (Video)\n"
                f"   - Path: {item.get('file_path', 'N/A')}\n"
                f"   - Dimensions: {item.get('video_width', 'N/A')}x{item.get('video_height', 'N/A')}\n"
                f"   - Duration: {item.get('duration', 'N/A')}s\n"
                f"   - FPS: {item.get('video_fps', 'N/A')}\n"
                f"   - Codec: {item.get('codec', 'N/A')}\n"
                f"   - Modified: {item.get('modified_date', 'N/A')}"
            )
        else:
            # Generic file
            context_parts.append(
                f"{idx}. **{item.get('file_name', 'Unknown')}** ({file_type})\n"
                f"   - Path: {item.get('file_path', 'N/A')}\n"
                f"   - Size: {_format_file_size(item.get('file_size', 0))}\n"
                f"   - Modified: {item.get('modified_date', 'N/A')}"
            )
        
        # Add similarity score if available
        if 'similarity' in item:
            context_parts[-1] += f"\n   - Relevance: {item['similarity']:.2%}"
    
    context = "\n\n".join(context_parts) if context_parts else "No relevant files found in the database."
    
    # Add database statistics if provided (for count queries)
    stats_context = ""
    if db_stats:
        stats_context = f"""

DATABASE STATISTICS:
- Total files in database: {db_stats.get('total_files', 0)}
- Total images: {db_stats.get('total_images', 0)}
- Total videos: {db_stats.get('total_videos', 0)}
- Total Blender files: {db_stats.get('total_blend_files', 0)}

Files by type:
"""
        for file_type, count in db_stats.get('files_by_type', {}).items():
            stats_context += f"- {file_type}: {count}\n"
    
    # Llama 3.2 prompt format (instruction-following)
    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an AI assistant helping artists and production teams find and understand their CG production assets stored in a database. You have access to metadata about Blender files, images, videos, and other production files.

Your role is to:
- Answer questions about file locations, specifications, and project organization
- Translate technical metadata into creative insights
- Help artists make informed decisions about asset usage
- Be concise, helpful, and production-focused
- Reference specific files by name when answering
- When asked about counts or totals, use the DATABASE STATISTICS section which shows the ACTUAL total counts

{stats_context}
Available files matching the query (showing top {len(metadata_results)} most relevant):
{context}
<|eot_id|><|start_header_id|>user<|end_header_id|>

{query}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
    
    return prompt


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    if size_bytes is None:
        return "N/A"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


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
