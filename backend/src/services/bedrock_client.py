"""
Simple wrapper for AWS Bedrock LLM calls using LangChain.
All prompt building is handled in chat_agent.py.
"""

import os
import logging
from typing import Union, Iterator
import langchain_aws.chat_models.bedrock_converse as bedrock_converse_module
from langchain_aws import ChatBedrock

# Monkey patch to handle 'reasoningContent' in Bedrock Converse API response
# Use a safe-guard to avoid infinite recursion if patched multiple times
if not getattr(bedrock_converse_module, "_is_patched_for_reasoning", False):
    _original_bedrock_to_lc = bedrock_converse_module._bedrock_to_lc

    def _bedrock_to_lc_patched(content):
        # Filter out reasoningContent blocks which cause validation errors in current langchain-aws
        filtered_content = []
        for block in content:
            if "reasoningContent" in block:
                # content is list regarding to the implementation of bedrock_converse
                # We log it for visibility but exclude it from LangChain parsing to prevent crash
                logging.getLogger(__name__).info("Skipping reasoningContent block from model response")
                continue
            filtered_content.append(block)
        return _original_bedrock_to_lc(filtered_content)

    bedrock_converse_module._bedrock_to_lc = _bedrock_to_lc_patched
    bedrock_converse_module._is_patched_for_reasoning = True

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
        # Determine model-specific parameters
        model_kwargs = {
            "temperature": temperature,
            "top_p": 0.9,
        }
        
        # Llama models use max_gen_len, others typically use max_tokens
        # We also enable Converse API for 'openai' models to bypass provider checks
        # and handle standard message formats better
        use_converse_api = False
        if "llama" in model_id.lower():
            model_kwargs["max_gen_len"] = max_tokens
        else:
            # Assuming openai.gpt-oss-20b-1:0 and others follow standard naming
            model_kwargs["max_tokens"] = max_tokens
            if "openai" in model_id.lower():
                use_converse_api = True

        _bedrock_client = ChatBedrock(
            model_id=model_id,
            region_name=region,
            model_kwargs=model_kwargs,
            streaming=streaming,
            beta_use_converse_api=use_converse_api,
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
