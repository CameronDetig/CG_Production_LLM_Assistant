"""
LangGraph ReAct agent implementation with custom Llama prompting.
Implements agentic workflow for intelligent tool selection and reasoning.
"""

import logging
import json
import time
from typing import List, Dict, Any, Optional, TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from bedrock_client import invoke_bedrock_for_reasoning, stream_bedrock_response
from tools import AVAILABLE_TOOLS

logger = logging.getLogger()


class AgentState(TypedDict):
    """State for the ReAct agent."""
    messages: Annotated[List[BaseMessage], operator.add]
    user_query: str
    conversation_history: List[Dict[str, str]]
    tool_results: List[Dict[str, Any]]
    iteration: int
    max_iterations: int
    final_answer: Optional[str]
    uploaded_image_base64: Optional[str]


# Maximum iterations to prevent infinite loops
MAX_ITERATIONS = 5


def create_react_agent() -> StateGraph:
    """
    Create the LangGraph ReAct agent workflow.
    
    Returns:
        Compiled StateGraph for agent execution
    """
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("reasoning", reasoning_node)
    workflow.add_node("tool_execution", tool_execution_node)
    workflow.add_node("final_response", final_response_node)
    
    # Add edges
    workflow.add_edge("reasoning", "tool_execution")
    workflow.add_conditional_edges(
        "tool_execution",
        should_continue,
        {
            "continue": "reasoning",
            "finish": "final_response"
        }
    )
    workflow.add_edge("final_response", END)
    
    # Set entry point
    workflow.set_entry_point("reasoning")
    
    return workflow.compile()


def reasoning_node(state: AgentState) -> AgentState:
    """
    Reasoning node: LLM decides which tools to call based on the query and previous results.
    
    Uses custom ReAct prompting for Llama models.
    """
    start_time = time.time()
    logger.info(f"Reasoning node - Iteration {state['iteration']}")
    
    # Build ReAct prompt for Llama
    prompt_start = time.time()
    prompt = build_react_prompt(
        query=state['user_query'],
        conversation_history=state.get('conversation_history', []),
        tool_results=state.get('tool_results', []),
        iteration=state['iteration']
    )
    logger.info(f"Prompt built in {time.time() - prompt_start:.2f}s")
    
    # Get LLM response with tool decisions
    bedrock_start = time.time()
    response = invoke_bedrock_for_reasoning(prompt)
    logger.info(f"Bedrock reasoning call took {time.time() - bedrock_start:.2f}s")
    
    # Parse tool calls from response
    tool_calls = parse_tool_calls_from_response(response)
    
    # Add to messages
    state['messages'].append(AIMessage(content=response))
    
    # Store tool calls for execution
    if not state.get('tool_results'):
        state['tool_results'] = []
    
    # Add parsed tool calls to state
    for tool_call in tool_calls:
        state['tool_results'].append({
            'tool': tool_call['tool'],
            'args': tool_call['args'],
            'result': None  # Will be filled by tool_execution_node
        })
    
    logger.info(f"Reasoning node completed in {time.time() - start_time:.2f}s")
    return state


def tool_execution_node(state: AgentState) -> AgentState:
    """
    Tool execution node: Execute the tools selected by the reasoning node.
    """
    start_time = time.time()
    logger.info(f"Tool execution node - Executing {len(state['tool_results'])} tools")
    
    # Execute tools that don't have results yet
    for tool_result in state['tool_results']:
        if tool_result['result'] is None:
            tool_name = tool_result['tool']
            tool_args = tool_result['args']
            
            # Find and execute the tool
            tool_func = get_tool_by_name(tool_name)
            if tool_func:
                try:
                    tool_start = time.time()
                    result = tool_func.invoke(tool_args)
                    tool_result['result'] = result
                    logger.info(f"Executed tool {tool_name} in {time.time() - tool_start:.2f}s with {len(result) if isinstance(result, list) else 1} results")
                except Exception as e:
                    logger.error(f"Error executing tool {tool_name}: {str(e)}", exc_info=True)
                    tool_result['result'] = {"error": str(e)}
            else:
                logger.error(f"Tool {tool_name} not found")
                tool_result['result'] = {"error": f"Tool {tool_name} not found"}
    
    # Increment iteration
    state['iteration'] += 1
    
    logger.info(f"Tool execution node completed in {time.time() - start_time:.2f}s")
    return state


