"""
PostgreSQL database connection and query functions.
"""

import os
import logging
import time
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from src.services.s3_thumbnail_utils import get_thumbnail_url

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


def _add_thumbnail_urls(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Add presigned thumbnail URLs to search results.
    
    Args:
        results: List of database query results
        
    Returns:
        Results with thumbnail_url field added
    """
    for result in results:
        # Determine which thumbnail path to use based on file type
        thumbnail_path = None
        file_type = result.get('file_type', '')
        
        if file_type == 'blend':
            thumbnail_path = result.get('blend_thumbnail')
        elif file_type == 'image':
            thumbnail_path = result.get('image_thumbnail')
        elif file_type == 'video':
            thumbnail_path = result.get('video_thumbnail')
        
        # Generate presigned URL
        if thumbnail_path:
            result['thumbnail_url'] = get_thumbnail_url(thumbnail_path)
        else:
            result['thumbnail_url'] = None
    
    return results


def execute_generated_sql(
    sql: str,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Execute LLM-generated SQL query safely.
    
    Args:
        sql: SQL query string (must be SELECT only)
        limit: Maximum number of results (default: 100)
        
    Returns:
        List of query results with thumbnail URLs added
        
    Raises:
        ValueError: If query is not a SELECT statement
        Exception: Database errors
    """
    conn = None
    try:
        start_time = time.time()
        
        # Validate query is SELECT only
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith('SELECT') and not sql_upper.startswith('WITH'):
            raise ValueError("Only SELECT queries are allowed for security")
        
        # Check if query already has LIMIT
        if 'LIMIT' not in sql_upper:
            sql = f"{sql.rstrip(';')} LIMIT {limit}"
        
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute(sql)
        results = cursor.fetchall()
        
        metadata_list = [dict(row) for row in results]
        
        # Add thumbnail URLs
        metadata_list = _add_thumbnail_urls(metadata_list)
        
        cursor.close()
        
        logger.info(f"Generated SQL executed successfully in {time.time() - start_time:.3f}s, returned {len(metadata_list)} results")
        return metadata_list
        
    except Exception as e:
        logger.error(f"Error executing generated SQL: {str(e)}", exc_info=True)
        raise
    finally:
        if conn:
            release_connection(conn)


def close_all_connections():
    """Close all database connections (cleanup)."""
    global connection_pool
    if connection_pool:
        connection_pool.closeall()
        logger.info("All database connections closed")
