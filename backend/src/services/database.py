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
import sqlglot
from sqlglot import exp

from src.services.s3_thumbnail_utils import get_thumbnail_url, get_file_download_url
from src.services.search_filters import apply_search_filters

logger = logging.getLogger()

# Connection pool (reused across Lambda invocations)
connection_pool: Optional[pool.SimpleConnectionPool] = None

# Separate, privilege-restricted pool used only to run LLM-generated SQL.
# Must point at a DB role that only has SELECT granted.
# See backend/docs for how DB_READONLY_USER/DB_READONLY_PASSWORD are provisioned.
readonly_connection_pool: Optional[pool.SimpleConnectionPool] = None

# Shows and file types offered as search filters change only when the metadata extractor
# runs, so the grouped count is cached per container instead of queried per page load.
FILTER_OPTIONS_TTL_SECONDS = 600
_filter_options_cache: Optional[Dict[str, Any]] = None
_filter_options_loaded_at = 0.0

# AST node types that must never appear in LLM-generated SQL, even nested
# inside a CTE (e.g. `WITH x AS (DELETE FROM files RETURNING *) SELECT * FROM x`).
_FORBIDDEN_SQL_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter,
    exp.Create, exp.TruncateTable, exp.Command, exp.Grant,
)


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


def init_readonly_db_connection():
    """Initialize the read-only PostgreSQL connection pool used for LLM-generated SQL."""
    global readonly_connection_pool

    if readonly_connection_pool is None:
        try:
            readonly_connection_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=5,
                host=os.environ.get('DB_HOST'),
                database=os.environ.get('DB_NAME'),
                user=os.environ.get('DB_READONLY_USER'),
                password=os.environ.get('DB_READONLY_PASSWORD'),
                port=os.environ.get('DB_PORT', '5432')
            )
            logger.info("Read-only database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize read-only database pool: {str(e)}", exc_info=True)
            raise


def get_readonly_connection():
    """Get a connection from the read-only pool."""
    if readonly_connection_pool is None:
        init_readonly_db_connection()
    return readonly_connection_pool.getconn()


def release_readonly_connection(conn):
    """Release a connection back to the read-only pool."""
    if readonly_connection_pool:
        readonly_connection_pool.putconn(conn)


def validate_select_only_sql(sql: str) -> str:
    """
    Validate that a SQL string is exactly one read-only SELECT statement.

    This is a real parse-tree check, not a prefix match: it rejects
    statement-stacking (`SELECT 1; DROP TABLE files;--`) and DML hidden
    inside a CTE (`WITH x AS (DELETE FROM files RETURNING *) SELECT * FROM x`),
    both of which pass a naive `sql.upper().startswith('SELECT')` check.

    Args:
        sql: SQL query string produced by the LLM

    Returns:
        The validated SQL string (unchanged)

    Raises:
        ValueError: If the query is not a single read-only SELECT statement
    """
    try:
        statements = [s for s in sqlglot.parse(sql, dialect='postgres') if s is not None]
    except Exception as e:
        raise ValueError(f"Could not parse generated SQL: {e}")

    if len(statements) != 1:
        raise ValueError("Only a single SELECT statement is allowed")

    statement = statements[0]
    if not isinstance(statement, exp.Select):
        raise ValueError("Only SELECT queries are allowed for security")

    for node in statement.walk():
        if isinstance(node, _FORBIDDEN_SQL_NODES):
            raise ValueError(
                f"Generated SQL contains a disallowed operation: {type(node).__name__}"
            )

    return sql


def _add_thumbnail_urls(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Add presigned thumbnail URLs and download URLs to search results.
    
    Args:
        results: List of database query results
        
    Returns:
        Results with thumbnail_url and download_url fields added
    """
    for result in results:
        # The column is 'thumbnail_path' from whichever child table was joined
        # (blend_files.thumbnail_path, images.thumbnail_path, or videos.thumbnail_path)
        thumbnail_path = result.get('thumbnail_path')
        
        # Generate presigned URL if thumbnail path exists
        if thumbnail_path:
            result['thumbnail_url'] = get_thumbnail_url(thumbnail_path)
        else:
            result['thumbnail_url'] = None
        
        # Generate download URL for source files (especially .blend files)
        file_path = result.get('file_path')
        file_type = result.get('file_type')
        file_name = result.get('file_name', '')
        
        # Generate download URL for .blend files and other downloadable types
        if file_path and (file_type == 'blend' or file_name.endswith('.blend')):
            result['download_url'] = get_file_download_url(file_path)
        else:
            result['download_url'] = None
    
    return results


def get_filter_options() -> Dict[str, List[Dict[str, Any]]]:
    """
    List the shows and file types a search can be restricted to, with file counts.

    Returns:
        {"shows": [{"name", "file_count"}], "file_types": [{"name", "file_count"}]},
        each sorted by name. Cached for FILTER_OPTIONS_TTL_SECONDS.
    """
    global _filter_options_cache, _filter_options_loaded_at

    if _filter_options_cache is not None and time.time() - _filter_options_loaded_at < FILTER_OPTIONS_TTL_SECONDS:
        return _filter_options_cache

    conn = None
    try:
        conn = get_readonly_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT show, file_type, COUNT(*) FROM files "
            "WHERE show IS NOT NULL AND file_type IS NOT NULL GROUP BY show, file_type"
        )
        rows = cursor.fetchall()
        cursor.close()
        # Read-only work still opens a transaction; end it before the connection is pooled.
        conn.rollback()
    finally:
        if conn:
            release_readonly_connection(conn)

    shows: Dict[str, int] = {}
    file_types: Dict[str, int] = {}
    for show, file_type, count in rows:
        shows[show] = shows.get(show, 0) + count
        file_types[file_type] = file_types.get(file_type, 0) + count

    _filter_options_cache = {
        "shows": [{"name": name, "file_count": shows[name]} for name in sorted(shows)],
        "file_types": [{"name": name, "file_count": file_types[name]} for name in sorted(file_types)],
    }
    _filter_options_loaded_at = time.time()
    return _filter_options_cache


def execute_generated_sql(
    sql: str,
    limit: int = 100,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Execute LLM-generated SQL query safely.

    Validated with a real SQL parser (not a prefix match) and run under a
    dedicated read-only DB role, so even a successful prompt-injection that
    gets a destructive statement past the parse check still can't write.

    Args:
        sql: SQL query string (must be a single SELECT statement)
        limit: Maximum number of results (default: 100)
        filters: Optional {"shows": [...], "file_types": [...]} restriction. Enforced by
            prefixing the query with filtering CTEs (see
            search_filters.apply_search_filters), so it holds regardless of what the
            LLM wrote.

    Returns:
        List of query results with thumbnail URLs added

    Raises:
        ValueError: If query is not a single read-only SELECT statement
        Exception: Database errors
    """
    conn = None
    try:
        start_time = time.time()

        sql = validate_select_only_sql(sql)
        sql = apply_search_filters(sql, filters)

        # Check if query already has LIMIT
        if 'LIMIT' not in sql.upper():
            sql = f"{sql.rstrip(';')} LIMIT {limit}"

        conn = get_readonly_connection()
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
            release_readonly_connection(conn)
