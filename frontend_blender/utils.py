"""
Utility functions for CG Production Assistant addon.
Includes SSE parsing, image handling, and helper functions.
"""

import json
import base64
import os
import tempfile
from typing import Generator, Tuple, List, Dict, Any, Optional


def parse_sse_line(line: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Parse a single SSE line.
    
    Args:
        line: Raw SSE line
        
    Returns:
        Tuple of (event_type, data_dict) or (None, None) if not a data line
    """
    line = line.strip()
    if not line:
        return None, None
    
    if line.startswith('event:'):
        return line.split(':', 1)[1].strip(), None
    elif line.startswith('data:'):
        try:
            data = json.loads(line.split(':', 1)[1].strip())
            return None, data
        except json.JSONDecodeError:
            return None, None
    
    return None, None


def process_sse_events(lines: List[str]) -> Generator[Dict[str, Any], None, None]:
    """
    Process SSE event lines and yield parsed events.
    
    Args:
        lines: List of SSE lines
        
    Yields:
        Dict with 'event' and 'data' keys
    """
    current_event = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if line.startswith('event:'):
            current_event = line.split(':', 1)[1].strip()
        elif line.startswith('data:'):
            try:
                data = json.loads(line.split(':', 1)[1].strip())
                yield {
                    'event': current_event,
                    'data': data
                }
            except json.JSONDecodeError:
                continue


def format_chat_response(events: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]], Optional[str]]:
    """
    Format SSE events into a chat response.
    
    Args:
        events: List of parsed SSE events
        
    Returns:
        Tuple of (formatted_text, blend_files, conversation_id)
    """
    text_parts = []
    blend_files = []
    conversation_id = None
    
    for event in events:
        event_type = event.get('event')
        data = event.get('data', {})
        
        if event_type == 'enhanced_query':
            enhanced = data.get('query', '')
            text_parts.append(f"\n[Enhanced Query]: {enhanced}\n")
        
        elif event_type == 'sql_query':
            sql = data.get('query', '')
            attempt = data.get('attempt', 1)
            if attempt > 1:
                text_parts.append(f"\n[SQL Query (Attempt {attempt})]:\n{sql}\n")
            else:
                text_parts.append(f"\n[SQL Query]:\n{sql}\n")
        
        elif event_type == 'query_results':
            count = data.get('count', 0)
            results = data.get('results', [])
            text_parts.append(f"\nFound {count} results\n")
            
            # Extract blend files from results
            for result in results:
                if result.get('file_type') == 'blend' or (
                    result.get('file_name', '').endswith('.blend')
                ):
                    blend_files.append({
                        'name': result.get('file_name', 'unknown.blend'),
                        'file_path': result.get('file_path', ''),
                        'download_url': result.get('download_url', ''),
                        'thumbnail_url': result.get('thumbnail_url', ''),
                    })
        
        elif event_type == 'thumbnail':
            file_name = data.get('file_name', 'thumbnail')
            text_parts.append(f"\n[Thumbnail: {file_name}]\n")
        
        elif event_type == 'answer_start':
            text_parts.append("\n--- Answer ---\n")
        
        elif event_type == 'answer_chunk':
            text = data.get('text', '')
            text_parts.append(text)
        
        elif event_type == 'done':
            conversation_id = data.get('conversation_id')
    
    return ''.join(text_parts), blend_files, conversation_id


def image_to_base64(image_path: str, max_size: int = 512) -> Optional[str]:
    """
    Load an image, resize it, and convert to base64.
    
    Args:
        image_path: Path to the image file
        max_size: Maximum dimension (width or height)
        
    Returns:
        Base64-encoded JPEG string, or None on error
    """
    try:
        # Try to use PIL if available (bundled with Blender)
        try:
            from PIL import Image
            from io import BytesIO
            
            img = Image.open(image_path)
            
            # Resize while maintaining aspect ratio
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Convert to RGB if necessary (e.g., RGBA, P mode)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save to buffer
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            image_bytes = buffer.getvalue()
            
            return base64.b64encode(image_bytes).decode('utf-8')
            
        except ImportError:
            # Fallback: read raw file and encode (no resize)
            with open(image_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
    
    except Exception as e:
        print(f"Error converting image to base64: {e}")
        return None


def get_temp_image_path(prefix: str = "cg_assistant") -> str:
    """
    Get a temporary file path for saving images.
    
    Args:
        prefix: Prefix for the temp file
        
    Returns:
        Path to temp file
    """
    temp_dir = tempfile.gettempdir()
    return os.path.join(temp_dir, f"{prefix}_capture.png")


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncate text to a maximum length with ellipsis.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def wrap_text(text: str, width: int = 50) -> List[str]:
    """
    Wrap text to a specified width.
    
    Args:
        text: Text to wrap
        width: Maximum line width
        
    Returns:
        List of wrapped lines
    """
    words = text.split()
    lines = []
    current_line = []
    current_length = 0
    
    for word in words:
        if current_length + len(word) + 1 <= width:
            current_line.append(word)
            current_length += len(word) + 1
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
            current_length = len(word)
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines if lines else ['']


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
