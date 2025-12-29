# Database Schema Documentation

## Overview

This document describes the PostgreSQL database schema used by the CG Production LLM Assistant. The database stores metadata about Blender files, videos, images, and other production assets, along with embeddings for semantic search.

## Table: `media_metadata`

### Core Metadata Columns

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PRIMARY KEY | Unique identifier |
| `file_name` | VARCHAR(255) | Name of the file |
| `file_path` | TEXT | Full path to the file |
| `file_size` | BIGINT | File size in bytes |
| `created_date` | TIMESTAMP | File creation date |
| `modified_date` | TIMESTAMP | Last modification date |

### Media-Specific Columns

| Column | Type | Description |
|--------|------|-------------|
| `resolution` | VARCHAR(50) | Video/image resolution (e.g., "3840x2160", "1920x1080") |
| `color_space` | VARCHAR(50) | Color space (e.g., "sRGB", "Linear", "ACEScg") |
| `frame_count` | INTEGER | Number of frames (for videos/sequences) |
| `render_engine` | VARCHAR(50) | Render engine used (e.g., "Cycles", "Eevee") |

### Project Organization Columns

| Column | Type | Description |
|--------|------|-------------|
| `project_name` | VARCHAR(255) | Associated project name |
| `tags` | TEXT | Comma-separated tags or JSON array |
| `thumbnail_path` | TEXT | Path to thumbnail image |

### Embedding Columns (pgvector)

| Column | Type | Description |
|--------|------|-------------|
| `text_embedding` | vector(384) | Text embedding from all-MiniLM-L6-v2 |
| `image_embedding` | vector(512) | Image embedding from clip-vit-base-patch32 |

## Indexes

For optimal performance, create these indexes:

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Indexes for keyword search
CREATE INDEX idx_file_name ON media_metadata(file_name);
CREATE INDEX idx_project_name ON media_metadata(project_name);
CREATE INDEX idx_modified_date ON media_metadata(modified_date DESC);

-- Indexes for vector similarity search (HNSW for fast approximate search)
CREATE INDEX idx_text_embedding ON media_metadata 
USING hnsw (text_embedding vector_cosine_ops);

CREATE INDEX idx_image_embedding ON media_metadata 
USING hnsw (image_embedding vector_cosine_ops);
```

## Embedding Details

### Text Embeddings
- **Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Dimensions**: 384
- **Purpose**: Semantic search of file metadata, descriptions, tags
- **Generated from**: File name, project name, tags, and other text metadata

### Image Embeddings
- **Model**: `openai/clip-vit-base-patch32`
- **Dimensions**: 512
- **Purpose**: Cross-modal search (text-to-image) for visual content
- **Generated from**: Thumbnail images of videos, renders, and Blender files

## Search Strategies

### 1. Semantic Text Search
Uses cosine similarity on `text_embedding`:
```sql
SELECT *, 1 - (text_embedding <=> query_embedding) AS similarity
FROM media_metadata
WHERE text_embedding IS NOT NULL
ORDER BY text_embedding <=> query_embedding
LIMIT 10;
```

### 2. Image Search (Cross-Modal)
Uses CLIP to search images with text queries:
```sql
SELECT *, 1 - (image_embedding <=> query_embedding) AS similarity
FROM media_metadata
WHERE image_embedding IS NOT NULL
ORDER BY image_embedding <=> query_embedding
LIMIT 10;
```

### 3. Keyword Search (Fallback)
Traditional ILIKE pattern matching:
```sql
SELECT *
FROM media_metadata
WHERE file_name ILIKE '%keyword%'
   OR project_name ILIKE '%keyword%'
   OR tags ILIKE '%keyword%'
ORDER BY modified_date DESC
LIMIT 10;
```

## Example Queries

### Find similar files by description
```python
from embeddings import generate_text_embedding
from database import search_by_text_embedding

query = "high resolution lighting renders"
embedding = generate_text_embedding(query)
results = search_by_text_embedding(embedding, limit=10)
```

### Find images matching a description
```python
from database import search_by_image_embedding

query = "dark moody scene with blue lighting"
results = search_by_image_embedding(query, limit=10)
```

### Hybrid search (combine semantic + keyword)
The `get_relevant_metadata()` function automatically tries semantic search first, then falls back to keyword search if needed.

## Notes

- **Null embeddings**: Files without embeddings will only be found via keyword search
- **Distance metrics**: Using cosine distance (`<=>`) for similarity
- **Performance**: HNSW indexes provide fast approximate nearest neighbor search
- **Similarity scores**: Range from 0 (identical) to 2 (opposite), converted to 0-1 scale in results
