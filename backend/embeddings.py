"""
Embedding generation utilities for semantic search.
Uses the same models as the metadata extractor:
- Text: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)
- Image: openai/clip-vit-base-patch32 (512 dimensions)
"""

import os
import logging
from typing import List, Optional

# Fix joblib multiprocessing warning in Lambda
# Lambda's /dev/shm has restricted permissions, causing joblib to fail
# Setting this env var forces serial mode without warnings
os.environ['JOBLIB_MULTIPROCESSING'] = '0'

import torch
from sentence_transformers import SentenceTransformer
from transformers import CLIPProcessor, CLIPModel
from PIL import Image

logger = logging.getLogger()

# Global model instances (loaded once, reused across Lambda invocations)
_text_model: Optional[SentenceTransformer] = None
_clip_model: Optional[CLIPModel] = None
_clip_processor: Optional[CLIPProcessor] = None


# Define absolute paths to bundled models in Lambda environment
# /var/task is the Lambda task root where code and files are copied
LAMBDA_TASK_ROOT = os.environ.get('LAMBDA_TASK_ROOT', '/var/task')
TEXT_MODEL_PATH = os.path.join(LAMBDA_TASK_ROOT, "model_cache", "text_model")
CLIP_MODEL_PATH = os.path.join(LAMBDA_TASK_ROOT, "model_cache", "clip_model")

def get_text_embedding_model() -> SentenceTransformer:
    """
    Get or initialize the text embedding model.
    Model: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)
    """
    global _text_model
    
    if _text_model is None:
        logger.info(f"Loading text embedding model from: {TEXT_MODEL_PATH}")
        try:
            # Load explicitly from local directory
            _text_model = SentenceTransformer(TEXT_MODEL_PATH, device='cpu')
            logger.info("Text embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load text model from {TEXT_MODEL_PATH}: {e}")
            raise
    
    return _text_model


def get_clip_model():
    """
    Get or initialize the CLIP model for image embeddings.
    Model: openai/clip-vit-base-patch32 (512 dimensions)
    """
    global _clip_model, _clip_processor
    
    if _clip_model is None or _clip_processor is None:
        logger.info(f"Loading CLIP model from: {CLIP_MODEL_PATH}")
        try:
            # Load explicitly from local directory
            _clip_model = CLIPModel.from_pretrained(CLIP_MODEL_PATH, local_files_only=True)
            _clip_processor = CLIPProcessor.from_pretrained(CLIP_MODEL_PATH, local_files_only=True)
            logger.info("CLIP model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load CLIP model from {CLIP_MODEL_PATH}: {e}")
            raise
    
    return _clip_model, _clip_processor


def generate_text_embedding(text: str) -> List[float]:
    """
    Generate text embedding for semantic search.
    
    Args:
        text: Input text (user query or metadata)
        
    Returns:
        384-dimensional embedding vector
    """
    try:
        import time
        start_time = time.time()
        
        model = get_text_embedding_model()
        embedding = model.encode(text, convert_to_tensor=False)
        
        logger.info(f"Text embedding generated in {time.time() - start_time:.3f}s")
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Error generating text embedding: {str(e)}", exc_info=True)
        # Return zero vector as fallback
        return [0.0] * 384


def generate_image_embedding_from_text(text: str) -> List[float]:
    """
    Generate CLIP embedding from text query (for cross-modal search).
    This allows searching images using text descriptions.
    
    Args:
        text: Text description
        
    Returns:
        512-dimensional CLIP embedding vector
    """
    try:
        import time
        start_time = time.time()
        
        model, processor = get_clip_model()
        
        # Process text through CLIP
        inputs = processor(text=[text], return_tensors="pt", padding=True)
        
        with torch.no_grad():
            text_features = model.get_text_features(**inputs)
        
        # Normalize embedding
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        
        logger.info(f"CLIP text embedding generated in {time.time() - start_time:.3f}s")
        return text_features[0].tolist()
    except Exception as e:
        logger.error(f"Error generating CLIP text embedding: {str(e)}", exc_info=True)
        # Return zero vector as fallback
        return [0.0] * 512


def generate_image_embedding(image_path: str) -> List[float]:
    """
    Generate CLIP embedding from image file.
    
    Args:
        image_path: Path to image file
        
    Returns:
        512-dimensional CLIP embedding vector
    """
    try:
        model, processor = get_clip_model()
        
        # Load and process image
        image = Image.open(image_path).convert('RGB')
        inputs = processor(images=image, return_tensors="pt")
        
        with torch.no_grad():
            image_features = model.get_image_features(**inputs)
        
        # Normalize embedding
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        
        return image_features[0].tolist()
    except Exception as e:
        logger.error(f"Error generating image embedding: {str(e)}", exc_info=True)
        # Return zero vector as fallback
        return [0.0] * 512


def preload_models():
    """
    Preload models during Lambda initialization to reduce cold start impact.
    Call this in lambda_function.py at module level.
    """
    try:
        logger.info("Preloading embedding models...")
        get_text_embedding_model()
        # Preload CLIP for image searches to avoid loading during queries
        get_clip_model()
        logger.info("Embedding models preloaded successfully")
    except Exception as e:
        logger.warning(f"Failed to preload models: {str(e)}")


def generate_image_embedding_from_base64(image_base64: str) -> List[float]:
    """
    Generate CLIP embedding from base64-encoded image.
    Used for image upload search functionality.
    
    Args:
        image_base64: Base64-encoded JPEG image (already resized to 512x512 client-side)
        
    Returns:
        512-dimensional CLIP embedding vector
        
    Example:
        >>> import base64
        >>> with open('image.jpg', 'rb') as f:
        ...     img_b64 = base64.b64encode(f.read()).decode('utf-8')
        >>> embedding = generate_image_embedding_from_base64(img_b64)
        >>> len(embedding)
        512
    """
    try:
        import base64
        from io import BytesIO
        
        model, processor = get_clip_model()
        
        # Decode base64 to image
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(BytesIO(image_bytes)).convert('RGB')
        
        # Generate CLIP embedding (same as generate_image_embedding but from PIL Image)
        inputs = processor(images=image, return_tensors="pt")
        
        with torch.no_grad():
            image_features = model.get_image_features(**inputs)
        
        # Normalize embedding
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        
        return image_features[0].tolist()
        
    except Exception as e:
        logger.error(f"Error generating CLIP embedding from base64: {str(e)}", exc_info=True)
        # Return zero vector as fallback
        return [0.0] * 512
