# Database Schema Documentation

## Overview

This document describes the PostgreSQL database schema used by the CG Production LLM Assistant. The database stores metadata about Blender files, videos, images, audio, code, documents, spreadsheets, and other production assets, along with embeddings for semantic and visual search.

The database follows a **star schema** pattern with a central `files` table, a `shows` table for production metadata, and specialized tables for different file types.

## Database Name
`cg-metadata-db`

## Tables

### 1. `shows` (Production Metadata)

Metadata about shows/productions.

**Primary Key**: `name` (character_varying)

| Column | Type | Description |
|--------|------|-------------|
| `name` | character_varying(255) | Show name (primary key), extracted from file paths |
| `release_date` | timestamp | Release date of the show |
| `description` | text | Description of the show |
| `director` | character_varying(255) | Director of the show |
| `blender_version` | character_varying(20) | Primary Blender version used for the show |
| `characters` | json | List of character names in the show |
| `created_at` | timestamp | Timestamp when record was created |
| `updated_at` | timestamp | Timestamp when record was last updated |

---

### 2. `files` (Central Table)

General metadata about all files in the database.

**Primary Key**: `id` (integer)

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | Unique identifier |
| `file_name` | character_varying(255) | Name of the file including extension. Does not include the path. |
| `file_path` | character_varying(1024) | Full path to the file. |
| `file_type` | character_varying(50) | Category the file falls into (e.g., "image", "video", "blend", "audio", "code", "spreadsheet", "document") |
| `extension` | character_varying(50) | File extension (e.g., ".png", ".jpg", ".blend", ".mp4") |
| `file_size` | integer | Size of the file in bytes. |
| `created_date` | timestamp | Date the file was created. |
| `modified_date` | timestamp | Most recent date that the file was modified. |
| `scan_date` | timestamp | Date that the file was scanned and put into this database. |
| `show` | character_varying(255) | Show name (foreign key to shows.name). Can be "other" for non-show files. |
| `version_number` | integer | Version number extracted from filename if present. |
| `error` | text | Typically is Null, but if there was an error scanning the file, it will show here. |
| `metadata_embedding` | vector(384) | Embedding vector of the metadata. Uses all-MiniLM-L6-v2 model with 384 dimensions for semantic search. |

---

### 3. `blend_files`

Metadata specific to Blender (.blend) files.

**Primary Key**: `id` (integer)

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | The id specific to the blend files in this table. |
| `file_id` | integer | ID number of the file, relates to the ID from the "files" table. |
| `blender_version` | character_varying(20) | Blender version from file header (e.g., "4.0.2" or "2.49"). |
| `num_frames` | integer | Total number of frames in the blend file. |
| `fps` | integer | Frames Per Second (frame rate). |
| `render_engine` | character_varying(100) | The specific render engine the blend file is set to (e.g., "CYCLES", "EEVEE"). |
| `resolution_x` | integer | Number of horizontal pixels the file is set to render. |
| `resolution_y` | integer | Number of vertical pixels the file is set to render. |
| `total_objects` | integer | Number of objects within the blend file. |
| `meshes` | integer | Number of meshes within the blend file. |
| `cameras` | integer | Number of cameras within the blend file. |
| `lights` | integer | Number of lights within the blend file. |
| `thumbnail_path` | character_varying(1024) | Path to 512x512 JPG thumbnail. Format: `show/blend/file_id_thumb.jpg` |
| `visual_embedding` | vector(512) | Embedding vector of thumbnail image. Uses CLIP model with 512 dimensions for visual similarity search. |

---

### 4. `images`

Metadata specific to image files.

**Primary Key**: `id` (integer)

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | The id specific to the images in this table. |
| `file_id` | integer | ID number of the file, relates to the ID from the "files" table. |
| `resolution_x` | integer | Number of horizontal pixels in the image. |
| `resolution_y` | integer | Number of vertical pixels in the image. |
| `mode` | character_varying(50) | Color mode of the image (e.g., "RGB", "RGBA"). |
| `thumbnail_path` | character_varying(1024) | Path to 512x512 JPG thumbnail. Format: `show/images/file_id_thumb.jpg` |
| `visual_embedding` | vector(512) | Embedding vector of thumbnail image. Uses CLIP model with 512 dimensions for visual similarity search. |

