"""
LangGraph tool definitions for the ReAct agent.
Wraps database and utility functions as LangGraph tools.
"""

import logging
import time
from typing import List, Dict, Any
from langchain.tools import tool
from psycopg2.extras import RealDictCursor

from src.services.database import (
    search_by_text_embedding,
    search_by_image_embedding,
    get_database_stats,
    get_connection,
    release_connection
)
from src.services.embeddings import generate_text_embedding, generate_image_embedding_from_base64

logger = logging.getLogger()


@tool
def search_by_metadata_embedding(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search files using semantic text embedding similarity.
    
    Use this tool when the user asks to find files based on descriptions, keywords, or concepts.
    This performs semantic search on file metadata (names, paths, descriptions).
    
    Args:
        query: Text description to search for (e.g., "character models", "lighting setups")
        limit: Maximum number of results to return (default: 10)
        
    Returns:
        List of matching files with metadata and thumbnail URLs
        
    Example queries:
        - "Find character models"
        - "Show me lighting setups"
        - "Files related to autumn scenes"
    """
    try:
        start_time = time.time()
        
        # Generate embedding from query
        embed_start = time.time()
        query_embedding = generate_text_embedding(query)
        logger.info(f"Text embedding generated in {time.time() - embed_start:.2f}s")
        
        # Search database
        db_start = time.time()
        results = search_by_text_embedding(query_embedding, limit)
        logger.info(f"Database search completed in {time.time() - db_start:.2f}s")
        
        logger.info(f"search_by_metadata_embedding returned {len(results)} results in {time.time() - start_time:.2f}s for: {query}")
        return results
        
    except Exception as e:
        logger.error(f"Error in search_by_metadata_embedding: {str(e)}", exc_info=True)
        return []


@tool
def search_by_visual_embedding(description: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search images/videos using CLIP visual similarity from text description.
    
    Use this tool when the user asks to find images or videos based on visual content descriptions.
    This performs cross-modal search (text query -> visual results).
    
    Args:
        description: Visual description to search for (e.g., "red car", "sunset scene")
        limit: Maximum number of results to return (default: 10)
        
    Returns:
        List of visually similar images/videos with thumbnail URLs
        
    Example queries:
        - "Find images of red cars"
        - "Show me sunset scenes"
        - "Videos with characters running"
    """
    try:
        start_time = time.time()
        results = search_by_image_embedding(description, limit)
        
        logger.info(f"search_by_visual_embedding returned {len(results)} results in {time.time() - start_time:.2f}s for: {description}")
        return results
        
    except Exception as e:
        logger.error(f"Error in search_by_visual_embedding: {str(e)}", exc_info=True)
        return []


@tool
def search_by_uploaded_image(image_base64: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search for visually similar images using an uploaded image.
    
    Use this tool when the user uploads an image to find similar images in the database.
    The image should already be base64-encoded (done client-side).
    
    Args:
        image_base64: Base64-encoded JPEG image (512x512, resized client-side)
        limit: Maximum number of results to return (default: 10)
        
    Returns:
        List of visually similar files with thumbnail URLs
        
    Example usage:
        User uploads an image of a car -> find similar car images in database
    """
    try:
        from src.services.database import search_by_text_embedding  # We'll create a vector-based search
        
        # Generate CLIP embedding from uploaded image
        query_embedding = generate_image_embedding_from_base64(image_base64)
        
        # Search using visual embeddings
        # Note: This requires a new function in database.py that searches visual_embedding column
        conn = None
        try:
            from src.services.database import get_connection, release_connection, _add_thumbnail_urls
            from psycopg2.extras import RealDictCursor
            
            conn = get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            embedding_str = f"[{','.join(map(str, query_embedding))}]"
            
            # Search across images, videos, and blend files
            sql = """
                (
                    SELECT 
                        f.id, f.file_name, f.file_path, f.file_type,
                        img.width, img.height, img.thumbnail_path,
                        1 - (img.visual_embedding <=> %s::vector) AS similarity
                    FROM files f
                    JOIN images img ON f.id = img.file_id
                    WHERE img.visual_embedding IS NOT NULL
                )
                UNION ALL
                (
                    SELECT 
                        f.id, f.file_name, f.file_path, f.file_type,
                        vid.width, vid.height, vid.thumbnail_path,
                        1 - (vid.visual_embedding <=> %s::vector) AS similarity
                    FROM files f
                    JOIN videos vid ON f.id = vid.file_id
                    WHERE vid.visual_embedding IS NOT NULL
                )
                UNION ALL
                (
                    SELECT 
                        f.id, f.file_name, f.file_path, f.file_type,
                        bf.resolution_x as width, bf.resolution_y as height, bf.thumbnail_path,
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
            metadata_list = _add_thumbnail_urls(metadata_list)
            
            cursor.close()
            
            logger.info(f"search_by_uploaded_image returned {len(metadata_list)} results")
            return metadata_list
            
        finally:
            if conn:
                release_connection(conn)
        
    except Exception as e:
        logger.error(f"Error in search_by_uploaded_image: {str(e)}", exc_info=True)
        return []





@tool
def analytics_query() -> Dict[str, Any]:
    """Get database statistics and counts.
    
    Use this tool when the user asks about totals, counts, or statistics.
    Returns information about total files, images, videos, and breakdowns by type.
    
    Returns:
        Dictionary with database statistics
        
    Example queries:
        - "How many files are in the database?"
        - "Show me statistics"
        - "What types of files do we have?"
    """
    try:
        stats = get_database_stats()
        
        logger.info(f"analytics_query returned stats: {stats.get('total_files', 0)} total files")
        return stats
        
    except Exception as e:
        logger.error(f"Error in analytics_query: {str(e)}", exc_info=True)
        return {}


@tool
def filter_by_metadata(
    file_type: str = None,
    min_resolution_x: int = None,
    min_resolution_y: int = None,
    extension: str = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Filter files by specific metadata criteria.
    
    Use this tool when the user asks to filter by specific attributes like resolution, file type, or extension.
    
    Args:
        file_type: Filter by file type ('image', 'video', 'blend')
        min_resolution_x: Minimum width in pixels
        min_resolution_y: Minimum height in pixels
        extension: File extension (e.g., '.blend', '.png')
        limit: Maximum number of results (default: 10)
        
    Returns:
        List of files matching the criteria with thumbnail URLs
        
    Example queries:
        - "Show me 4K renders" (min_resolution_x=3840, min_resolution_y=2160)
        - "Find all blend files"
        - "Show me PNG images"
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Build dynamic SQL query
        conditions = []
        params = []
        
        if file_type:
            conditions.append("f.file_type = %s")
            params.append(file_type)
        
        if extension:
            conditions.append("f.extension = %s")
            params.append(extension)
        
        # Resolution filtering depends on file type
        resolution_conditions = []
        if min_resolution_x and min_resolution_y:
            resolution_conditions.append(f"(img.width >= %s AND img.height >= %s)")
            resolution_conditions.append(f"(vid.width >= %s AND vid.height >= %s)")
            resolution_conditions.append(f"(bf.resolution_x >= %s AND bf.resolution_y >= %s)")
            params.extend([min_resolution_x, min_resolution_y] * 3)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        if resolution_conditions:
            where_clause += f" AND ({' OR '.join(resolution_conditions)})"
        
        sql = f"""
            SELECT 
                f.id, f.file_name, f.file_path, f.file_type, f.extension,
                f.file_size, f.created_date, f.modified_date,
                bf.resolution_x, bf.resolution_y, bf.render_engine, bf.thumbnail_path as blend_thumbnail,
                img.width as image_width, img.height as image_height, img.thumbnail_path as image_thumbnail,
                vid.width as video_width, vid.height as video_height, vid.thumbnail_path as video_thumbnail
            FROM files f
            LEFT JOIN blend_files bf ON f.id = bf.file_id
            LEFT JOIN images img ON f.id = img.file_id
            LEFT JOIN videos vid ON f.id = vid.file_id
            WHERE {where_clause}
            ORDER BY f.modified_date DESC
            LIMIT %s
        """
        
        params.append(limit)
        cursor.execute(sql, params)
        results = cursor.fetchall()
        
        from src.services.database import _add_thumbnail_urls
        metadata_list = [dict(row) for row in results]
        metadata_list = _add_thumbnail_urls(metadata_list)
        
        cursor.close()
        release_connection(conn)
        
        logger.info(f"filter_by_metadata returned {len(metadata_list)} results")
        return metadata_list
        
    except Exception as e:
        logger.error(f"Error in filter_by_metadata: {str(e)}", exc_info=True)
        return []


@tool
def get_file_details(file_id: int) -> Dict[str, Any]:
    """Get detailed information about a specific file by ID.
    
    Use this tool when the user asks for details about a specific file.
    
    Args:
        file_id: Database ID of the file
        
    Returns:
        Detailed file metadata with thumbnail URL
        
    Example queries:
        - "Tell me more about file 123"
        - "What are the details of that file?"
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        sql = """
            SELECT 
                f.*, 
                bf.*, img.*, vid.*
            FROM files f
            LEFT JOIN blend_files bf ON f.id = bf.file_id
            LEFT JOIN images img ON f.id = img.file_id
            LEFT JOIN videos vid ON f.id = vid.file_id
            WHERE f.id = %s
        """
        
        cursor.execute(sql, (file_id,))
        result = cursor.fetchone()
        
        if result:
            from src.services.database import _add_thumbnail_urls
            file_data = dict(result)
            _add_thumbnail_urls([file_data])
            cursor.close()
            release_connection(conn)
            return file_data
        else:
            cursor.close()
            release_connection(conn)
            return {"error": f"File with ID {file_id} not found"}
        
    except Exception as e:
        logger.error(f"Error in get_file_details: {str(e)}", exc_info=True)
        return {"error": str(e)}


# List of all available tools for the agent
AVAILABLE_TOOLS = [
    search_by_metadata_embedding,
    search_by_visual_embedding,
    search_by_uploaded_image,
    analytics_query,
    filter_by_metadata,
    get_file_details
]