def final_response_node(state: AgentState) -> AgentState:
    """
    Final response node: Generate user-facing response based on all gathered information.
    """
    logger.info("Final response node - Generating answer")
    
    # Build final prompt with all tool results
    final_prompt = build_final_response_prompt(
        query=state['user_query'],
        conversation_history=state.get('conversation_history', []),
        tool_results=state['tool_results']
    )
    
    # Generate final response (this will be streamed in lambda_function.py)
    # For now, just store the prompt
    state['final_answer'] = final_prompt
    
    return state


def should_continue(state: AgentState) -> str:
    """
    Conditional edge: Determine if agent should continue reasoning or finish.
    
    Returns:
        "continue" if more reasoning needed, "finish" if ready for final answer
    """
    # Check if max iterations reached
    if state['iteration'] >= state['max_iterations']:
        logger.info(f"Max iterations ({state['max_iterations']}) reached")
        return "finish"
    
    # Early termination: if we have tool results with data, finish
    if state.get('tool_results') and len(state['tool_results']) > 0:
        # Check if all tools have results
        all_have_results = all(tr.get('result') is not None for tr in state['tool_results'])
        if all_have_results:
            # Check if any tool returned actual data (not just errors)
            has_data = any(
                (isinstance(tr.get('result'), list) and len(tr['result']) > 0) or
                (isinstance(tr.get('result'), dict) and not tr['result'].get('error'))
                for tr in state['tool_results']
            )
            if has_data:
                logger.info("Tool results contain data, finishing early")
                return "finish"
    
    # Continue reasoning if no tool results yet
    return "continue" if state['iteration'] < state['max_iterations'] else "finish"


def build_react_prompt(
    query: str,
    conversation_history: List[Dict[str, str]],
    tool_results: List[Dict[str, Any]],
    iteration: int
) -> str:
    """
    Build ReAct-style prompt for Llama model.
    
    Custom prompting since Llama doesn't natively support function calling.
    """
    # Tool descriptions
    tools_desc = """
Available Tools:
1. search_by_metadata_embedding(query: str, limit: int = 10)
   - Search files using semantic text similarity on metadata
   - Use for: finding files by description, keywords, concepts
   
2. search_by_visual_embedding(description: str, limit: int = 10)
   - Search images/videos by visual content description
   - Use for: finding images/videos by what they look like
   
3. search_by_uploaded_image(image_base64: str, limit: int = 10)
   - Find similar images to an uploaded image
   - Use for: reverse image search
   
4. keyword_search_tool(query: str, limit: int = 10)
   - Traditional keyword search on filenames and paths
   - Use for: exact filename matches
   
5. analytics_query()
   - Get database statistics and counts
   - Use for: "how many files", "statistics", "totals"
   
6. filter_by_metadata(file_type: str, min_resolution_x: int, min_resolution_y: int, extension: str, limit: int = 10)
   - Filter files by specific criteria
   - Use for: "4K renders", "blend files", "PNG images"
   
7. get_file_details(file_id: int)
   - Get detailed info about a specific file
   - Use for: "tell me about file 123"
"""
    
    # Conversation context
    context = ""
    if conversation_history:
        context = "Previous conversation:\n"
        for msg in conversation_history[-5:]:  # Last 5 messages
            context += f"{msg['role']}: {msg['content']}\n"
        context += "\n"
    
    # Previous tool results
    results_context = ""
    if tool_results:
        results_context = "Previous tool results:\n"
        for tr in tool_results:
            if tr.get('result'):
                result_summary = f"Tool: {tr['tool']}\n"
                result_summary += f"Args: {json.dumps(tr['args'])}\n"
                
                # Summarize result
                result = tr['result']
                if isinstance(result, list):
                    result_summary += f"Found {len(result)} results\n"
                    if result:
                        result_summary += f"Sample: {result[0].get('file_name', 'N/A')}\n"
                elif isinstance(result, dict):
                    result_summary += f"Result: {json.dumps(result, indent=2)[:200]}...\n"
                
                results_context += result_summary + "\n"
    
    # ReAct prompt
    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an AI assistant helping users find CG production assets. You have access to tools to search a database of Blender files, images, and videos.