---

### 5. `videos`

Metadata specific to video files.

**Primary Key**: `id` (integer)

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | The id specific to the videos in this table. |
| `file_id` | integer | ID number of the file, relates to the ID from the "files" table. |
| `resolution_x` | integer | Number of horizontal pixels in the video. |
| `resolution_y` | integer | Number of vertical pixels in the video. |
| `duration` | double_precision | How long the video is in seconds. |
| `fps` | double_precision | Frames per second of the video. |
| `codec` | character_varying(100) | Codec used for the video (e.g., "h264", "mov"). |
| `bit_rate` | integer | Amount of digital data processed per second, measured in bits per second (bps). |
| `thumbnail_path` | character_varying(1024) | Path to 512x512 JPG thumbnail. Format: `show/videos/file_id_thumb.jpg` |
| `visual_embedding` | vector(512) | Embedding vector of thumbnail image. Uses CLIP model with 512 dimensions for visual similarity search. |

---

### 6. `audio`

Audio file-specific metadata.

**Primary Key**: `id` (integer)

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | The id specific to audio files in this table. |
| `file_id` | integer | ID number of the file, relates to the ID from the "files" table. |
| `duration` | double_precision | Duration of the audio in seconds. |
| `bitrate` | integer | Bitrate in bits per second. |
| `sample_rate` | integer | Sample rate in Hz (e.g., 44100, 48000). |
| `channels` | integer | Number of audio channels (1=mono, 2=stereo, etc.). |
| `codec` | character_varying(50) | Audio codec (e.g., "mp3", "flac", "aac", "wav"). |

---

### 7. `code`

Code file-specific metadata.

