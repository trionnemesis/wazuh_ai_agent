import os
import logging
from typing import List, Optional
from langchain_google_genai import GoogleGenerativeAIEmbeddings

logger = logging.getLogger(__name__)

class GeminiEmbeddingService:
    """Google Gemini Embedding 服務類，支援 MRL 技術"""
    
    def __init__(self):
        self.model_name = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")
        self.dimension = self._get_embedding_dimension()
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
                return GoogleGenerativeAIEmbeddings(
                    model=self.model_name,
                    google_api_key=api_key,
                    task_type="retrieval_document",
                    dimensions=self.dimension  # 正確參數名
                )
            else:
                return GoogleGenerativeAIEmbeddings(
                    model=self.model_name,
                    google_api_key=api_key,
                    task_type="retrieval_document"
                )
        except Exception as e:
            logger.error(f"初始化 Gemini Embedding 模型失敗: {str(e)}")
            raise
    
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """將文件列表轉換為向量"""
        try:
            return await self.client.aembed_documents(texts)
        except Exception as e:
            logger.error(f"文件向量化失敗: {str(e)}")
            raise
    
    async def embed_query(self, text: str) -> List[float]:
        """將查詢文本轉換為向量"""
        try:
            return await self.client.aembed_query(text)
        except Exception as e:
            logger.error(f"查詢向量化失敗: {str(e)}")
            raise 