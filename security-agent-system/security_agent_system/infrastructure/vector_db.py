"""ChromaDB 向量資料庫實作。"""
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
    """用於相似性搜索的 ChromaDB 向量資料庫實作。"""
    
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
        """連接到 ChromaDB。"""
        try:
            # ChromaDB 客戶端設定
            self.client = chromadb.HttpClient(
                host=self.host,
                port=self.port,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # 建立預設集合
            await self._create_collections()
            
            logger.info("已連接到 ChromaDB",
                       host=self.host,
                       port=self.port)
                       
        except Exception as e:
            logger.error("連接到 ChromaDB 失敗", error=str(e))
            # 後備使用記憶體內客戶端
            logger.warning("後備使用記憶體內 ChromaDB")
            self.client = chromadb.Client()
            await self._create_collections()
            
    async def disconnect(self) -> None:
        """從 ChromaDB 斷開連接。"""
        # ChromaDB 不需要明確的斷開連接
        logger.info("已從 ChromaDB 斷開連接")
        
    async def insert(
        self,
        vector: List[float],
        metadata: Dict[str, Any],
        collection: str = "alerts"
    ) -> str:
        """插入帶有元資料的向量。"""
        try:
            # 產生唯一 ID
            vector_id = str(uuid.uuid4())
            
            # 獲取集合
            coll = self.collections.get(collection)
            if not coll:
                raise ValueError(f"找不到集合 {collection}")
                
            # 新增至集合
            await asyncio.to_thread(
                coll.add,
                embeddings=[vector],
                metadatas=[metadata],
                ids=[vector_id]
            )
            
            logger.debug("已插入向量",
                        collection=collection,
                        vector_id=vector_id)
                        
            return vector_id
            
        except Exception as e:
            logger.error("插入向量失敗",
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
        """搜索相似的向量。"""
        try:
            # 獲取集合
            coll = self.collections.get(collection)
            if not coll:
                raise ValueError(f"找不到集合 {collection}")
                
            # 執行搜索
            results = await asyncio.to_thread(
                coll.query,
                query_embeddings=[vector],
                n_results=top_k,
                where=filters
            )
            
            # 格式化結果
            formatted_results = []
            if results['ids'] and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    result = {
                        "id": results['ids'][0][i],
                        "score": 1 - results['distances'][0][i],  # 將距離轉換為相似度
                        "metadata": results['metadatas'][0][i] if results['metadatas'] else {}
                    }
                    formatted_results.append(result)
                    
            return formatted_results
            
        except Exception as e:
            logger.error("向量搜索失敗",
                        collection=collection,
                        error=str(e))
            return []
            
    async def delete(self, vector_id: str, collection: str = "alerts") -> bool:
        """按 ID 刪除向量。"""
        try:
            # 獲取集合
            coll = self.collections.get(collection)
            if not coll:
                raise ValueError(f"找不到集合 {collection}")
                
            # 從集合中刪除
            await asyncio.to_thread(
                coll.delete,
                ids=[vector_id]
            )
            
            logger.debug("已刪除向量",
                        collection=collection,
                        vector_id=vector_id)
                        
            return True
            
        except Exception as e:
            logger.error("刪除向量失敗",
                        collection=collection,
                        vector_id=vector_id,
                        error=str(e))
            return False
            
    async def _create_collections(self) -> None:
        """建立預設集合。"""
        collections_config = {
            "alerts": {
                "metadata": {
                    "description": "安全警報嵌入",
                    "created_at": "2024-01-01"
                }
            },
            "threats": {
                "metadata": {
                    "description": "已知威脅模式",
                    "created_at": "2024-01-01"
                }
            },
            "iocs": {
                "metadata": {
                    "description": "入侵指標",
                    "created_at": "2024-01-01"
                }
            }
        }
        
        for name, config in collections_config.items():
            try:
                # 獲取或建立集合
                collection = await asyncio.to_thread(
                    self.client.get_or_create_collection,
                    name=name,
                    metadata=config["metadata"]
                )
                self.collections[name] = collection
                
                logger.debug("集合已就緒", collection=name)
                
            except Exception as e:
                logger.error("建立集合失敗",
                            collection=name,
                            error=str(e))
                            
    async def update_metadata(
        self,
        vector_id: str,
        metadata: Dict[str, Any],
        collection: str = "alerts"
    ) -> bool:
        """更新向量的元資料。"""
        try:
            coll = self.collections.get(collection)
            if not coll:
                raise ValueError(f"找不到集合 {collection}")
                
            # 更新元資料
            await asyncio.to_thread(
                coll.update,
                ids=[vector_id],
                metadatas=[metadata]
            )
            
            return True
            
        except Exception as e:
            logger.error("更新元資料失敗",
                        vector_id=vector_id,
                        error=str(e))
            return False
            
    async def bulk_insert(
        self,
        vectors: List[List[float]],
        metadatas: List[Dict[str, Any]],
        collection: str = "alerts"
    ) -> List[str]:
        """批次插入多個向量。"""
        try:
            coll = self.collections.get(collection)
            if not coll:
                raise ValueError(f"找不到集合 {collection}")
                
            # 產生 ID
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]
            
            # 批次新增
            await asyncio.to_thread(
                coll.add,
                embeddings=vectors,
                metadatas=metadatas,
                ids=ids
            )
            
            logger.info("批次插入完成",
                       collection=collection,
                       count=len(vectors))
                       
            return ids
            
        except Exception as e:
            logger.error("批次插入失敗",
                        collection=collection,
                        count=len(vectors),
                        error=str(e))
            raise
            
    async def get_collection_stats(self, collection: str = "alerts") -> Dict[str, Any]:
        """獲取集合的統計資料。"""
        try:
            coll = self.collections.get(collection)
            if not coll:
                raise ValueError(f"找不到集合 {collection}")
                
            # 獲取計數
            count = await asyncio.to_thread(coll.count)
            
            return {
                "collection": collection,
                "count": count,
                "metadata": coll.metadata
            }
            
        except Exception as e:
            logger.error("獲取集合統計資料失敗",
                        collection=collection,
                        error=str(e))
            return {"collection": collection, "count": 0, "error": str(e)}