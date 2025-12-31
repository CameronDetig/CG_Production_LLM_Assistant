"""
Script to pre-download HuggingFace models for Lambda deployment.
This ensures models are bundled in the Docker image and don't need internet access at runtime.
"""

from sentence_transformers import SentenceTransformer
from transformers import CLIPProcessor, CLIPModel

print("Downloading text embedding model...")
text_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print("✅ Text model downloaded")

print("\nDownloading CLIP model...")
clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
print("✅ CLIP model and processor downloaded")

print("\n✅ All models downloaded successfully!")
print("Models are cached in ~/.cache/huggingface/ and will be bundled in the Docker image")
