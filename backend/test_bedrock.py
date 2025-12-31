"""
Simple Bedrock test to measure LLM response time.
Tests the Llama model used by the agent.
"""

import boto3
import time
import json

# Initialize Bedrock client
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

# Test prompt
prompt = """<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are a helpful assistant.

<|eot_id|><|start_header_id|>user<|end_header_id|>

Show me recent images

<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""

# Bedrock request
request_body = {
    "prompt": prompt,
    "max_gen_len": 512,
    "temperature": 0.7,
    "top_p": 0.9
}

print("Testing Bedrock LLM response time...")
print(f"Model: us.meta.llama3-2-11b-instruct-v1:0")
print(f"Prompt length: {len(prompt)} chars")
print("-" * 60)

start_time = time.time()

try:
    response = bedrock.invoke_model(
        modelId='us.meta.llama3-2-11b-instruct-v1:0',  # Use inference profile
        body=json.dumps(request_body),
        contentType='application/json',
        accept='application/json'
    )
    
    response_time = time.time() - start_time
    
    # Parse response
    response_body = json.loads(response['body'].read())
    generated_text = response_body.get('generation', '')
    
    print(f"✅ Response received in {response_time:.2f} seconds")
    print(f"Response length: {len(generated_text)} chars")
    print("-" * 60)
    print("Generated text:")
    print(generated_text[:500])  # First 500 chars
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    response_time = time.time() - start_time
    print(f"Failed after {response_time:.2f} seconds")
