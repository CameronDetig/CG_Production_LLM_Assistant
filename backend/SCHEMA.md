# Database Schema Reference

## Table Structure

Your PostgreSQL database uses a normalized schema with a main `files` table and type-specific tables for different file types.

### Main Table: `files`

Stores core metadata for all files:

```python
- id (Integer, Primary Key)
- file_name (String, indexed)
- file_path (String, unique, indexed)
- file_type (String, indexed)  # 'blend', 'image', 'video', 'text', 'unknown'
- extension (String)
- file_size (Integer)  # bytes
- created_date (DateTime)
- modified_date (DateTime)
- scan_date (DateTime)
- metadata_json (JSON)  # Additional metadata
- error (Text)
- metadata_embedding (Vector(384))  # all-MiniLM-L6-v2 embeddings
```

### Type-Specific Tables

#### `images` table
```python
- id (Integer, Primary Key)
- file_id (Integer, Foreign Key → files.id)
- width (Integer)
- height (Integer)
- mode (String)  # e.g., 'RGB', 'RGBA'
- thumbnail_path (String)  # 512x512 JPG
- visual_embedding (Vector(512))  # CLIP embeddings
```

#### `videos` table
```python
- id (Integer, Primary Key)
- file_id (Integer, Foreign Key → files.id)
- width (Integer)
- height (Integer)
- duration (Float)  # seconds
- fps (Float)
- codec (String)
- bit_rate (Integer)
- thumbnail_path (String)  # 512x512 JPG
- visual_embedding (Vector(512))  # CLIP embeddings
```

#### `blend_files` table
```python
- id (Integer, Primary Key)
- file_id (Integer, Foreign Key → files.id)
- num_frames (Integer)
- fps (Integer)
- render_engine (String)  # 'Cycles', 'Eevee', etc.
- resolution_x (Integer)
- resolution_y (Integer)
- total_objects (Integer)
- meshes (Integer)
- cameras (Integer)
- lights (Integer)
- empties (Integer)
- thumbnail_path (String)  # 512x512 JPG viewport render
- visual_embedding (Vector(512))  # CLIP embeddings
```

#### `text_files` table
```python
- id (Integer, Primary Key)
- file_id (Integer, Foreign Key → files.id)
```

#### `unknown_files` table
```python
- id (Integer, Primary Key)
- file_id (Integer, Foreign Key → files.id)
```

## Embedding Columns

### metadata_embedding (384 dimensions)
- **Location**: `files` table
- **Model**: sentence-transformers/all-MiniLM-L6-v2
- **Purpose**: Semantic search of file metadata
- **Generated from**: File name, path, metadata_json, and other text fields

### visual_embedding (512 dimensions)
- **Location**: `images`, `videos`, `blend_files` tables
- **Model**: openai/clip-vit-base-patch32
- **Purpose**: Visual similarity and cross-modal text-to-image search
- **Generated from**: Thumbnail images (512x512 JPG)

## Query Examples

### Semantic Text Search
```sql
SELECT 
    f.file_name,
    f.file_path,
    f.file_type,
    bf.render_engine,
    bf.resolution_x,
    bf.resolution_y,
    1 - (f.metadata_embedding <=> query_embedding) AS similarity
FROM files f
LEFT JOIN blend_files bf ON f.id = bf.file_id
WHERE f.metadata_embedding IS NOT NULL
ORDER BY f.metadata_embedding <=> query_embedding
LIMIT 10;
```

### Visual Search (CLIP)
```sql
-- Search across all visual content
SELECT * FROM (
    SELECT f.*, img.thumbnail_path,
           1 - (img.visual_embedding <=> query_embedding) AS similarity
    FROM files f
    JOIN images img ON f.id = img.file_id
    WHERE img.visual_embedding IS NOT NULL
    
    UNION ALL
    
    SELECT f.*, vid.thumbnail_path,
           1 - (vid.visual_embedding <=> query_embedding) AS similarity
    FROM files f
    JOIN videos vid ON f.id = vid.file_id
    WHERE vid.visual_embedding IS NOT NULL
    
    UNION ALL
    
    SELECT f.*, bf.thumbnail_path,
           1 - (bf.visual_embedding <=> query_embedding) AS similarity
    FROM files f
    JOIN blend_files bf ON f.id = bf.file_id
    WHERE bf.visual_embedding IS NOT NULL
) combined
ORDER BY similarity DESC
LIMIT 10;
```

### Keyword Search
```sql
SELECT 
    f.*,
    bf.render_engine,
    img.thumbnail_path
FROM files f
LEFT JOIN blend_files bf ON f.id = bf.file_id
LEFT JOIN images img ON f.id = img.file_id
WHERE 
    f.file_name ILIKE '%keyword%'
    OR f.file_path ILIKE '%keyword%'
    OR f.metadata_json::text ILIKE '%keyword%'
ORDER BY f.modified_date DESC
LIMIT 10;
```

## Indexes

Recommended indexes for performance:

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- File table indexes
CREATE INDEX idx_files_file_name ON files(file_name);
CREATE INDEX idx_files_file_path ON files(file_path);
CREATE INDEX idx_files_file_type ON files(file_type);
CREATE INDEX idx_files_modified_date ON files(modified_date DESC);

-- Vector similarity indexes (HNSW for fast approximate search)
CREATE INDEX idx_files_metadata_embedding ON files 
USING hnsw (metadata_embedding vector_cosine_ops);

CREATE INDEX idx_images_visual_embedding ON images 
USING hnsw (visual_embedding vector_cosine_ops);

CREATE INDEX idx_videos_visual_embedding ON videos 
USING hnsw (visual_embedding vector_cosine_ops);

CREATE INDEX idx_blend_files_visual_embedding ON blend_files 
USING hnsw (visual_embedding vector_cosine_ops);
```

## Lambda Integration

The Lambda function uses these queries through `database.py`:

1. **`get_relevant_metadata(query)`** - Tries semantic search first, falls back to keyword
2. **`search_by_text_embedding(embedding)`** - Searches `files.metadata_embedding`
3. **`search_by_image_embedding(text)`** - Searches `visual_embedding` across all visual types
4. **`keyword_search(query)`** - Traditional ILIKE pattern matching

All queries use LEFT JOINs to retrieve type-specific metadata when available.
