"""
Embedding Service Client
Integration layer for calling the external embedding service microservice.
"""

import logging
import time
import requests
from typing import List, Dict, Any, Optional
import numpy as np

from .config import EMBEDDING_SERVICE_CONFIG, EMBEDDING_FALLBACK_ENABLED
from embedding_generation.model_manager import EmbeddingModel

logger = logging.getLogger(__name__)


class EmbeddingServiceClient:
    """
    Client for interacting with the external embedding service.
    
    Provides fallback to local embedding generation if the service is unavailable.
    """
    
    def __init__(self):
        """Initialize the embedding service client."""
        self.base_url = EMBEDDING_SERVICE_CONFIG['base_url']
        self.timeout = EMBEDDING_SERVICE_CONFIG['timeout_seconds']
        self.retry_attempts = EMBEDDING_SERVICE_CONFIG['retry_attempts']
        self.async_processing = EMBEDDING_SERVICE_CONFIG['async_processing']
        
        # Fallback model
        self.fallback_model = None
        if EMBEDDING_FALLBACK_ENABLED:
            logger.info("Initializing shared fallback embedding model")
            from embedding_generation.model_manager import get_shared_embedding_model
            self.fallback_model = get_shared_embedding_model()
        
        self.service_enabled = EMBEDDING_SERVICE_CONFIG['enabled']
        
        logger.info(f"EmbeddingServiceClient initialized - Service: {self.service_enabled}, "
                   f"URL: {self.base_url}, Fallback: {EMBEDDING_FALLBACK_ENABLED}")
    
    def generate_embedding(
        self,
        text: str,
        source_id: str = None,
        source_type: str = None,
        force_update: bool = False
    ) -> np.ndarray:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            source_id: Optional source document ID
            source_type: Optional source document type
            force_update: Force re-embedding even if unchanged
        
        Returns:
            Embedding vector as numpy array
        """
        if not self.service_enabled:
            return self._fallback_generate_embedding(text)
        
        try:
            # Prepare request payload
            payload = {
                "source_id": source_id or f"doc_{int(time.time())}",
                "source_type": source_type or "unknown",
                "content": text,
                "force_update": force_update,
                "priority": "normal"
            }
            
            # Call embedding service
            if self.async_processing:
                # Async processing - get task result
                task_response = self._make_request(
                    "/embeddings/documents",
                    payload,
                    params={"async_processing": False}  # Force sync for fallback
                )
                
                if task_response.get("task_id"):
                    # Poll for result
                    return self._wait_for_task(task_response["task_id"])
                else:
                    raise Exception("No task ID returned")
            else:
                # Direct synchronous processing
                response = self._make_request(
                    "/embeddings/documents",
                    payload,
                    params={"async_processing": False}
                )
                
                if response.get("embedding_id"):
                    # Get the actual embedding from database
                    return self._get_embedding_from_db(response["embedding_id"])
                else:
                    raise Exception("No embedding ID returned")
                    
        except Exception as e:
            logger.warning(f"Embedding service call failed: {e}")
            if EMBEDDING_FALLBACK_ENABLED:
                return self._fallback_generate_embedding(text)
            else:
                raise Exception(f"Embedding service unavailable and fallback disabled: {e}")
    
    def generate_embeddings_batch(
        self,
        texts: List[str],
        source_ids: List[str] = None,
        source_types: List[str] = None,
        batch_id: str = None
    ) -> List[np.ndarray]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            source_ids: Optional list of source document IDs
            source_types: Optional list of source document types
            batch_id: Optional batch identifier
        
        Returns:
            List of embedding vectors
        """
        if not self.service_enabled:
            return self._fallback_generate_embeddings_batch(texts)
        
        try:
            # Prepare documents
            documents = []
            for i, text in enumerate(texts):
                documents.append({
                    "source_id": source_ids[i] if source_ids else f"doc_{int(time.time())}_{i}",
                    "source_type": source_types[i] if source_types else "unknown",
                    "content": text,
                    "priority": "normal"
                })
            
            # Prepare request payload
            payload = {
                "documents": documents,
                "batch_id": batch_id or f"batch_{int(time.time())}",
                "priority": "normal"
            }
            
            # Call embedding service
            response = self._make_request("/embeddings/batch", payload)
            
            if response.get("task_id"):
                # Wait for batch completion
                result = self._wait_for_task(response["task_id"])
                
                # Extract embeddings from results
                embeddings = []
                for doc_result in result.get("results", []):
                    if doc_result.get("embedding_id"):
                        embedding = self._get_embedding_from_db(doc_result["embedding_id"])
                        embeddings.append(embedding)
                    else:
                        # Use fallback for failed documents
                        if EMBEDDING_FALLBACK_ENABLED:
                            original_text = next(
                                (doc["content"] for doc in documents 
                                 if doc["source_id"] == doc_result.get("source_id")),
                                texts[i]  # Fallback to original text
                            )
                            embedding = self._fallback_generate_embedding(original_text)
                            embeddings.append(embedding)
                        else:
                            raise Exception(f"Failed to embed {doc_result.get('source_id')}")
                
                return embeddings
            else:
                raise Exception("No task ID returned for batch processing")
                
        except Exception as e:
            logger.warning(f"Batch embedding service call failed: {e}")
            if EMBEDDING_FALLBACK_ENABLED:
                return self._fallback_generate_embeddings_batch(texts)
            else:
                raise Exception(f"Embedding service unavailable and fallback disabled: {e}")
    
    def _make_request(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to embedding service."""
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(self.retry_attempts):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    params=params,
                    timeout=self.timeout,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    logger.warning(f"Embedding service request failed (attempt {attempt + 1}): {error_msg}")
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"Embedding service request failed (attempt {attempt + 1}): {e}")
            
            # Wait before retry
            if attempt < self.retry_attempts - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
        
        raise Exception(f"Failed to complete request after {self.retry_attempts} attempts")
    
    def _wait_for_task(self, task_id: str, timeout: int = 300) -> Dict[str, Any]:
        """Wait for async task completion."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = self._make_request(f"/tasks/{task_id}", {})
                
                if response.get("state") in ["completed", "failed"]:
                    return response
                elif response.get("state") == "retrying":
                    logger.info(f"Task {task_id} is retrying, waiting...")
                
                time.sleep(2)  # Poll every 2 seconds
                
            except Exception as e:
                logger.warning(f"Failed to check task status: {e}")
                time.sleep(5)
        
        raise TimeoutError(f"Task {task_id} did not complete within {timeout} seconds")
    
    def _get_embedding_from_db(self, embedding_id: str) -> np.ndarray:
        """Get embedding vector from database by ID."""
        try:
            # Import here to avoid circular imports
            from .postgres_client import PostgresVectorClient
            from .config import POSTGRES_CONFIG
            
            client = PostgresVectorClient(config=POSTGRES_CONFIG)
            
            # Query embedding by ID
            sql = """
                SELECT embedding 
                FROM embeddings 
                WHERE id = %s
            """
            
            conn = client.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, (embedding_id,))
                    result = cur.fetchone()
                    
                    if result and result[0]:
                        # Convert PostgreSQL vector to numpy array
                        embedding_str = result[0]
                        if isinstance(embedding_str, str):
                            # Remove brackets and split
                            embedding_str = embedding_str.strip('[]')
                            embedding_list = [float(x) for x in embedding_str.split(',')]
                            return np.array(embedding_list)
                        else:
                            return np.array(result[0])
                    else:
                        raise Exception(f"Embedding not found: {embedding_id}")
            finally:
                client.return_connection(conn)
                
        except Exception as e:
            logger.error(f"Failed to get embedding from database: {e}")
            raise
    
    def _fallback_generate_embedding(self, text: str) -> np.ndarray:
        """Fallback to local embedding generation."""
        if not self.fallback_model:
            raise Exception("Fallback embedding model not initialized")
        
        logger.debug("Using fallback embedding generation")
        return self.fallback_model.generate_embedding(text)
    
    def _fallback_generate_embeddings_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Fallback to local batch embedding generation."""
        if not self.fallback_model:
            raise Exception("Fallback embedding model not initialized")
        
        logger.debug("Using fallback batch embedding generation")
        return self.fallback_model.generate_embeddings_batch(texts)
    
    def health_check(self) -> Dict[str, Any]:
        """Check health of embedding service."""
        if not self.service_enabled:
            return {"status": "disabled", "message": "Embedding service is disabled"}
        
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}",
                    "message": response.text
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to connect to embedding service"
            }
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get information about the embedding service."""
        if not self.service_enabled:
            return {
                "enabled": False,
                "fallback_enabled": EMBEDDING_FALLBACK_ENABLED,
                "message": "Embedding service is disabled"
            }
        
        try:
            response = requests.get(f"{self.base_url}/", timeout=10)
            
            if response.status_code == 200:
                info = response.json()
                info.update({
                    "enabled": True,
                    "fallback_enabled": EMBEDDING_FALLBACK_ENABLED,
                    "base_url": self.base_url
                })
                return info
            else:
                return {
                    "enabled": True,
                    "fallback_enabled": EMBEDDING_FALLBACK_ENABLED,
                    "base_url": self.base_url,
                    "error": f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            return {
                "enabled": True,
                "fallback_enabled": EMBEDDING_FALLBACK_ENABLED,
                "base_url": self.base_url,
                "error": str(e)
            }


# Global client instance
_embedding_client = None


def get_embedding_client() -> EmbeddingServiceClient:
    """Get or create the global embedding client."""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingServiceClient()
    return _embedding_client