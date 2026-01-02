# Database Schema Documentation

## Overview

This document describes the PostgreSQL database schema used by the CG Production LLM Assistant. The database stores metadata about Blender files, videos, images, and other production assets, along with embeddings for semantic search.

The database follows a **star schema** pattern with a central `files` table and specialized tables for different file types.

## Database Name
`cg-metadata-db`

## Tables

### 1. `files` (Central Table)

General metadata about all files in the database.

**Primary Key**: `id` (integer)

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | Unique identifier |
| `file_name` | character_varying | Name of the file including the extension. Does not include the path. |
| `file_path` | character_varying | Full path to the file. |
| `file_type` | character_varying | Category the file falls into (e.g., "image", "video", "blend") |
| `extension` | character_varying | File prefix extension (e.g., ".png", ".jpg", ".blend", ".mp4") |
| `file_size` | integer | Size of the file in KB. |
| `created_date` | timestamp | Date the file was created. |
| `modified_date` | timestamp | Most recent date that the file was modified. |
| `scan_date` | timestamp | Date that the file was scanned and put into this database. |
| `metadata_json` | json | Contains the full set of information from the other columns in this table. |
| `error` | text | Typically is Null, but if there was an error scanning the file, it will show here. |
| `metadata_embedding` | vector | An embedding vector of the metadata for this entry. Uses the model: all-MiniLM-L6-v2 with 384 dimensions. Is used to measure the similarity of metadata between files. |

---

### 2. `blend_files`

Metadata specific to Blender (.blend) files.

**Primary Key**: `id` (integer)

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | The id specific to the blend files in this table. |
| `file_id` | integer | ID number of the file, relates to the ID from the "files" table. |
| `num_frames` | integer | Total number of frames in the blend file. |
| `fps` | integer | Frames Per Second (frame rate). |
| `render_engine` | character_varying | The specific render engine the blend file is set to (e.g., "CYCLES", "EEVEE"). |
| `resolution_x` | integer | Number of horizontal pixels the file is set to render. |
| `resolution_y` | integer | Number of vertical pixels the file is set to render. |
| `total_objects` | integer | Number of objects within the blend file. |
| `meshes` | integer | Number of meshes within the blend file. |
| `cameras` | integer | Number of cameras within the blend file. |
| `lights` | integer | Number of lights within the blend file. |
| `empties` | integer | Number of empties within the blend file. |
| `thumbnail_path` | character_varying | File path to the thumbnail image of the contents of this blend file. |
| `visual_embedding` | vector | An embedding vector of this file's thumbnail image. Uses CLIP model with 512 dimensions. Used to compare the similarity of images and to search for images using text prompts. |

---

### 3. `images`

Metadata specific to image files.

**Primary Key**: `id` (integer)

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | The id specific to the images in this table. |
| `file_id` | integer | ID number of the file, relates to the ID from the "files" table. |
| `width` | integer | Number of horizontal pixels in the image. |
| `height` | integer | Number of vertical pixels in the image. |
| `mode` | character_varying | Color mode of the image (e.g., "RGB", "RGBA"). |
| `thumbnail_path` | character_varying | File path to the thumbnail image. |
| `visual_embedding` | vector | An embedding vector of this file's thumbnail image. Uses CLIP model with 512 dimensions. Used to compare the similarity of images and to search for images using text prompts. |

---

### 4. `videos`

Metadata specific to video files.

**Primary Key**: `id` (integer)

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | The id specific to the videos in this table. |
| `file_id` | integer | ID number of the file, relates to the ID from the "files" table. |
| `width` | integer | Number of horizontal pixels in the video. |
| `height` | integer | Number of vertical pixels in the video. |
| `duration` | double_precision | How long the video is in seconds. |
| `fps` | double_precision | Frames per second of the video. |
| `codec` | character_varying | Codec used for the video (e.g., "h264", "mov"). |
| `bit_rate` | integer | Amount of digital data processed per second, measured in bits per second (bps). |
| `thumbnail_path` | character_varying | File path to the thumbnail image. |
| `visual_embedding` | vector | An embedding vector of this file's thumbnail image. Uses CLIP model with 512 dimensions. Used to compare the similarity of images and to search for images using text prompts. |

---

### 5. `text_files`

Metadata specific to text files.

**Primary Key**: `id` (integer)

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | The id specific to the files in this table. |
| `file_id` | integer | ID number of the file, relates to the ID from the "files" table. |

---

### 6. `unknown_files`

Metadata for all other files that don't fit into the categories of image, video, blend, or text.

