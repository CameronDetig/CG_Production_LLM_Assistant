"""
Simple wrapper for AWS Bedrock LLM calls using LangChain.
All prompt building is handled in chat_agent.py.
"""

import os
import logging
from typing import Union, Iterator
from langchain_aws import ChatBedrock

logger = logging.getLogger()

# Initialize reusable LangChain Bedrock client (persists across Lambda invocations)
_bedrock_client = None


def _get_bedrock_client(streaming: bool = False, temperature: float = 0.7, max_tokens: int = 2048) -> ChatBedrock:
    """
    Get or create a reusable ChatBedrock client.
    Client is cached at module level for reuse across invocations.
    
    Args:
        streaming: Whether to enable streaming
        temperature: Model temperature
        max_tokens: Maximum tokens to generate
        
    Returns:
        ChatBedrock instance
    """
    global _bedrock_client
    
    model_id = os.environ.get('BEDROCK_MODEL_ID', 'meta.llama4-scout-17b-instruct-v1:0')
    region = os.environ.get('AWS_REGION', 'us-east-1')
    
    # Create new client if none exists or if parameters changed significantly
    # (LangChain clients are lightweight, so we recreate for different streaming modes)
    if _bedrock_client is None or _bedrock_client.streaming != streaming:
        _bedrock_client = ChatBedrock(
            model_id=model_id,
            region_name=region,
            model_kwargs={
                "temperature": temperature,
                "max_gen_len": max_tokens,
                "top_p": 0.9,
            },
            streaming=streaming,
        )
        logger.info(f"Created Bedrock client: {model_id} (streaming={streaming})")
    
    return _bedrock_client


def invoke_bedrock(
    prompt: str,
    streaming: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 2048
) -> Union[str, Iterator[str]]:
    """
    Invoke AWS Bedrock LLM via LangChain.
    
    Args:
        prompt: The complete prompt to send to the model
        streaming: If True, returns an iterator of text chunks. If False, returns complete text.
        temperature: Model temperature (0.0-1.0). Lower = more focused, higher = more creative.
        max_tokens: Maximum tokens to generate
        
    Returns:
        If streaming=False: Complete response text as string
        If streaming=True: Iterator yielding text chunks
        
    Examples:
        # Non-streaming (for SQL generation, reasoning)
        response = invoke_bedrock("Generate SQL...", streaming=False, temperature=0.3, max_tokens=512)
        
        # Streaming (for user-facing responses)
        for chunk in invoke_bedrock("Answer this...", streaming=True):
            print(chunk, end='')
    """
    try:
        # Get reusable client
        llm = _get_bedrock_client(streaming=streaming, temperature=temperature, max_tokens=max_tokens)
        
        if streaming:
            # Return iterator for streaming responses
            def stream_generator():
                try:
                    for chunk in llm.stream(prompt):
                        text = chunk.content if hasattr(chunk, 'content') else str(chunk)
                        if text:
                            yield text
                except Exception as e:
                    logger.error(f"Error during streaming: {str(e)}", exc_info=True)
                    yield f"\n\n[Error: {str(e)}]"
            
            return stream_generator()
            
        else:
            # Return complete response for non-streaming
            response = llm.invoke(prompt)
            text = response.content if hasattr(response, 'content') else str(response)
            logger.info(f"Bedrock response length: {len(text)} chars")
            return text
            
    except Exception as e:
        logger.error(f"Error invoking Bedrock: {str(e)}", exc_info=True)
        if streaming:
            def error_generator():
                yield f"Error: {str(e)}"
            return error_generator()
        else:
            return f"Error: {str(e)}"
