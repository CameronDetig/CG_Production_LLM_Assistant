"""
LangGraph chat agent with LLM-based SQL query generation.
Provides flexible SQL generation.
"""

import logging
import json
import time
import yaml
import os
from typing import List, Dict, Any, Optional, TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

# Import services
from psycopg2.extras import RealDictCursor
from src.services.database import get_connection, release_connection, _add_thumbnail_urls
from src.services.bedrock_client import invoke_bedrock
from src.services.embeddings import (
    generate_text_embedding,
    generate_image_embedding_from_text,
    generate_image_embedding_from_base64
)


logger = logging.getLogger()

# Load semantic file (contains database structure and relationships, custom instructions, verified queries)
SEMANTIC_FILE_PATH = os.path.join(os.path.dirname(__file__), 'semantic_file.yaml')
with open(SEMANTIC_FILE_PATH, 'r') as f:
    SEMANTIC_FILE_DICT = yaml.safe_load(f)

# contains the whole semantic file as a string
SEMANTIC_FILE_STR = yaml.dump(SEMANTIC_FILE_DICT, default_flow_style=False)

# contains the individual components of the semantic file as strings
DATABASE_INFO_STR = yaml.dump(SEMANTIC_FILE_DICT.get('database_info', []), default_flow_style=False)
CUSTOM_INSTRUCTIONS_STR = yaml.dump(SEMANTIC_FILE_DICT.get('custom_instructions', []), default_flow_style=False)
DATABASE_SCHEMA_STR = yaml.dump(SEMANTIC_FILE_DICT.get('tables', []), default_flow_style=False)
VERIFIED_QUERIES_STR = yaml.dump(SEMANTIC_FILE_DICT.get('verified_queries', []), default_flow_style=False)


class ChatAgentState(TypedDict):
    """State for the chat agent."""
    messages: Annotated[List[BaseMessage], operator.add]
    user_query: str
    conversation_history: List[Dict[str, str]]
    uploaded_image_base64: Optional[str]
    
    # New fields for SQL generation
    enhanced_query: Optional[str]
    query_intent: Optional[Dict[str, Any]]
    text_embedding: Optional[List[float]]  # For semantic text search
    visual_embedding: Optional[List[float]]  # For image similarity search
    sql_query: Optional[str]
    sql_params: Optional[List[Any]]
    query_results: Optional[List[Dict[str, Any]]]
    evaluation_feedback: Optional[str]
    attempt_count: int
    max_attempts: int
    final_answer: Optional[str]
    sql_query_history: List[Dict[str, Any]]  # Track all SQL queries attempted


# Maximum SQL generation attempts
MAX_ATTEMPTS = 2


def create_chat_agent() -> StateGraph:
    """
    Create the LangGraph chat agent workflow.
    
    Returns:
        Compiled StateGraph for agent execution
    """
    workflow = StateGraph(ChatAgentState)
    
    # Add nodes
    workflow.add_node("query_router_node", query_router)
    workflow.add_node("embedding_determination", embedding_determination_node)
    workflow.add_node("sql_generation", sql_generation_node)
    workflow.add_node("result_evaluation", result_evaluation_node)
    
    # Add conditional edge from query_router_node
    # If query is not database-related, final_answer is set and we go to END
    # Otherwise, continue to embedding_determination for SQL pipeline
    workflow.add_conditional_edges(
        "query_router_node",
        lambda state: "finish" if state.get('final_answer') else "continue",
        {
            "continue": "embedding_determination",
            "finish": END
        }
    )
    
    # Add edges
    workflow.add_edge("embedding_determination", "sql_generation")
    workflow.add_edge("sql_generation", "result_evaluation")
    workflow.add_conditional_edges(
        "result_evaluation",
        should_retry_sql,
        {
            "retry": "sql_generation",
            "finish": END
        }
    )
    
    # Set entry point
    workflow.set_entry_point("query_router_node")
    
    return workflow.compile()


