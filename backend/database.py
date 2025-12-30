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


def get_database_stats() -> Dict[str, Any]:
    """
    Get database statistics including total counts.
    Useful for queries like "how many files are in the database".
    
    Returns:
        Dictionary with database statistics
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Get total file count
        cursor.execute("SELECT COUNT(*) FROM files")
        total_files = cursor.fetchone()[0]
        
        # Get counts by file type
        cursor.execute("""
            SELECT file_type, COUNT(*) 
            FROM files 
            GROUP BY file_type 
            ORDER BY COUNT(*) DESC
        """)
        files_by_type = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get counts for specific tables
        cursor.execute("SELECT COUNT(*) FROM images")
        total_images = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM videos")
        total_videos = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM blend_files")
        total_blend_files = cursor.fetchone()[0]
        
        cursor.close()
        
        return {
            'total_files': total_files,
            'total_images': total_images,
            'total_videos': total_videos,
            'total_blend_files': total_blend_files,
            'files_by_type': files_by_type
        }
    except Exception as e:
        logger.error(f"Error getting database stats: {str(e)}", exc_info=True)
        return {}
    finally:
        release_connection(conn)


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
    Uses all-MiniLM-L6-v2 embeddings (384 dimensions) on metadata_embedding column.
    
    Args:
        query_embedding: 384-dimensional text embedding
        limit: Maximum number of results
        
    Returns:
        List of similar file metadata with type-specific details
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # pgvector cosine distance search on files table
        # Joins with type-specific tables to get additional metadata
        sql = """
            SELECT 
                f.id,
                f.file_name,
                f.file_path,
                f.file_type,
                f.extension,
                f.file_size,
                f.created_date,
                f.modified_date,
                f.metadata_json,
                -- Blend file specific fields
                bf.render_engine,
                bf.resolution_x,
                bf.resolution_y,
                bf.num_frames,
                bf.fps,
                bf.total_objects,
                bf.thumbnail_path as blend_thumbnail,
                -- Image specific fields
                img.width as image_width,
                img.height as image_height,
                img.mode as image_mode,
                img.thumbnail_path as image_thumbnail,
                -- Video specific fields
                vid.width as video_width,
                vid.height as video_height,
                vid.duration,
                vid.fps as video_fps,
                vid.codec,
                vid.thumbnail_path as video_thumbnail,
                -- Similarity score
                1 - (f.metadata_embedding <=> %s::vector) AS similarity
            FROM files f
            LEFT JOIN blend_files bf ON f.id = bf.file_id
            LEFT JOIN images img ON f.id = img.file_id
            LEFT JOIN videos vid ON f.id = vid.file_id
            WHERE f.metadata_embedding IS NOT NULL
            ORDER BY f.metadata_embedding <=> %s::vector
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
    Converts text query to CLIP embedding and searches visual_embedding (512 dimensions).
    Searches across images, videos, and blend_files tables.
    
    Args:
        query_text: Text description to search for in images
        limit: Maximum number of results
        
    Returns:
        List of files with similar visual content
    """
    conn = None
    try:
        from embeddings import generate_image_embedding_from_text
        
        # Generate CLIP embedding from text
        query_embedding = generate_image_embedding_from_text(query_text)
        embedding_str = f"[{','.join(map(str, query_embedding))}]"
        
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Search across all tables with visual embeddings using UNION
        sql = """
            (
                SELECT 
                    f.id,
                    f.file_name,
                    f.file_path,
                    f.file_type,
                    f.file_size,
                    f.created_date,
                    f.modified_date,
                    img.width,
                    img.height,
                    img.thumbnail_path,
                    1 - (img.visual_embedding <=> %s::vector) AS similarity
                FROM files f
                JOIN images img ON f.id = img.file_id
                WHERE img.visual_embedding IS NOT NULL
            )
            UNION ALL
            (
                SELECT 
                    f.id,
                    f.file_name,
                    f.file_path,
                    f.file_type,
                    f.file_size,
                    f.created_date,
                    f.modified_date,
                    vid.width,
                    vid.height,
                    vid.thumbnail_path,
                    1 - (vid.visual_embedding <=> %s::vector) AS similarity
                FROM files f
                JOIN videos vid ON f.id = vid.file_id
                WHERE vid.visual_embedding IS NOT NULL
            )
            UNION ALL
            (
                SELECT 
                    f.id,
                    f.file_name,
                    f.file_path,
                    f.file_type,
                    f.file_size,
                    f.created_date,
                    f.modified_date,
                    bf.resolution_x as width,
                    bf.resolution_y as height,
                    bf.thumbnail_path,
                    1 - (bf.visual_embedding <=> %s::vector) AS similarity
                FROM files f
                JOIN blend_files bf ON f.id = bf.file_id
                WHERE bf.visual_embedding IS NOT NULL
            )
            ORDER BY similarity DESC
            LIMIT %s
        """
        
        cursor.execute(sql, (embedding_str, embedding_str, embedding_str, limit))
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
    Searches file_name, file_path, and metadata_json fields.
    
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
        
        # Build SQL query with keyword matching on files table
        sql = """
            SELECT 
                f.id,
                f.file_name,
                f.file_path,
                f.file_type,
                f.extension,
                f.file_size,
                f.created_date,
                f.modified_date,
                f.metadata_json,
                bf.render_engine,
                bf.resolution_x,
                bf.resolution_y,
                bf.num_frames,
                bf.thumbnail_path as blend_thumbnail,
                img.thumbnail_path as image_thumbnail,
                vid.thumbnail_path as video_thumbnail
            FROM files f
            LEFT JOIN blend_files bf ON f.id = bf.file_id
            LEFT JOIN images img ON f.id = img.file_id
            LEFT JOIN videos vid ON f.id = vid.file_id
            WHERE 
                f.file_name ILIKE ANY(%s)
                OR f.file_path ILIKE ANY(%s)
                OR f.metadata_json::text ILIKE ANY(%s)
            ORDER BY f.modified_date DESC
            LIMIT %s
        """
        
        # Create ILIKE patterns for each keyword
        patterns = [f"%{kw}%" for kw in keywords]
        
        cursor.execute(sql, (patterns, patterns, patterns, limit))
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
