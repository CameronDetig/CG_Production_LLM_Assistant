#!/bin/bash
# Download embedding models for local development
# This matches the Lambda environment setup

set -e

echo "=================================================="
echo "Downloading Embedding Models for Local Development"
echo "=================================================="
echo ""

# Check if we're in the backend directory
if [ ! -f "requirements.txt" ]; then
    echo "❌ Error: Must run this script from the backend directory"
    echo "   cd backend && ./scripts/download_models_local.sh"
    exit 1
fi

# Create model cache directory
MODEL_CACHE_DIR="model_cache"
mkdir -p "$MODEL_CACHE_DIR"

echo "📦 Installing huggingface_hub (if needed)..."
pip3 install -q huggingface_hub

echo ""
echo "📥 Downloading models to $MODEL_CACHE_DIR/..."
echo ""

# Download models using Python
python3 - <<EOF
import os
from huggingface_hub import snapshot_download

# Define model IDs
TEXT_MODEL_ID = 'sentence-transformers/all-MiniLM-L6-v2'
CLIP_MODEL_ID = 'openai/clip-vit-base-patch32'

# Define local cache directory
CACHE_DIR = "model_cache"

print(f"1️⃣  Downloading {TEXT_MODEL_ID}...")
snapshot_download(
    repo_id=TEXT_MODEL_ID,
    local_dir=os.path.join(CACHE_DIR, "text_model"),
    local_dir_use_symlinks=False
)
print("   ✅ Text model downloaded")

print(f"\n2️⃣  Downloading {CLIP_MODEL_ID}...")
snapshot_download(
    repo_id=CLIP_MODEL_ID,
    local_dir=os.path.join(CACHE_DIR, "clip_model"),
    local_dir_use_symlinks=False
)
print("   ✅ CLIP model downloaded")

print(f"\n✅ All models downloaded to '{CACHE_DIR}/' directory")
EOF

echo ""
echo "=================================================="
echo "✅ Models downloaded successfully!"
echo "=================================================="
echo ""
echo "Model locations:"
echo "  📁 Text model: $MODEL_CACHE_DIR/text_model/"
echo "  📁 CLIP model: $MODEL_CACHE_DIR/clip_model/"
echo ""
echo "These models will be used for local testing and development."
echo "The same models are bundled into the Lambda Docker image."
echo ""