def query_router(state: ChatAgentState) -> ChatAgentState:
    """
    Enhance the user's query using conversation history and database structure.
    Extracts intent and clarifies what the user is looking for.
    """
    start_time = time.time()
    logger.info("Prompt enhancement node - Analyzing user query")
    
    # Build context from conversation history. Only include the last 5 messages to keep the prompt concise.
    conversation_recall_depth = 5  # how many previous messages to include in conversation context
    context = ""
    if state.get('conversation_history'):
        context = "Previous conversation:\n"
        for msg in state['conversation_history'][-conversation_recall_depth:]:
            context += f"{msg['role']}: {msg['content']}\n"
        context += "\n"
    
    # Build prompt for enhancement
    prompt = f"""
You are analyzing a user's query and routing it to the appropriate node in the workflow.
The user may ask questions about the cg-production-data database that require an SQL query to be generated, 
or they may ask general questions that can simply be answered by you directly.

User's query: {state['user_query']}

Here is information on the database:
{DATABASE_INFO_STR}

Database schema:
{DATABASE_SCHEMA_STR}

The chat history is as follows:
{context}

{"User uploaded an image for similarity search." if state.get('uploaded_image_base64') else ""}

INSTRUCTIONS:
First, determine if the user's query relates to the database (asking about files, metadata, shows, assets, etc.) 
or if it's a general question (asking about concepts, seeking advice, casual conversation, etc.).

If the user's query RELATES TO THE DATABASE:
1. Set "is_database_query" to true
2. Enhance their question by:
   - Understanding what they're asking for
   - Identifying key search criteria (file types, folders, attributes, etc.)
   - Determining if they need similarity search (semantic or visual)
   - Clarifying any ambiguous terms
3. Fill in the "enhanced_query" and "intent" fields

If the user's query DOES NOT RELATE TO THE DATABASE:
1. Set "is_database_query" to false
2. Provide a helpful, direct answer to their question in the "direct_answer" field
3. You can leave "enhanced_query" and "intent" empty or with placeholder values

Respond in strict JSON format:
{{
  "is_database_query": true|false,
  "enhanced_query": "Clarified version of the query (if database-related)",
  "intent": {{
    "search_type": "similarity|filter|count|details",
    "file_types": ["image", "video", "blend"],
    "needs_text_embedding": true|false,
    "needs_visual_embedding": true|false,
    "key_criteria": ["list", "of", "criteria"]
  }},
  "direct_answer": "Your answer to the user's general question (if not database-related)"
}}
"""
    
    # Get LLM response
    response = invoke_bedrock(prompt, streaming=False, temperature=0.3, max_tokens=1024)
    
    # Parse JSON response
    try:
        # Extract JSON from response (may have extra text)
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            json_str = response[json_start:json_end]
            parsed = json.loads(json_str)
            
            # Check if this is a database query or general question
            is_database_query = parsed.get('is_database_query', True)
            
            if not is_database_query:
                # This is a general question - answer directly and skip SQL pipeline
                direct_answer = parsed.get('direct_answer', 
                    "I'm designed to help with CG production asset database queries. Your question doesn't seem related to the database. Could you ask about files, metadata, shows, or production data?")
                state['final_answer'] = direct_answer
                state['query_results'] = []
                logger.info(f"Non-database query detected. Direct answer: {direct_answer[:100]}...")
            else:
                # This is a database query - enhance it for SQL generation
                state['enhanced_query'] = parsed.get('enhanced_query', state['user_query'])
                state['query_intent'] = parsed.get('intent', {})
                logger.info(f"Database query detected. Enhanced query: {state['enhanced_query']}")
                logger.info(f"Intent: {state['query_intent']}")
        else:
            logger.warning("Could not parse JSON from enhancement response")
            state['enhanced_query'] = state['user_query']
            state['query_intent'] = {"search_type": "similarity", "needs_text_embedding": True}
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in prompt enhancement: {e}")
        state['enhanced_query'] = state['user_query']
        state['query_intent'] = {"search_type": "similarity", "needs_text_embedding": True}
    
    logger.info(f"Prompt enhancement completed in {time.time() - start_time:.2f}s")
    
    return state


