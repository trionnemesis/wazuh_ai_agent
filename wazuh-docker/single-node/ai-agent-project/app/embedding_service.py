import os
import logging
import asyncio
from typing import List, Optional
from langchain_google_genai import GoogleGenerativeAIEmbeddings

logger = logging.getLogger(__name__)

class GeminiEmbeddingService:
    """Google Gemini Embedding 服務類，支援 MRL 技術和穩定的向量化"""
    
    def __init__(self):
        self.model_name = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")
        self.dimension = self._get_embedding_dimension()
        self.max_retries = int(os.getenv("EMBEDDING_MAX_RETRIES", "3"))
        self.retry_delay = float(os.getenv("EMBEDDING_RETRY_DELAY", "1.0"))
        self.client = self._initialize_client()
        logger.info(f"GeminiEmbeddingService 初始化完成 - 模型: {self.model_name}, 維度: {self.dimension}")
        
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
                    dimensions=self.dimension  # 正確參數名
                )
            else:
                client = GoogleGenerativeAIEmbeddings(
                    model=self.model_name,
                    google_api_key=api_key,
                    task_type="retrieval_document"
                )
            
            logger.info("Gemini Embedding 客戶端初始化成功")
            return client
            
        except Exception as e:
            logger.error(f"初始化 Gemini Embedding 模型失敗: {str(e)}")
            raise
    
    async def _retry_embedding_operation(self, operation, *args, **kwargs):
        """帶重試機制的向量化操作"""
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # 指數退避
                    logger.warning(f"向量化操作失敗 (嘗試 {attempt + 1}/{self.max_retries}): {str(e)}")
                    logger.info(f"等待 {wait_time} 秒後重試...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"向量化操作在 {self.max_retries} 次嘗試後仍然失敗")
        
        raise last_exception
    
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """將文件列表轉換為向量"""
        if not texts:
            logger.warning("收到空的文本列表")
            return []
        
        # 清理和預處理文本
        cleaned_texts = []
        for text in texts:
            if not text or not text.strip():
                cleaned_texts.append("空白內容")
            else:
                # 限制文本長度以避免 API 限制
                cleaned_text = text.strip()[:8000]  # Gemini API 通常有文本長度限制
                cleaned_texts.append(cleaned_text)
        
        try:
            return await self._retry_embedding_operation(
                self.client.aembed_documents, 
                cleaned_texts
            )
        except Exception as e:
            logger.error(f"批次文件向量化失敗: {str(e)}")
            raise
    
    async def embed_query(self, text: str) -> List[float]:
        """將查詢文本轉換為向量"""
        if not text or not text.strip():
            logger.warning("收到空的查詢文本，使用預設文本")
            text = "空白查詢"
        
        # 清理和預處理文本
        cleaned_text = text.strip()[:8000]  # 限制文本長度
        
        try:
            vector = await self._retry_embedding_operation(
                self.client.aembed_query, 
                cleaned_text
            )
            
            logger.debug(f"查詢向量化成功，維度: {len(vector) if vector else 0}")
            return vector
            
        except Exception as e:
            logger.error(f"查詢向量化失敗: {str(e)}")
            raise
    
    def get_vector_dimension(self) -> int:
        """取得實際向量維度"""
        return self.dimension if self.dimension else 768
    
    async def test_connection(self) -> bool:
        """測試 embedding 服務連線"""
        try:
            test_vector = await self.embed_query("connection test")
            if test_vector and len(test_vector) > 0:
                logger.info(f"Embedding 服務連線測試成功，向量維度: {len(test_vector)}")
                return True
            else:
                logger.error("Embedding 服務測試失敗: 返回空向量")
                return False
        except Exception as e:
            logger.error(f"Embedding 服務連線測試失敗: {str(e)}")
            return False
    
    async def embed_alert_content(self, alert_source: dict) -> List[float]:
        """專門用於警報內容的向量化方法"""
        try:
            rule = alert_source.get('rule', {})
            agent = alert_source.get('agent', {})
            data = alert_source.get('data', {})
            
            # 構建結構化的警報描述
            alert_components = []
            
            # 基本資訊
            if rule.get('description'):
                alert_components.append(f"規則描述: {rule['description']}")
            
            if rule.get('level'):
                alert_components.append(f"警報等級: {rule['level']}")
            
            if agent.get('name'):
                alert_components.append(f"主機名稱: {agent['name']}")
            
            # 規則詳細資訊
            if rule.get('id'):
                alert_components.append(f"規則ID: {rule['id']}")
            
            if rule.get('groups'):
                groups = ', '.join(rule['groups'])
                alert_components.append(f"規則群組: {groups}")
            
            # 資料內容 (如果有的話)
            if data:
                # 提取重要的資料欄位
                important_fields = ['srcip', 'dstip', 'srcport', 'dstport', 'protocol', 'url', 'user', 'command']
                for field in important_fields:
                    if field in data:
                        alert_components.append(f"{field}: {data[field]}")
            
            # 組合成完整描述
            alert_text = ' | '.join(alert_components)
            
            if not alert_text.strip():
                alert_text = "未知警報類型"
            
            logger.debug(f"構建的警報文本: {alert_text[:200]}...")
            
            return await self.embed_query(alert_text)
            
        except Exception as e:
            logger.error(f"警報內容向量化失敗: {str(e)}")
            # 回退到基本描述
            fallback_text = f"Rule: {alert_source.get('rule', {}).get('description', 'Unknown')}"
            return await self.embed_query(fallback_text) 