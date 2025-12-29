"""
PostgreSQL database connection and query functions.
"""

import os
import logging
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger()

# Connection pool (reused across Lambda invocations)
connection_pool: Optional[pool.SimpleConnectionPool] = None


def init_db_connection():
    """Initialize PostgreSQL connection pool."""
    global connection_pool
    
    if connection_pool is None:
        try:
            connection_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=5,
                host=os.environ.get('DB_HOST'),
                database=os.environ.get('DB_NAME'),
                user=os.environ.get('DB_USER'),
                password=os.environ.get('DB_PASSWORD'),
                port=os.environ.get('DB_PORT', '5432')
            )
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {str(e)}", exc_info=True)
            raise


def get_connection():
    """Get a connection from the pool."""
    if connection_pool is None:
        init_db_connection()
    return connection_pool.getconn()


def release_connection(conn):
    """Release connection back to the pool."""
    if connection_pool:
        connection_pool.putconn(conn)



def get_relevant_metadata(query: str, limit: int = 10, use_semantic: bool = True) -> List[Dict[str, Any]]:
    """
    Retrieve relevant metadata from PostgreSQL based on user query.
    Uses hybrid search: semantic (vector) + keyword matching.
    
    Args:
        query: User's search query
        limit: Maximum number of results to return
        use_semantic: Whether to use semantic search (default: True)
        
    Returns:
        List of metadata dictionaries
    """
    if use_semantic:
        try:
            # Try semantic search first
            from embeddings import generate_text_embedding
            query_embedding = generate_text_embedding(query)
            results = search_by_text_embedding(query_embedding, limit)
            
            if results:
                logger.info(f"Semantic search returned {len(results)} results")
                return results
            else:
                logger.info("Semantic search returned no results, falling back to keyword search")
        except Exception as e:
            logger.warning(f"Semantic search failed, falling back to keyword search: {str(e)}")
    
    # Fallback to keyword search
    return keyword_search(query, limit)


def search_by_text_embedding(query_embedding: List[float], limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search using text embedding similarity (pgvector).
    Uses all-MiniLM-L6-v2 embeddings (384 dimensions).
    
    Args:
        query_embedding: 384-dimensional text embedding
        limit: Maximum number of results
        
    Returns:
        List of similar file metadata
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # pgvector cosine distance search
        # Assumes table has 'text_embedding' column with vector(384)
        sql = """
            SELECT 
                file_name,
                file_path,
                resolution,
                color_space,
                project_name,
                tags,
                created_date,
                modified_date,
                file_size,
                frame_count,
                render_engine,
                1 - (text_embedding <=> %s::vector) AS similarity
            FROM media_metadata
            WHERE text_embedding IS NOT NULL
            ORDER BY text_embedding <=> %s::vector
            LIMIT %s
        """
        
        # Convert embedding to PostgreSQL vector format
        embedding_str = f"[{','.join(map(str, query_embedding))}]"
        
        cursor.execute(sql, (embedding_str, embedding_str, limit))
        results = cursor.fetchall()
        
        metadata_list = [dict(row) for row in results]
        cursor.close()
        
        logger.info(f"Text embedding search returned {len(metadata_list)} results")
        return metadata_list
        
    except Exception as e:
        logger.error(f"Text embedding search error: {str(e)}", exc_info=True)
        return []
    finally:
        if conn:
            release_connection(conn)


def search_by_image_embedding(query_text: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search images using CLIP text-to-image cross-modal search.
    Converts text query to CLIP embedding and searches image embeddings.
    Uses clip-vit-base-patch32 (512 dimensions).
    
    Args:
        query_text: Text description to search for in images
        limit: Maximum number of results
        
    Returns:
        List of files with similar image content
    """
    conn = None
    try:
        from embeddings import generate_image_embedding_from_text
        
        # Generate CLIP embedding from text
        query_embedding = generate_image_embedding_from_text(query_text)
        
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Search using CLIP image embeddings
        # Assumes table has 'image_embedding' column with vector(512)
        sql = """
            SELECT 
                file_name,
                file_path,
                resolution,
                color_space,
                project_name,
                tags,
                created_date,
                modified_date,
                thumbnail_path,
                1 - (image_embedding <=> %s::vector) AS similarity
            FROM media_metadata
            WHERE image_embedding IS NOT NULL
            ORDER BY image_embedding <=> %s::vector
            LIMIT %s
        """
        
        embedding_str = f"[{','.join(map(str, query_embedding))}]"
        
        cursor.execute(sql, (embedding_str, embedding_str, limit))
        results = cursor.fetchall()
        
        metadata_list = [dict(row) for row in results]
        cursor.close()
        
        logger.info(f"Image embedding search returned {len(metadata_list)} results")
        return metadata_list
        
    except Exception as e:
        logger.error(f"Image embedding search error: {str(e)}", exc_info=True)
        return []
    finally:
        if conn:
            release_connection(conn)


def keyword_search(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Traditional keyword-based search (fallback).
    
    Args:
        query: User's search query
        limit: Maximum number of results
        
    Returns:
        List of metadata dictionaries
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Extract search keywords from query
        keywords = extract_keywords(query)
        
        # Build SQL query with keyword matching
        sql = """
            SELECT 
                file_name,
                file_path,
                resolution,
                color_space,
                project_name,
                tags,
                created_date,
                modified_date,
                file_size,
                frame_count,
                render_engine
            FROM media_metadata
            WHERE 
                file_name ILIKE ANY(%s)
                OR project_name ILIKE ANY(%s)
                OR tags ILIKE ANY(%s)
                OR color_space ILIKE ANY(%s)
            ORDER BY modified_date DESC
            LIMIT %s
        """
        
        # Create ILIKE patterns for each keyword
        patterns = [f"%{kw}%" for kw in keywords]
        
        cursor.execute(sql, (patterns, patterns, patterns, patterns, limit))
        results = cursor.fetchall()
        
        # Convert to list of dicts
        metadata_list = [dict(row) for row in results]
        
        cursor.close()
        
        logger.info(f"Keyword search returned {len(metadata_list)} results for query: {query}")
        return metadata_list
        
    except Exception as e:
        logger.error(f"Keyword search error: {str(e)}", exc_info=True)
        return []
    finally:
        if conn:
            release_connection(conn)




def extract_keywords(query: str) -> List[str]:
    """
    Extract search keywords from user query.
    
    Args:
        query: User's query string
        
    Returns:
        List of keywords
    """
    # Simple keyword extraction (can be enhanced with NLP)
    stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                 'show', 'me', 'find', 'get', 'list', 'what', 'where', 'when', 'how'}
    
    words = query.lower().split()
    keywords = [w.strip('.,!?') for w in words if w.lower() not in stopwords and len(w) > 2]
    
    # If no keywords found, use the whole query
    if not keywords:
        keywords = [query]
    
    return keywords


def close_all_connections():
    """Close all database connections (cleanup)."""
    global connection_pool
    if connection_pool:
        connection_pool.closeall()
        logger.info("All database connections closed")
