import os
import logging
import asyncio
from typing import List, Optional
from langchain_google_genai import GoogleGenerativeAIEmbeddings

logger = logging.getLogger(__name__)

class GeminiEmbeddingService:
    """Google Gemini Embedding 服務類，支援 MRL 技術和穩健的錯誤處理"""
    
    def __init__(self):
        self.model_name = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")
        self.dimension = self._get_embedding_dimension()
        self.max_retries = int(os.getenv("EMBEDDING_MAX_RETRIES", "3"))
        self.retry_delay = float(os.getenv("EMBEDDING_RETRY_DELAY", "1.0"))
        self.client = self._initialize_client()
        
    def _get_embedding_dimension(self) -> Optional[int]:
        """從環境變數讀取並驗證向量維度"""
        dim_str = os.getenv("EMBEDDING_DIMENSION")
        if not dim_str:
            logger.info("未指定 EMBEDDING_DIMENSION，使用模型預設維度 (768)")
            return None

        try:
            dimension = int(dim_str)
            # text-embedding-004 支援的維度範圍
            if not (1 <= dimension <= 768):
                logger.warning(f"維度須在 1-768 範圍內: {dimension}。將使用預設維度。")
                return None
            logger.info(f"使用 Matryoshka 向量維度: {dimension}")
            return dimension
        except ValueError:
            logger.warning(f"無效的維度設定: {dim_str}。將使用預設維度。")
            return None
    
    def _initialize_client(self) -> GoogleGenerativeAIEmbeddings:
        """初始化 Google Generative AI 嵌入客戶端"""
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("必須設定 GOOGLE_API_KEY 環境變數")

        try:
            # 根據是否指定維度使用不同初始化方式
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
            
            logger.info(f"成功初始化 Gemini Embedding 客戶端: {self.model_name}")
            return client
            
        except Exception as e:
            logger.error(f"初始化 Gemini Embedding 模型失敗: {str(e)}")
            raise
    
    async def _retry_with_backoff(self, func, *args, **kwargs):
        """帶退避機制的重試函式"""
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"嘗試 {attempt + 1} 失敗，{wait_time} 秒後重試: {str(e)}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"所有重試嘗試失敗: {str(e)}")
        
        raise last_exception
    
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """將文件列表轉換為向量，帶重試機制"""
        if not texts:
            logger.warning("嘗試對空文件列表進行向量化")
            return []
        
        try:
            logger.info(f"開始向量化 {len(texts)} 個文件")
            result = await self._retry_with_backoff(
                self.client.aembed_documents, texts
            )
            logger.info(f"成功向量化 {len(texts)} 個文件")
            return result
        except Exception as e:
            logger.error(f"文件向量化失敗: {str(e)}")
            raise
    
    async def embed_query(self, text: str) -> List[float]:
        """將查詢文本轉換為向量，帶重試機制"""
        if not text or not text.strip():
            logger.warning("嘗試對空字串進行向量化")
            raise ValueError("輸入文本不能為空")
        
        try:
            logger.debug(f"開始向量化查詢: {text[:50]}...")
            result = await self._retry_with_backoff(
                self.client.aembed_query, text
            )
            
            # 驗證返回的向量維度
            if self.dimension and len(result) != self.dimension:
                logger.warning(f"返回的向量維度 ({len(result)}) 與預期維度 ({self.dimension}) 不符")
            
            logger.debug(f"成功向量化查詢，維度: {len(result)}")
            return result
        except Exception as e:
            logger.error(f"查詢向量化失敗: {str(e)}")
            raise
    
    def get_embedding_info(self) -> dict:
        """獲取 embedding 服務的資訊"""
        return {
            "model_name": self.model_name,
            "dimension": self.dimension or 768,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay
        }
    
    async def test_connection(self) -> bool:
        """測試與 Gemini API 的連接"""
        try:
            test_text = "This is a test query for connection verification."
            await self.embed_query(test_text)
            logger.info("Gemini Embedding API 連接測試成功")
            return True
        except Exception as e:
            logger.error(f"Gemini Embedding API 連接測試失敗: {str(e)}")
            return False 