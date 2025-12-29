"""
Embedding generation utilities for semantic search.
Uses the same models as the metadata extractor:
- Text: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)
- Image: openai/clip-vit-base-patch32 (512 dimensions)
"""

import logging
from typing import List, Optional
import torch
from sentence_transformers import SentenceTransformer
from transformers import CLIPProcessor, CLIPModel
from PIL import Image

logger = logging.getLogger()

# Global model instances (loaded once, reused across Lambda invocations)
_text_model: Optional[SentenceTransformer] = None
_clip_model: Optional[CLIPModel] = None
_clip_processor: Optional[CLIPProcessor] = None


def get_text_embedding_model() -> SentenceTransformer:
    """
    Get or initialize the text embedding model.
    Model: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)
    """
    global _text_model
    
    if _text_model is None:
        logger.info("Loading text embedding model: all-MiniLM-L6-v2")
        _text_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        logger.info("Text embedding model loaded successfully")
    
    return _text_model


def get_clip_model():
    """
    Get or initialize the CLIP model for image embeddings.
    Model: openai/clip-vit-base-patch32 (512 dimensions)
    """
    global _clip_model, _clip_processor
    
    if _clip_model is None or _clip_processor is None:
        logger.info("Loading CLIP model: clip-vit-base-patch32")
        _clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        _clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        logger.info("CLIP model loaded successfully")
    
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
        model = get_text_embedding_model()
        embedding = model.encode(text, convert_to_tensor=False)
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
        model, processor = get_clip_model()
        
        # Process text through CLIP
        inputs = processor(text=[text], return_tensors="pt", padding=True)
        
        with torch.no_grad():
            text_features = model.get_text_features(**inputs)
        
        # Normalize embedding
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        
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
        # Optionally preload CLIP if you expect image searches
        # get_clip_model()
        logger.info("Embedding models preloaded successfully")
    except Exception as e:
        logger.warning(f"Failed to preload models: {str(e)}")
