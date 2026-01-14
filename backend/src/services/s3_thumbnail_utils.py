"""
S3 utilities for thumbnail management.
Handles presigned URL generation for secure thumbnail access.
Thumbnails are organized by show: show_name/file_type/file_id_thumb.jpg
"""

import os
import logging
from typing import Optional, List, Dict
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Initialize S3 client (reused across Lambda invocations)
s3_client = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))  # AWS_REGION is auto-set by Lambda

# Configuration
BUCKET_NAME = os.environ.get('THUMBNAIL_BUCKET', 'cg-production-thumbnails')
DEFAULT_EXPIRATION = int(os.environ.get('THUMBNAIL_URL_EXPIRATION', '3600'))  # 1 hour


def get_thumbnail_url(thumbnail_path: str, expiration: int = DEFAULT_EXPIRATION) -> Optional[str]:
    """
    Generate presigned URL for thumbnail access.
    
    Args:
        thumbnail_path: S3 key for thumbnail (e.g., 'image/123_thumb.jpg' or 's3://bucket/image/123_thumb.jpg')
        expiration: URL expiration time in seconds (default: 3600 = 1 hour)
        
    Returns:
        Presigned URL string, or None if generation fails
        
    Example:
        >>> url = get_thumbnail_url('image/123_thumb.jpg')
        >>> print(url)
        'https://cg-production-thumbnails.s3.amazonaws.com/image/123_thumb.jpg?X-Amz-Algorithm=...'
    """
    if not thumbnail_path:
        return None
    
    try:
        # Remove s3:// prefix if present
        key = thumbnail_path.replace(f's3://{BUCKET_NAME}/', '')
        
        # Generate presigned URL
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': key
            },
            ExpiresIn=expiration
        )
        
        return url
        
    except ClientError as e:
        logger.error(f"Error generating presigned URL for {thumbnail_path}: {str(e)}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error generating presigned URL: {str(e)}", exc_info=True)
        return None


def batch_get_thumbnail_urls(thumbnail_paths: List[str], expiration: int = DEFAULT_EXPIRATION) -> Dict[str, Optional[str]]:
    """
    Generate presigned URLs for multiple thumbnails efficiently.
    
    Args:
        thumbnail_paths: List of S3 keys for thumbnails
        expiration: URL expiration time in seconds
        
    Returns:
        Dictionary mapping thumbnail_path -> presigned_url
        
    Example:
        >>> paths = ['image/123_thumb.jpg', 'video/456_thumb.jpg']
        >>> urls = batch_get_thumbnail_urls(paths)
        >>> print(urls['image/123_thumb.jpg'])
        'https://...'
    """
    result = {}
    
    for path in thumbnail_paths:
        result[path] = get_thumbnail_url(path, expiration)
    
    return result


def get_thumbnail_path(file_id: int, file_type: str, show: str = 'other') -> str:
    """
    Construct S3 key for thumbnail based on file ID, type, and show.
    
    Args:
        file_id: Database file ID
        file_type: File type ('image', 'video', 'blend')
        show: Show name (defaults to 'other' for files not in a specific show)
        
    Returns:
        S3 key for thumbnail following show-based structure
        
    Example:
        >>> path = get_thumbnail_path(123, 'image', 'show1')
        >>> print(path)
        'show1/image/123_thumb.jpg'
        
        >>> path = get_thumbnail_path(456, 'blend', 'other')
        >>> print(path)
        'other/blend/456_thumb.jpg'
    """
    # Map file types to S3 folders
    folder_map = {
        'image': 'images',
        'video': 'videos',
        'blend': 'blend'
    }
    
    folder = folder_map.get(file_type, 'images')
    return f"{show}/{folder}/{file_id}_thumb.jpg"



def check_thumbnail_exists(thumbnail_path: str) -> bool:
    """
    Check if thumbnail exists in S3.
    
    Args:
        thumbnail_path: S3 key for thumbnail
        
    Returns:
        True if thumbnail exists, False otherwise
    """
    try:
        key = thumbnail_path.replace(f's3://{BUCKET_NAME}/', '')
        
        s3_client.head_object(Bucket=BUCKET_NAME, Key=key)
        return True
        
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        logger.error(f"Error checking thumbnail existence: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking thumbnail: {str(e)}")
        return False