def embedding_determination_node(state: ChatAgentState) -> ChatAgentState:
    """
    Determine if embeddings are needed and generate them.
    Handles text embeddings for semantic search and visual embeddings for image search.
    """
    start_time = time.time()
    logger.info("Embedding determination node")
    
    intent = state.get('query_intent', {})
    
    # Generate text embedding if needed
    if intent.get('needs_text_embedding', False):
        try:
            embed_start = time.time()
            state['text_embedding'] = generate_text_embedding(state['enhanced_query'])
            logger.info(f"Text embedding generated in {time.time() - embed_start:.2f}s")
        except Exception as e:
            logger.error(f"Error generating text embedding: {e}", exc_info=True)
            state['text_embedding'] = None
    
    # Generate visual embedding if needed
    if intent.get('needs_visual_embedding', False):
        try:
            embed_start = time.time()
            
            # If user uploaded an image, use that
            if state.get('uploaded_image_base64'):
                state['visual_embedding'] = generate_image_embedding_from_base64(
                    state['uploaded_image_base64']
                )
                logger.info(f"Visual embedding from uploaded image generated in {time.time() - embed_start:.2f}s")
            else:
                # Otherwise, generate from text description
                state['visual_embedding'] = generate_image_embedding_from_text(
                    state['enhanced_query']
                )
                logger.info(f"Visual embedding from text generated in {time.time() - embed_start:.2f}s")
        except Exception as e:
            logger.error(f"Error generating visual embedding: {e}", exc_info=True)
            state['visual_embedding'] = None
    
    logger.info(f"Embedding determination completed in {time.time() - start_time:.2f}s")
    return state


def sql_generation_node(state: ChatAgentState) -> ChatAgentState:
    """
    Generate SQL query using LLM based on enhanced query, intent, and embeddings.
    Uses database structure and example queries to guide generation.
    """
    start_time = time.time()
    logger.info(f"SQL generation node - Attempt {state['attempt_count'] + 1}/{state['max_attempts']}")
    
    # Build conversation history context for follow-up questions
    conversation_recall_depth = 3  # how many previous messages to include in conversation context
    conversation_context = ""
    if state.get('conversation_history'):
        for msg in state['conversation_history'][-conversation_recall_depth:]:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            conversation_context += f"{role}: {content}\n"
            
            # If this is an assistant message with tool_calls (SQL query), include it
            if role == 'assistant' and 'tool_calls' in msg:
                tool_calls = msg.get('tool_calls', [])
                if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
                    sql_query = tool_calls[0].get('sql_query')
                    if sql_query:
                        conversation_context += f"  [SQL used: {sql_query}]\n"
    
    # Build embedding context
    embedding_context = ""
    if state.get('text_embedding'):
        embedding_str = f"[{','.join(map(str, state['text_embedding']))}]"
        embedding_context += f"\nText embedding available: If needed, use '[EMBEDDING_VECTOR]'::vector in your query, which will be replaced with: {embedding_str[:100]}..."
    
    if state.get('visual_embedding'):
        embedding_str = f"[{','.join(map(str, state['visual_embedding']))}]"
        embedding_context += f"\nVisual embedding available: If needed, use '[VISUAL_EMBEDDING]'::vector in your query, which will be replaced with: {embedding_str[:100]}..."
    
    # Build feedback context if this is a retry
    feedback_context = ""
    if state.get('evaluation_feedback'):
        feedback_context = f"\n\nPrevious attempt failed. Feedback:\n{state['evaluation_feedback']}\n\nGenerate an improved query."
    
    # Build prompt for SQL generation
    prompt = f"""
You are a PostgreSQL query generator for a database of assets from a CG production studio. 
Generate an SQL query to answer the user's question.

Recent conversation (for context on follow-up questions):
{conversation_context}

Current User Query: {state['enhanced_query']}

Intent: {json.dumps(state.get('query_intent', {}), indent=2)}
{feedback_context}

Here is the semantic file that defines the database schema, verified queries, and custom instructions:
{SEMANTIC_FILE_STR}

Here is the embedding context:
{embedding_context}

IMPORTANT RULES:
1. **Column References**: Only use columns that exist in the table you're querying
   
2. **Show Filtering**: Use the show column in files table for filtering by show
   - Example: WHERE f.show = 'show1' (not LIKE '%show1%')
   - 'other' is used for files not belonging to a specific show
   
3. **JOINs**: Use proper JOINs based on relationships:
   
4. **Similarity Search**: Use <=> operator for vector similarity
   - Example: ORDER BY metadata_embedding <=> '[EMBEDDING_VECTOR]'::vector
   
5. **SELECT Only**: Only generate SELECT queries (no INSERT, UPDATE, DELETE)

6. **Example Queries**: Refer to the verified_queries section in the schema for patterns


Generate a PostgreSQL query to answer the user's query. Respond in strict JSON format like this:
{{
  "sql": "SELECT ...",
  "explanation": "Brief explanation of what the query does"
}}
"""
    
    # Get LLM response
    response = invoke_bedrock(prompt, streaming=False, temperature=0.3, max_tokens=1024)
    
    # Parse SQL from response
    try:
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            json_str = response[json_start:json_end]
            parsed = json.loads(json_str)
            sql = parsed.get('sql', '')
            
            # Replace embedding placeholders
            if state.get('text_embedding'):
                embedding_str = f"[{','.join(map(str, state['text_embedding']))}]"
                sql = sql.replace('[EMBEDDING_VECTOR]', embedding_str)
            
            if state.get('visual_embedding'):
                embedding_str = f"[{','.join(map(str, state['visual_embedding']))}]"
                sql = sql.replace('[VISUAL_EMBEDDING]', embedding_str)
            
            state['sql_query'] = sql
            
            # Add to query history (will be updated with results later)
            state['sql_query_history'].append({
                'sql': sql,
                'attempt': state['attempt_count'] + 1,
                'results': None,  # Will be filled in result_evaluation_node
                'feedback': None  # Will be filled if retry needed
            })
            
            logger.info(f"Generated SQL: {sql[:200]}...")
        else:
            logger.error("Could not extract JSON from SQL generation response")
            state['sql_query'] = None
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in SQL generation: {e}")
        state['sql_query'] = None
    
    logger.info(f"SQL generation completed in {time.time() - start_time:.2f}s")
    return state