{tools_desc}

Your task: Analyze the user's query and decide which tool(s) to call. Think step-by-step.

Format your response as:
Thought: [Your reasoning about what tools to use]
Action: [Tool name]
Action Input: {{"arg1": "value1", "arg2": value2}}

If you have enough information to answer, respond with:
Thought: I have sufficient information to answer
Final Answer: [Your answer]

<|eot_id|><|start_header_id|>user<|end_header_id|>

{context}{results_context}
User Query: {query}

Iteration: {iteration + 1}/{MAX_ITERATIONS}

<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
    
    return prompt


def build_final_response_prompt(
    query: str,
    conversation_history: List[Dict[str, str]],
    tool_results: List[Dict[str, Any]]
) -> str:
    """
    Build prompt for generating final user-facing response.
    """
    # Summarize tool results
    results_summary = ""
    for tr in tool_results:
        if tr.get('result'):
            results_summary += f"\nTool: {tr['tool']}\n"
            result = tr['result']
            
            if isinstance(result, list):
                results_summary += f"Found {len(result)} results:\n"
                for item in result[:5]:  # Top 5
                    results_summary += f"- {item.get('file_name', 'Unknown')}: {item.get('file_path', 'N/A')}\n"
                    if item.get('thumbnail_url'):
                        results_summary += f"  Thumbnail: {item['thumbnail_url']}\n"
            elif isinstance(result, dict):
                results_summary += f"{json.dumps(result, indent=2)}\n"
    
    # Conversation context
    context = ""
    if conversation_history:
        context = "Previous conversation:\n"
        for msg in conversation_history[-3:]:
            context += f"{msg['role']}: {msg['content']}\n"
        context += "\n"
    
    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an AI assistant for CG production asset management. Generate a helpful, concise response to the user's query based on the information gathered.

{context}
Information gathered:
{results_summary}

<|eot_id|><|start_header_id|>user<|end_header_id|>

{query}

<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
    
    return prompt


def parse_tool_calls_from_response(response: str) -> List[Dict[str, Any]]:
    """
    Parse tool calls from Llama's ReAct-style response.
    
    Looks for patterns like:
    Action: tool_name
    Action Input: {"arg": "value"}
    """
    tool_calls = []
    
    lines = response.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for "Action:" line
        if line.startswith('Action:'):
            tool_name = line.replace('Action:', '').strip()
            
            # Look for "Action Input:" on next line
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith('Action Input:'):
                    input_str = next_line.replace('Action Input:', '').strip()
                    
                    try:
                        # Parse JSON input
                        tool_args = json.loads(input_str)
                        tool_calls.append({
                            'tool': tool_name,
                            'args': tool_args
                        })
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse tool input: {input_str}")
        
        i += 1
    
    return tool_calls


def get_tool_by_name(tool_name: str):
    """Get tool function by name."""
    for tool in AVAILABLE_TOOLS:
        if tool.name == tool_name:
            return tool
    return None


def run_agent(
    query: str,
    conversation_history: List[Dict[str, str]] = None,
    uploaded_image_base64: str = None,
    max_iterations: int = MAX_ITERATIONS
) -> Dict[str, Any]:
    """
    Run the ReAct agent for a user query.
    
    Args:
        query: User's query
        conversation_history: Previous conversation messages
        uploaded_image_base64: Optional uploaded image for search
        max_iterations: Maximum reasoning iterations
        
    Returns:
        Dict with final_answer and tool_results
    """
    # Initialize state
    initial_state = AgentState(
        messages=[HumanMessage(content=query)],
        user_query=query,
        conversation_history=conversation_history or [],
        tool_results=[],
        iteration=0,
        max_iterations=max_iterations,
        final_answer=None,
        uploaded_image_base64=uploaded_image_base64
    )
    
    # Create and run agent
    agent = create_react_agent()
    final_state = agent.invoke(initial_state)
    
    return {
        'final_answer': final_state.get('final_answer'),
        'tool_results': final_state.get('tool_results', []),
        'iterations': final_state.get('iteration', 0)
    }
