"""
Script to pre-download HuggingFace models for Lambda deployment.
Downloads models to a local directory that will be bundled in the Docker image.
"""

import os
from huggingface_hub import snapshot_download

# Define model IDs
TEXT_MODEL_ID = 'sentence-transformers/all-MiniLM-L6-v2'
CLIP_MODEL_ID = 'openai/clip-vit-base-patch32'

# Define local cache directory (relative to this script)
CACHE_DIR = "model_cache"

print(f"Downloading models to {CACHE_DIR}...")

# Download Text Model
print(f"\nDownloading {TEXT_MODEL_ID}...")
snapshot_download(
    repo_id=TEXT_MODEL_ID,
    local_dir=os.path.join(CACHE_DIR, "text_model"),
    local_dir_use_symlinks=False  # Important for Docker consistency
)
print("✅ Text model downloaded permenantly")

# Download CLIP Model
print(f"\nDownloading {CLIP_MODEL_ID}...")
snapshot_download(
    repo_id=CLIP_MODEL_ID,
    local_dir=os.path.join(CACHE_DIR, "clip_model"),
    local_dir_use_symlinks=False
)
print("✅ CLIP model downloaded permenantly")

print(f"\n✅ All models downloaded to '{CACHE_DIR}' directory.")
print("These will be bundled directly into the Lambda container.")