def result_evaluation_node(state: ChatAgentState) -> ChatAgentState:
    """
    Execute SQL query and evaluate if results answer the user's question.
    If not satisfied and attempts < max, generate feedback for retry.
    Otherwise, generate final answer.
    """
    start_time = time.time()
    logger.info("Result evaluation node")
    
    # Execute SQL query
    if not state.get('sql_query'):
        state['final_answer'] = "I was unable to generate a valid SQL query for your request. Please try reformatting your question."
        state['query_results'] = []
        return state
    
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Validate query is SELECT only
        sql_upper = state['sql_query'].strip().upper()
        if not sql_upper.startswith('SELECT') and not sql_upper.startswith('WITH'):
            raise ValueError("Only SELECT queries are allowed")
        
        # Execute query
        exec_start = time.time()
        cursor.execute(state['sql_query'])
        results = cursor.fetchall()
        logger.info(f"Query executed in {time.time() - exec_start:.2f}s, returned {len(results)} rows")
        
        # Convert to list of dicts and add thumbnail URLs
        state['query_results'] = [dict(row) for row in results]
        state['query_results'] = _add_thumbnail_urls(state['query_results'])
        
        # Update query history with results
        if state['sql_query_history']:
            state['sql_query_history'][-1]['results'] = state['query_results']
            state['sql_query_history'][-1]['result_count'] = len(state['query_results'])
        
        cursor.close()
        release_connection(conn)
        
    except Exception as e:
        logger.error(f"Error executing SQL: {e}", exc_info=True)
        state['query_results'] = []
        state['evaluation_feedback'] = f"SQL execution error: {str(e)}"
        state['attempt_count'] += 1
        return state
    
    # Generate CSV-formatted results for display
    csv_results = ""
    markdown_table = ""
    if state['query_results']:
        # Get all column names (excluding internal fields)
        exclude_cols = {'thumbnail_url', 'thumbnail_path'}
        if state['query_results']:
            all_cols = [k for k in state['query_results'][0].keys() if k not in exclude_cols]
            
            # Create CSV header
            csv_results = ",".join(all_cols) + "\n"
            
            # Create markdown table header
            markdown_table = "| " + " | ".join(all_cols) + " |\n"
            markdown_table += "| " + " | ".join(["---"] * len(all_cols)) + " |\n"
            
            # Add data rows (limit to 50 for display)
            for row in state['query_results'][:50]:
                csv_row = []
                md_row = []
                for col in all_cols:
                    value = row.get(col, '')
                    # Handle None
                    if value is None:
                        csv_row.append('')
                        md_row.append('')
                    else:
                        # For CSV: escape quotes and commas
                        str_val = str(value).replace('"', '""')
                        if ',' in str_val or '\n' in str_val:
                            csv_row.append(f'"{str_val}"')
                        else:
                            csv_row.append(str_val)
                        
                        # For markdown: escape pipes
                        md_val = str(value).replace('|', '\\|')
                        md_row.append(md_val)
                
                csv_results += ",".join(csv_row) + "\n"
                markdown_table += "| " + " | ".join(md_row) + " |\n"
    
    # Prepare results summary for LLM evaluation
    results_summary = ""
    if state['query_results']:
        results_summary = f"Found {len(state['query_results'])} results.\n\n"
        results_summary += "Results (CSV format):\n"
        results_summary += csv_results[:1000]  # Limit to first 1000 chars for LLM
        if len(csv_results) > 1000:
            results_summary += "\n... (truncated)"
    else:
        results_summary = "No results found."
    
    eval_prompt = f"""
Evaluate if the SQL query results answer the user's question.

IMPORTANT: 
- For COUNT, SUM, AVG, MIN, MAX queries, a single row result IS the complete answer
- The row contains the aggregate value that directly answers the question
- An answer of 0 (zero) is a VALID and COMPLETE answer - it means "there are none"
- Do NOT mark 0 (zero) results as unsatisfactory for counting queries

User's query: {state['enhanced_query']}

Executed SQL Query:
{state['sql_query']}

Results:
{results_summary}

Does this answer the user's question? Respond in JSON:
{{
  "satisfactory": true|false,
  "feedback": "If not satisfactory, explain what's wrong and how to improve the query",
  "summary": "User-friendly summary of the findings (e.g., 'There are 0 blend files in the charge show.')"
}}
"""
    
    eval_response = invoke_bedrock(eval_prompt, streaming=False, temperature=0.3, max_tokens=1024)
    
    logger.info(f"Evaluation response (first 200 chars): {eval_response[:200]}")
    
    # Parse evaluation with improved JSON extraction
    try:
        # Try to find JSON in response
        json_start = eval_response.find('{')
        json_end = eval_response.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            json_str = eval_response[json_start:json_end]
            
            # Try to parse
            try:
                evaluation = json.loads(json_str)
            except json.JSONDecodeError:
                # Try cleaning up common issues
                import re
                # Remove any trailing commas before closing braces
                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                # Try parsing again
                evaluation = json.loads(json_str)
            
            if evaluation.get('satisfactory', False):
                # Success! Generate final answer with CSV results
                summary = evaluation.get('summary', 'Results found.')
                # Make sure summary doesn't mention tools
                if 'tool' in summary.lower() or 'function' in summary.lower():
                    logger.warning("Evaluation summary mentions tools, using simple summary instead")
                    summary = f"Found {len(state['query_results'])} results."
                
                # Results are shown inline via SSE, just use summary
                state['final_answer'] = summary
            else:
                # Not satisfactory - prepare for retry or final explanation
                state['evaluation_feedback'] = evaluation.get('feedback', 'Results did not match query intent')
                
                # Update query history with feedback
                if state['sql_query_history']:
                    state['sql_query_history'][-1]['feedback'] = state['evaluation_feedback']
                    state['sql_query_history'][-1]['satisfactory'] = False
                
                if state['attempt_count'] + 1 >= state['max_attempts']:
                    # Max attempts reached - provide simple explanation with results
                    if state['query_results']:
                        state['final_answer'] = f"I found {len(state['query_results'])} results, but they may not fully answer your question. Please try rephrasing or being more specific."
                    else:
                        state['final_answer'] = "I couldn't find results matching your query. The database might not contain this information, or try rephrasing your question."
                else:
                    # Will retry
                    state['attempt_count'] += 1
                    logger.info(f"Results not satisfactory, will retry. Feedback: {state['evaluation_feedback']}")
        else:
            logger.warning("Could not find JSON in evaluation response")
            # Assume success if we have results
            if state['query_results']:
                state['final_answer'] = f"Found {len(state['query_results'])} results."
            else:
                state['final_answer'] = "No results found for your query."
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in evaluation: {e}")
        logger.error(f"Failed to parse: {json_str[:200] if 'json_str' in locals() else 'N/A'}")
        # Default to success if we have results
        if state['query_results']:
            state['final_answer'] = f"Found {len(state['query_results'])} results."
        else:
            state['final_answer'] = "No results found for your query."
    except Exception as e:
        logger.error(f"Unexpected error in evaluation: {e}", exc_info=True)
        # Fallback
        if state['query_results']:
            state['final_answer'] = f"Found {len(state['query_results'])} results."
        else:
            state['final_answer'] = "No results found for your query."
    
    logger.info(f"Result evaluation completed in {time.time() - start_time:.2f}s")
    return state


