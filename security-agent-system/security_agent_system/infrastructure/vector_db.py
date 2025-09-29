"""ChromaDB vector database implementation."""
import asyncio
from typing import Dict, Any, List, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
import structlog
import uuid

from ..core.interfaces import IVectorDatabase
from ..core.config import settings

logger = structlog.get_logger()


class ChromaDatabase(IVectorDatabase):
    """ChromaDB vector database implementation for similarity search."""
    
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None
    ):
        self.host = host or settings.chroma_host
        self.port = port or settings.chroma_port
        self.client = None
        self.collections = {}
        
    async def connect(self) -> None:
        """Connect to ChromaDB."""
        try:
            # ChromaDB client setup
            self.client = chromadb.HttpClient(
                host=self.host,
                port=self.port,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Create default collections
            await self._create_collections()
            
            logger.info("Connected to ChromaDB",
                       host=self.host,
                       port=self.port)
                       
        except Exception as e:
            logger.error("Failed to connect to ChromaDB", error=str(e))
            # Fallback to in-memory client
            logger.warning("Falling back to in-memory ChromaDB")
            self.client = chromadb.Client()
            await self._create_collections()
            
    async def disconnect(self) -> None:
        """Disconnect from ChromaDB."""
        # ChromaDB doesn't require explicit disconnection
        logger.info("Disconnected from ChromaDB")
        
    async def insert(
        self,
        vector: List[float],
        metadata: Dict[str, Any],
        collection: str = "alerts"
    ) -> str:
        """Insert vector with metadata."""
        try:
            # Generate unique ID
            vector_id = str(uuid.uuid4())
            
            # Get collection
            coll = self.collections.get(collection)
            if not coll:
                raise ValueError(f"Collection {collection} not found")
                
            # Add to collection
            await asyncio.to_thread(
                coll.add,
                embeddings=[vector],
                metadatas=[metadata],
                ids=[vector_id]
            )
            
            logger.debug("Vector inserted",
                        collection=collection,
                        vector_id=vector_id)
                        
            return vector_id
            
        except Exception as e:
            logger.error("Failed to insert vector",
                        collection=collection,
                        error=str(e))
            raise
            
    async def search(
        self,
        vector: List[float],
        top_k: int = 10,
        collection: str = "alerts",
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors."""
        try:
            # Get collection
            coll = self.collections.get(collection)
            if not coll:
                raise ValueError(f"Collection {collection} not found")
                
            # Perform search
            results = await asyncio.to_thread(
                coll.query,
                query_embeddings=[vector],
                n_results=top_k,
                where=filters
            )
            
            # Format results
            formatted_results = []
            if results['ids'] and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    result = {
                        "id": results['ids'][0][i],
                        "score": 1 - results['distances'][0][i],  # Convert distance to similarity
                        "metadata": results['metadatas'][0][i] if results['metadatas'] else {}
                    }
                    formatted_results.append(result)
                    
            return formatted_results
            
        except Exception as e:
            logger.error("Vector search failed",
                        collection=collection,
                        error=str(e))
            return []
            
    async def delete(self, vector_id: str, collection: str = "alerts") -> bool:
        """Delete a vector by ID."""
        try:
            # Get collection
            coll = self.collections.get(collection)
            if not coll:
                raise ValueError(f"Collection {collection} not found")
                
            # Delete from collection
            await asyncio.to_thread(
                coll.delete,
                ids=[vector_id]
            )
            
            logger.debug("Vector deleted",
                        collection=collection,
                        vector_id=vector_id)
                        
            return True
            
        except Exception as e:
            logger.error("Failed to delete vector",
                        collection=collection,
                        vector_id=vector_id,
                        error=str(e))
            return False
            
    async def _create_collections(self) -> None:
        """Create default collections."""
        collections_config = {
            "alerts": {
                "metadata": {
                    "description": "Security alerts embeddings",
                    "created_at": "2024-01-01"
                }
            },
            "threats": {
                "metadata": {
                    "description": "Known threat patterns",
                    "created_at": "2024-01-01"
                }
            },
            "iocs": {
                "metadata": {
                    "description": "Indicators of compromise",
                    "created_at": "2024-01-01"
                }
            }
        }
        
        for name, config in collections_config.items():
            try:
                # Get or create collection
                collection = await asyncio.to_thread(
                    self.client.get_or_create_collection,
                    name=name,
                    metadata=config["metadata"]
                )
                self.collections[name] = collection
                
                logger.debug("Collection ready", collection=name)
                
            except Exception as e:
                logger.error("Failed to create collection",
                            collection=name,
                            error=str(e))
                            
    async def update_metadata(
        self,
        vector_id: str,
        metadata: Dict[str, Any],
        collection: str = "alerts"
    ) -> bool:
        """Update metadata for a vector."""
        try:
            coll = self.collections.get(collection)
            if not coll:
                raise ValueError(f"Collection {collection} not found")
                
            # Update metadata
            await asyncio.to_thread(
                coll.update,
                ids=[vector_id],
                metadatas=[metadata]
            )
            
            return True
            
        except Exception as e:
            logger.error("Failed to update metadata",
                        vector_id=vector_id,
                        error=str(e))
            return False
            
    async def bulk_insert(
        self,
        vectors: List[List[float]],
        metadatas: List[Dict[str, Any]],
        collection: str = "alerts"
    ) -> List[str]:
        """Bulk insert multiple vectors."""
        try:
            coll = self.collections.get(collection)
            if not coll:
                raise ValueError(f"Collection {collection} not found")
                
            # Generate IDs
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]
            
            # Bulk add
            await asyncio.to_thread(
                coll.add,
                embeddings=vectors,
                metadatas=metadatas,
                ids=ids
            )
            
            logger.info("Bulk insert completed",
                       collection=collection,
                       count=len(vectors))
                       
            return ids
            
        except Exception as e:
            logger.error("Bulk insert failed",
                        collection=collection,
                        count=len(vectors),
                        error=str(e))
            raise
            
    async def get_collection_stats(self, collection: str = "alerts") -> Dict[str, Any]:
        """Get statistics for a collection."""
        try:
            coll = self.collections.get(collection)
            if not coll:
                raise ValueError(f"Collection {collection} not found")
                
            # Get count
            count = await asyncio.to_thread(coll.count)
            
            return {
                "collection": collection,
                "count": count,
                "metadata": coll.metadata
            }
            
        except Exception as e:
            logger.error("Failed to get collection stats",
                        collection=collection,
                        error=str(e))
            return {"collection": collection, "count": 0, "error": str(e)}