**Primary Key**: `id` (integer)

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | The id specific to code files in this table. |
| `file_id` | integer | ID number of the file, relates to the ID from the "files" table. |
| `language` | character_varying(50) | Programming language (e.g., "python", "cpp", "javascript"). |
| `num_lines` | integer | Total number of lines in the file. |
| `encoding` | character_varying(50) | File encoding (e.g., "utf-8", "ascii"). |
| `has_shebang` | boolean | Whether file has a shebang (#!/usr/bin/env python). |

---

### 8. `spreadsheets`

Spreadsheet file-specific metadata.

**Primary Key**: `id` (integer)

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | The id specific to spreadsheet files in this table. |
| `file_id` | integer | ID number of the file, relates to the ID from the "files" table. |
| `num_sheets` | integer | Number of sheets/tabs in the spreadsheet. |
| `sheet_names` | json | List of sheet names. |
| `num_rows` | integer | Total number of rows (sum for Excel, count for CSV). |
| `num_columns` | integer | Maximum number of columns. |
| `has_header` | boolean | Whether a header row was detected. |

---

### 9. `documents`

Document file-specific metadata (text files, PDFs, Word docs, etc.).

**Primary Key**: `id` (integer)

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | The id specific to document files in this table. |
| `file_id` | integer | ID number of the file, relates to the ID from the "files" table. |
| `doc_type` | character_varying(50) | Document type (e.g., "txt", "pdf", "docx", "odt", "md"). |
| `page_count` | integer | Number of pages (for PDF, ODT, DOCX). |
| `word_count` | integer | Approximate word count. |

---

### 10. `unknown_files`

Metadata for all other files that don't fit into the above categories.

**Primary Key**: `id` (integer)

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | The id specific to the files in this table. |
| `file_id` | integer | ID number of the file, relates to the ID from the "files" table. |

---

## Relationships

All specialized file tables have a **many-to-one** relationship with the central `files` table. The `files` table has a **many-to-one** relationship with the `shows` table.

| Relationship | Left Table | Right Table | Join Column | Type |
|--------------|------------|-------------|-------------|------|
| `files_to_shows` | files | shows | show → name | many-to-one |
| `blend_files_to_files` | blend_files | files | file_id → id | many-to-one |
| `images_to_files` | images | files | file_id → id | many-to-one |
| `videos_to_files` | videos | files | file_id → id | many-to-one |
| `audio_to_files` | audio | files | file_id → id | many-to-one |
| `code_to_files` | code | files | file_id → id | many-to-one |
| `spreadsheets_to_files` | spreadsheets | files | file_id → id | many-to-one |
| `documents_to_files` | documents | files | file_id → id | many-to-one |
| `unknown_files_to_files` | unknown_files | files | file_id → id | many-to-one |

**Note**: Each specialized file entry references exactly one file in the `files` table through the `file_id` foreign key. Each file can optionally belong to a show.

---

## S3 Thumbnail Structure

Thumbnails are stored in S3 with the following structure:

```
cg-production-data-thumbnails/
├── show1/
│   ├── blend/
│   │   └── {file_id}_thumb.jpg
│   ├── images/
│   │   └── {file_id}_thumb.jpg
│   └── videos/
│       └── {file_id}_thumb.jpg
├── show2/
│   ├── blend/
│   ├── images/
│   └── videos/
└── other/
    ├── blend/
    ├── images/
    └── videos/
```

**Example paths:**
- `show1/images/123_thumb.jpg`
- `show2/blend/456_thumb.jpg`
- `other/videos/789_thumb.jpg`

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
CREATE INDEX idx_file_show ON files(show);
CREATE INDEX idx_modified_date ON files(modified_date DESC);

-- Indexes for foreign keys
CREATE INDEX idx_blend_files_file_id ON blend_files(file_id);
CREATE INDEX idx_images_file_id ON images(file_id);
CREATE INDEX idx_videos_file_id ON videos(file_id);
CREATE INDEX idx_audio_file_id ON audio(file_id);
CREATE INDEX idx_code_file_id ON code(file_id);
CREATE INDEX idx_spreadsheets_file_id ON spreadsheets(file_id);
CREATE INDEX idx_documents_file_id ON documents(file_id);
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

### 3. Show-Based Filtering
Use the `show` column for efficient filtering:
```sql
SELECT f.*, i.*
FROM files f
JOIN images i ON f.id = i.file_id
WHERE f.show = 'show1'
  AND f.file_type = 'image'
ORDER BY f.modified_date DESC
LIMIT 20;
```

---

## Verified Queries

### Example 1: Count files in specific show

**Question**: "How many blend files are there in the charge show?"

```sql
SELECT COUNT(*) AS blend_file_count
FROM blend_files bf
JOIN files f ON bf.file_id = f.id
WHERE f.show = 'charge';
```

### Example 2: Find 4K renders

**Question**: "Find 4K renders"

```sql
SELECT
  f.id,
  f.file_name,
  f.file_path,
  f.file_type,
  f.show,
  img.resolution_x,
  img.resolution_y,
  img.thumbnail_path
FROM files f
JOIN images img ON f.id = img.file_id
WHERE img.resolution_x >= 3840
  AND img.resolution_y >= 2160
ORDER BY f.modified_date DESC
LIMIT 10;
```

### Example 3: Show statistics

**Question**: "How many files does each show have?"

```sql
SELECT
  f.show,
  COUNT(*) AS file_count,
  COUNT(DISTINCT f.file_type) AS file_types
FROM files f
GROUP BY f.show
ORDER BY file_count DESC;
```

---

## Notes

- **Null embeddings**: Files without embeddings will only be found via keyword search
- **Distance metrics**: Using cosine distance (`<=>`) for similarity
- **Performance**: HNSW indexes provide fast approximate nearest neighbor search
- **Similarity scores**: Range from 0 (identical) to 2 (opposite), converted to 0-1 scale in results
- **Star schema**: The `files` table is the central fact table, with specialized dimension tables for each file type
- **Show column**: Use `show = 'show_name'` for filtering instead of `LIKE` on file_path for better performance
- **Resolution columns**: Use `resolution_x` and `resolution_y` (not width/height) across images, videos, and blend_files tables