**Primary Key**: `id` (integer)

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | The id specific to the files in this table. |
| `file_id` | integer | ID number of the file, relates to the ID from the "files" table. |

---

## Relationships

All specialized file tables have a **many-to-one** relationship with the central `files` table:

| Relationship | Left Table | Right Table | Join Column | Type |
|--------------|------------|-------------|-------------|------|
| `blend_files_to_files` | blend_files | files | file_id → id | many-to-one |
| `images_to_files` | images | files | file_id → id | many-to-one |
| `videos_to_files` | videos | files | file_id → id | many-to-one |
| `text_files_to_files` | text_files | files | file_id → id | many-to-one |
| `unknown_files_to_files` | unknown_files | files | file_id → id | many-to-one |

**Note**: Each specialized file entry references exactly one file in the `files` table through the `file_id` foreign key.

---

## Embedding Details

### Metadata Embeddings (Text)
- **Model**: `all-MiniLM-L6-v2`
- **Dimensions**: 384
- **Purpose**: Semantic search of file metadata
- **Location**: `files.metadata_embedding`
- **Generated from**: File metadata (name, path, type, etc.)

### Visual Embeddings (Image)
- **Model**: CLIP
- **Dimensions**: 512
- **Purpose**: Cross-modal search (text-to-image) for visual content
- **Location**: `blend_files.visual_embedding`, `images.visual_embedding`, `videos.visual_embedding`
- **Generated from**: Thumbnail images

---

## Indexes

For optimal performance, create these indexes:

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Indexes for keyword search on files table
CREATE INDEX idx_file_name ON files(file_name);
CREATE INDEX idx_file_path ON files(file_path);
CREATE INDEX idx_file_type ON files(file_type);
CREATE INDEX idx_modified_date ON files(modified_date DESC);

-- Indexes for foreign keys
CREATE INDEX idx_blend_files_file_id ON blend_files(file_id);
CREATE INDEX idx_images_file_id ON images(file_id);
CREATE INDEX idx_videos_file_id ON videos(file_id);
CREATE INDEX idx_text_files_file_id ON text_files(file_id);
CREATE INDEX idx_unknown_files_file_id ON unknown_files(file_id);

-- Indexes for vector similarity search (HNSW for fast approximate search)
CREATE INDEX idx_metadata_embedding ON files 
USING hnsw (metadata_embedding vector_cosine_ops);

CREATE INDEX idx_blend_visual_embedding ON blend_files 
USING hnsw (visual_embedding vector_cosine_ops);

CREATE INDEX idx_image_visual_embedding ON images 
USING hnsw (visual_embedding vector_cosine_ops);

CREATE INDEX idx_video_visual_embedding ON videos 
USING hnsw (visual_embedding vector_cosine_ops);
```

---

## Search Strategies

### 1. Semantic Metadata Search
Uses cosine similarity on `files.metadata_embedding`:
```sql
SELECT f.*, 1 - (f.metadata_embedding <=> query_embedding) AS similarity
FROM files f
WHERE f.metadata_embedding IS NOT NULL
ORDER BY f.metadata_embedding <=> query_embedding
LIMIT 10;
```

### 2. Visual Search (Cross-Modal)
Uses CLIP to search images with text queries:
```sql
-- Search images
SELECT f.*, i.*, 1 - (i.visual_embedding <=> query_embedding) AS similarity
FROM images i
JOIN files f ON i.file_id = f.id
WHERE i.visual_embedding IS NOT NULL
ORDER BY i.visual_embedding <=> query_embedding
LIMIT 10;
```

### 3. Keyword Search (Fallback)
Traditional ILIKE pattern matching:
```sql
SELECT *
FROM files
WHERE file_name ILIKE '%keyword%'
   OR file_path ILIKE '%keyword%'
ORDER BY modified_date DESC
LIMIT 10;
```

---

## Verified Queries

### Example: Count images in a specific show

**Question**: "How many images are there in the Spring show?"

```sql
SELECT
  COUNT(*) AS image_count
FROM
  images i
  JOIN files f ON i.file_id = f.id
WHERE
  f.file_path LIKE '%Spring%';
```

---

## Notes

- **Null embeddings**: Files without embeddings will only be found via keyword search
- **Distance metrics**: Using cosine distance (`<=>`) for similarity
- **Performance**: HNSW indexes provide fast approximate nearest neighbor search
- **Similarity scores**: Range from 0 (identical) to 2 (opposite), converted to 0-1 scale in results
- **Star schema**: The `files` table is the central fact table, with specialized dimension tables for each file type
