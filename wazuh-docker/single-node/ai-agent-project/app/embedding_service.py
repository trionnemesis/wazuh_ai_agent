import os
import logging
import asyncio
from typing import List, Optional, Dict, Any
from langchain_google_genai import GoogleGenerativeAIEmbeddings

logger = logging.getLogger(__name__)

class GeminiEmbeddingService:
    """
    Google Gemini Embedding Service class with MRL support and stable vectorization.
    
    This service provides async methods for converting text to vectors using Google's
    Gemini Embedding API with built-in error handling and retry mechanisms.
    """
    
    def __init__(self):
        """
        Initialize the Gemini Embedding Service.
        
        Reads configuration from environment variables:
        - GOOGLE_API_KEY: Required API key for Gemini
        - EMBEDDING_MODEL: Model name (default: models/text-embedding-004)
        - EMBEDDING_DIMENSION: Vector dimensions 1-768 (default: 768)
        - EMBEDDING_MAX_RETRIES: Maximum retry attempts (default: 3)
        - EMBEDDING_RETRY_DELAY: Initial retry delay in seconds (default: 1.0)
        """
        self.model_name = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")
        self.dimension = self._get_embedding_dimension()
        self.max_retries = int(os.getenv("EMBEDDING_MAX_RETRIES", "3"))
        self.retry_delay = float(os.getenv("EMBEDDING_RETRY_DELAY", "1.0"))
        self.client = self._initialize_client()
        logger.info(f"GeminiEmbeddingService initialized - Model: {self.model_name}, Dimensions: {self.dimension or 768}")
        
    def _get_embedding_dimension(self) -> Optional[int]:
        """
        Read and validate vector dimensions from environment variables.
        
        Returns:
            Optional[int]: Validated dimension or None for default
        """
        dim_str = os.getenv("EMBEDDING_DIMENSION")
        if not dim_str:
            logger.info("EMBEDDING_DIMENSION not specified, using model default (768)")
            return None

        try:
            dimension = int(dim_str)
            # text-embedding-004 supports dimensions 1-768
            if not (1 <= dimension <= 768):
                logger.warning(f"Dimension must be in range 1-768: {dimension}. Using default.")
                return None
            logger.info(f"Using Matryoshka vector dimension: {dimension}")
            return dimension
        except ValueError:
            logger.warning(f"Invalid dimension setting: {dim_str}. Using default.")
            return None
    
    def _initialize_client(self) -> GoogleGenerativeAIEmbeddings:
        """
        Initialize Google Generative AI Embeddings client.
        
        Returns:
            GoogleGenerativeAIEmbeddings: Configured client instance
            
        Raises:
            ValueError: If GOOGLE_API_KEY is not set
        """
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable must be set")

        try:
            # Initialize with or without dimension specification
            if self.dimension:
                client = GoogleGenerativeAIEmbeddings(
                    model=self.model_name,
                    google_api_key=api_key,
                    task_type="retrieval_document",
                    dimensions=self.dimension
                )
            else:
                client = GoogleGenerativeAIEmbeddings(
                    model=self.model_name,
                    google_api_key=api_key,
                    task_type="retrieval_document"
                )
            
            logger.info("Gemini Embedding client initialized successfully")
            return client
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini Embedding model: {str(e)}")
            raise
    
    async def _retry_embedding_operation(self, operation, *args, **kwargs):
        """
        Execute embedding operations with retry mechanism using exponential backoff.
        
        Args:
            operation: The async operation to execute
            *args: Positional arguments for the operation
            **kwargs: Keyword arguments for the operation
            
        Returns:
            Result of the operation
            
        Raises:
            Exception: The last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Embedding operation failed (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Embedding operation failed after {self.max_retries} attempts")
        
        raise last_exception
    
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Convert a list of documents to vectors.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of corresponding embedding vectors
            
        Raises:
            Exception: If vectorization fails after all retries
        """
        if not texts:
            logger.warning("Received empty text list")
            return []
        
        # Clean and preprocess texts
        cleaned_texts = []
        for text in texts:
            if not text or not text.strip():
                cleaned_texts.append("empty content")
            else:
                # Limit text length to avoid API limits
                cleaned_text = text.strip()[:8000]  # Gemini API usually has text length limits
                cleaned_texts.append(cleaned_text)
        
        try:
            return await self._retry_embedding_operation(
                self.client.aembed_documents, 
                cleaned_texts
            )
        except Exception as e:
            logger.error(f"Batch document vectorization failed: {str(e)}")
            raise
    
    async def embed_query(self, text: str) -> List[float]:
        """
        Convert query text to a vector.
        
        Args:
            text: Text string to embed
            
        Returns:
            Vector representation of the text
            
        Raises:
            Exception: If vectorization fails after all retries
        """
        if not text or not text.strip():
            logger.warning("Received empty query text, using default")
            text = "empty query"
        
        # Clean and preprocess text
        cleaned_text = text.strip()[:8000]  # Limit text length
        
        try:
            vector = await self._retry_embedding_operation(
                self.client.aembed_query, 
                cleaned_text
            )
            
            logger.debug(f"Query vectorization successful, dimensions: {len(vector) if vector else 0}")
            return vector
            
        except Exception as e:
            logger.error(f"Query vectorization failed: {str(e)}")
            raise
    
    def get_vector_dimension(self) -> int:
        """
        Get the actual vector dimension.
        
        Returns:
            int: Vector dimension (768 if using default)
        """
        return self.dimension if self.dimension else 768
    
    async def test_connection(self) -> bool:
        """
        Test embedding service connection.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            test_vector = await self.embed_query("connection test")
            if test_vector and len(test_vector) > 0:
                logger.info(f"Embedding service connection test successful, vector dimension: {len(test_vector)}")
                return True
            else:
                logger.error("Embedding service test failed: returned empty vector")
                return False
        except Exception as e:
            logger.error(f"Embedding service connection test failed: {str(e)}")
            return False
    
    async def embed_alert_content(self, alert_source: Dict[str, Any]) -> List[float]:
        """
        Specialized method for vectorizing alert content.
        
        This method extracts and structures key information from Wazuh alerts
        before converting to vectors, optimizing for alert-specific content.
        
        Args:
            alert_source: Alert source data from OpenSearch
            
        Returns:
            Vector representation of the alert content
            
        Raises:
            Exception: If vectorization fails
        """
        try:
            rule = alert_source.get('rule', {})
            agent = alert_source.get('agent', {})
            data = alert_source.get('data', {})
            
            # Build structured alert description
            alert_components = []
            
            # Basic information
            if rule.get('description'):
                alert_components.append(f"Rule Description: {rule['description']}")
            
            if rule.get('level'):
                alert_components.append(f"Alert Level: {rule['level']}")
            
            if agent.get('name'):
                alert_components.append(f"Host Name: {agent['name']}")
            
            # Rule details
            if rule.get('id'):
                alert_components.append(f"Rule ID: {rule['id']}")
            
            if rule.get('groups'):
                groups = ', '.join(rule['groups'])
                alert_components.append(f"Rule Groups: {groups}")
            
            # Data content (if available)
            if data:
                # Extract important data fields
                important_fields = ['srcip', 'dstip', 'srcport', 'dstport', 'protocol', 'url', 'user', 'command']
                for field in important_fields:
                    if field in data and data[field]:
                        alert_components.append(f"{field}: {data[field]}")
            
            # Additional context
            if alert_source.get('location'):
                alert_components.append(f"Location: {alert_source['location']}")
                
            if alert_source.get('decoder') and alert_source['decoder'].get('name'):
                alert_components.append(f"Decoder: {alert_source['decoder']['name']}")
            
            # Combine into complete description
            alert_text = ' | '.join(alert_components)
            
            if not alert_text.strip():
                alert_text = "Unknown alert type"
            
            logger.debug(f"Built alert text: {alert_text[:200]}...")
            
            return await self.embed_query(alert_text)
            
        except Exception as e:
            logger.error(f"Alert content vectorization failed: {str(e)}")
            # Fallback to basic description
            fallback_text = f"Rule: {alert_source.get('rule', {}).get('description', 'Unknown')}"
            logger.info(f"Using fallback text: {fallback_text}")
            return await self.embed_query(fallback_text) 