def should_retry_sql(state: ChatAgentState) -> str:
    """
    Conditional edge: Determine if we should retry SQL generation or finish.
    
    Returns:
        "retry" if should generate new SQL, "finish" if done
    """
    # If we have a final answer, we're done
    if state.get('final_answer'):
        return "finish"
    
    # If we have feedback and haven't exceeded max attempts, retry
    if state.get('evaluation_feedback') and state['attempt_count'] < state['max_attempts']:
        logger.info(f"Retrying SQL generation (attempt {state['attempt_count'] + 1}/{state['max_attempts']})")
        return "retry"
    
    # Otherwise, finish
    return "finish"


def run_chat_agent(
    query: str,
    conversation_history: List[Dict[str, str]] = None,
    uploaded_image_base64: str = None,
    max_attempts: int = MAX_ATTEMPTS
) -> Dict[str, Any]:
    """
    Run the chat agent for a user query.
    
    Args:
        query: User's query
        conversation_history: Previous conversation messages
        uploaded_image_base64: Optional uploaded image for search
        max_attempts: Maximum SQL generation attempts
        
    Returns:
        Dict with final_answer, query_results, and all SQL queries attempted
    """
    # Initialize state
    initial_state = ChatAgentState(
        messages=[HumanMessage(content=query)],
        user_query=query,
        conversation_history=conversation_history or [],
        uploaded_image_base64=uploaded_image_base64,
        enhanced_query=None,
        query_intent=None,
        text_embedding=None,
        visual_embedding=None,
        sql_query=None,
        sql_params=None,
        query_results=None,
        evaluation_feedback=None,
        attempt_count=0,
        max_attempts=max_attempts,
        final_answer=None,
        sql_query_history=[]
    )
    
    # Create and run agent
    agent = create_chat_agent()
    
    # Print ASCII graph for debugging
    print(agent.get_graph().draw_ascii())
    
    # Run agent with intermediate state tracking
    final_state = agent.invoke(initial_state)
    
    return {
        'final_answer': final_state.get('final_answer'),
        'query_results': final_state.get('query_results', []),
        'sql_query': final_state.get('sql_query'),
        'enhanced_query': final_state.get('enhanced_query'),
        'all_sql_queries': final_state.get('sql_query_history', []),  # All queries attempted
        'attempts': final_state.get('attempt_count', 0) + 1
    }
