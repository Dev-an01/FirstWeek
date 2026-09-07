"""
Model manager for Sentence Transformer embedding generation.
Wraps sentence-transformers library with GPU support and optimization.
"""

import logging
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from typing import List, Union

from . import config

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """
    Wrapper for Sentence Transformer model with GPU support.
    Handles embedding generation with normalization and batching.
    """
    
    def __init__(
        self,
        model_name: str = config.MODEL_NAME,
        device: str = config.DEVICE
    ):
        """
        Initialize Sentence Transformer model.
        
        Args:
            model_name: HuggingFace model ID (default: all-mpnet-base-v2)
            device: 'cuda' for GPU, 'cpu' for CPU
        """
        self.model_name = model_name
        self.device = device
        self.model = None
        self.embedding_dimension = config.EMBEDDING_DIMENSION
        
        logger.info(f"Initializing embedding model: {model_name}")
        logger.info(f"Target device: {device}")
        
        # Check CUDA availability if GPU requested
        if device == 'cuda':
            if not torch.cuda.is_available():
                logger.warning("CUDA requested but not available. Falling back to CPU.")
                self.device = 'cpu'
            else:
                # Test CUDA kernel compatibility (not just availability)
                try:
                    test_tensor = torch.zeros(1).cuda()
                    _ = test_tensor + 1  # Simple operation to trigger kernel
                    del test_tensor
                    torch.cuda.empty_cache()

                    gpu_name = torch.cuda.get_device_name(0)
                    gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
                    logger.info(f"GPU detected: {gpu_name}")
                    logger.info(f"GPU memory: {gpu_memory:.2f} GB")
                except RuntimeError as e:
                    if "no kernel image" in str(e) or "CUDA" in str(e):
                        logger.warning(f"CUDA kernel incompatible with GPU: {e}")
                        logger.warning("Falling back to CPU.")
                        self.device = 'cpu'
                    else:
                        raise

        # Load model
        self._load_model()
        
        # Warm up model
        self._warmup()
    
    def _load_model(self):
        """Load the Sentence Transformer model."""
        try:
            logger.info("Loading Sentence Transformer model...")
            self.model = SentenceTransformer(self.model_name, device=self.device)

            # Verify embedding dimension
            test_embedding = self.model.encode("test", show_progress_bar=False)
            actual_dim = len(test_embedding)

            if actual_dim != self.embedding_dimension:
                logger.warning(
                    f"Expected {self.embedding_dimension}D but got {actual_dim}D. "
                    f"Updating expected dimension."
                )
                self.embedding_dimension = actual_dim

            logger.info(f"Model loaded successfully: {self.model_name}")
            logger.info(f"Embedding dimension: {self.embedding_dimension}")
            logger.info(f"Model device: {self.model.device}")

        except RuntimeError as e:
            # Handle CUDA kernel compatibility errors during model loading
            if ("no kernel image" in str(e) or "CUDA" in str(e)) and self.device == 'cuda':
                logger.warning(f"CUDA error during model loading: {e}")
                logger.warning("Retrying with CPU...")
                self.device = 'cpu'
                self.model = SentenceTransformer(self.model_name, device=self.device)

                # Verify embedding dimension
                test_embedding = self.model.encode("test", show_progress_bar=False)
                self.embedding_dimension = len(test_embedding)

                logger.info(f"Model loaded successfully on CPU: {self.model_name}")
                logger.info(f"Embedding dimension: {self.embedding_dimension}")
            else:
                logger.error(f"Failed to load model: {e}")
                raise RuntimeError(f"Model loading failed: {e}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise RuntimeError(f"Model loading failed: {e}")
    
    def _warmup(self):
        """Warm up model with a dummy encoding (first call is slower)."""
        try:
            logger.info("Warming up model...")
            _ = self.model.encode("Warm-up text to initialize model", show_progress_bar=False)
            logger.info("Model warm-up complete")
        except Exception as e:
            logger.warning(f"Model warm-up failed (non-critical): {e}")
    
    def generate_embedding(
        self,
        text: str,
        normalize: bool = config.NORMALIZE_EMBEDDINGS
    ) -> np.ndarray:
        """
        Generate single embedding from text.
        
        Args:
            text: Input text to embed
            normalize: Whether to L2 normalize (default: True)
        
        Returns:
            Numpy array of shape (embedding_dimension,)
            
        Raises:
            ValueError: If text is invalid
            RuntimeError: If embedding generation fails
        """
        if not text or not isinstance(text, str):
            raise ValueError("Text must be a non-empty string")
        
        try:
            # Generate embedding
            embedding = self.model.encode(
                text,
                normalize_embeddings=normalize,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            
            # Ensure it's the right shape
            if embedding.shape[0] != self.embedding_dimension:
                raise RuntimeError(
                    f"Unexpected embedding dimension: {embedding.shape[0]} "
                    f"(expected {self.embedding_dimension})"
                )
            
            logger.debug(f"Generated embedding for text ({len(text)} chars)")
            
            return embedding
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            logger.error(f"Text preview: {text[:100]}...")
            raise RuntimeError(f"Failed to generate embedding: {e}")
    
    def generate_embeddings_batch(
        self,
        texts: List[str],
        normalize: bool = config.NORMALIZE_EMBEDDINGS,
        batch_size: int = config.BATCH_SIZE,
        show_progress: bool = config.SHOW_PROGRESS
    ) -> np.ndarray:
        """
        Generate embeddings for multiple texts (faster than individual calls).
        
        Args:
            texts: List of input texts
            normalize: Whether to L2 normalize (default: True)
            batch_size: Batch size for processing
            show_progress: Show progress bar
        
        Returns:
            Numpy array of shape (len(texts), embedding_dimension)
            
        Raises:
            ValueError: If texts is invalid
            RuntimeError: If embedding generation fails
        """
        if not texts or not isinstance(texts, list):
            raise ValueError("Texts must be a non-empty list")
        
        if not all(isinstance(t, str) and t for t in texts):
            raise ValueError("All texts must be non-empty strings")
        
        try:
            logger.info(f"Generating embeddings for {len(texts)} texts (batch_size={batch_size})")
            
            # Generate embeddings in batch
            embeddings = self.model.encode(
                texts,
                normalize_embeddings=normalize,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
                batch_size=batch_size
            )
            
            # Verify shape
            expected_shape = (len(texts), self.embedding_dimension)
            if embeddings.shape != expected_shape:
                raise RuntimeError(
                    f"Unexpected embeddings shape: {embeddings.shape} "
                    f"(expected {expected_shape})"
                )
            
            logger.info(f"Generated {len(embeddings)} embeddings successfully")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            raise RuntimeError(f"Failed to generate batch embeddings: {e}")
    
    def verify_embedding(self, embedding: np.ndarray) -> dict:
        """
        Verify that an embedding is valid.
        
        Args:
            embedding: Numpy array to verify
        
        Returns:
            Dict with verification results
        """
        results = {
            'valid': True,
            'dimension': None,
            'norm': None,
            'normalized': None,
            'errors': []
        }
        
        # Check type
        if not isinstance(embedding, np.ndarray):
            results['valid'] = False
            results['errors'].append("Not a numpy array")
            return results
        
        # Check dimension
        results['dimension'] = embedding.shape[0] if embedding.ndim == 1 else None
        if results['dimension'] != self.embedding_dimension:
            results['valid'] = False
            results['errors'].append(
                f"Wrong dimension: {results['dimension']} (expected {self.embedding_dimension})"
            )
        
        # Check norm
        results['norm'] = np.linalg.norm(embedding)
        results['normalized'] = abs(results['norm'] - 1.0) < config.NORM_TOLERANCE
        
        if not results['normalized']:
            results['errors'].append(
                f"Not normalized: L2 norm = {results['norm']:.4f} (expected ~1.0)"
            )
        
        return results
    
    def get_gpu_info(self) -> dict:
        """
        Get GPU information if available.
        
        Returns:
            Dict with GPU info or empty dict if not available
        """
        if not torch.cuda.is_available():
            return {'available': False}
        
        try:
            return {
                'available': True,
                'device_name': torch.cuda.get_device_name(0),
                'device_count': torch.cuda.device_count(),
                'memory_allocated_gb': torch.cuda.memory_allocated(0) / 1e9,
                'memory_reserved_gb': torch.cuda.memory_reserved(0) / 1e9,
                'memory_total_gb': torch.cuda.get_device_properties(0).total_memory / 1e9
            }
        except Exception as e:
            logger.warning(f"Failed to get GPU info: {e}")
            return {'available': True, 'error': str(e)}
    
    def __repr__(self):
        return (
            f"EmbeddingModel(model={self.model_name}, "
            f"device={self.device}, dim={self.embedding_dimension})"
        )



# Shared singleton instance
_shared_model_instance = None


def get_shared_embedding_model(
    model_name: str = config.MODEL_NAME,
    device: str = config.DEVICE
) -> EmbeddingModel:
    """
    Get or create a shared singleton instance of EmbeddingModel.
    
    This ensures we only load the heavy BAAI/bge-m3 model once per process,
    preventing CUDA OOM errors when multiple components need embeddings.
    
    Args:
        model_name: Model ID to load
        device: Device to use (cuda/cpu)
        
    Returns:
        Shared EmbeddingModel instance
    """
    global _shared_model_instance
    if _shared_model_instance is None:
        logger.info(f"Creating shared EmbeddingModel instance ({model_name} on {device})")
        _shared_model_instance = EmbeddingModel(model_name, device)
    return _shared_model_instance


# Example usage and testing
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s'
    )
    
    print("\n" + "="*60)
    print("EMBEDDING MODEL TEST")
    print("="*60)
    
    # Initialize model
    print("\n1. Initializing model...")
    model = EmbeddingModel()
    
    # GPU info
    print("\n2. GPU Information:")
    gpu_info = model.get_gpu_info()
    for key, value in gpu_info.items():
        print(f"   {key}: {value}")
    
    # Test single embedding
    print("\n3. Testing single embedding generation...")
    test_text = "This is a test sentence for embedding generation."
    embedding = model.generate_embedding(test_text)
    print(f"   Text: {test_text}")
    print(f"   Embedding shape: {embedding.shape}")
    print(f"   Embedding preview: [{embedding[0]:.4f}, {embedding[1]:.4f}, ...]")
    print(f"   L2 norm: {np.linalg.norm(embedding):.6f}")
    
    # Verify embedding
    print("\n4. Verifying embedding...")
    verification = model.verify_embedding(embedding)
    print(f"   Valid: {verification['valid']}")
    print(f"   Dimension: {verification['dimension']}")
    print(f"   Norm: {verification['norm']:.6f}")
    print(f"   Normalized: {verification['normalized']}")
    if verification['errors']:
        print(f"   Errors: {verification['errors']}")
    
    # Test batch embedding
    print("\n5. Testing batch embedding generation...")
    test_texts = [
        "First test sentence about AI and machine learning.",
        "Second sentence discussing natural language processing.",
        "Third sentence about vector embeddings and similarity."
    ]
    batch_embeddings = model.generate_embeddings_batch(test_texts, show_progress=False)
    print(f"   Number of texts: {len(test_texts)}")
    print(f"   Batch embeddings shape: {batch_embeddings.shape}")
    print(f"   All norms close to 1.0: {all(abs(np.linalg.norm(e) - 1.0) < 0.01 for e in batch_embeddings)}")
    
    # Test similarity
    print("\n6. Testing semantic similarity...")
    sim_12 = np.dot(batch_embeddings[0], batch_embeddings[1])
    sim_13 = np.dot(batch_embeddings[0], batch_embeddings[2])
    print(f"   Similarity(1, 2): {sim_12:.4f}")
    print(f"   Similarity(1, 3): {sim_13:.4f}")
    print(f"   (Higher score = more similar)")
    
    print("\n" + "="*60)
    print("✅ All tests completed successfully!")
    print("="*60)
