import os
import logging
import asyncio
from typing import List, Optional, Dict, Any
from langchain_google_genai import GoogleGenerativeAIEmbeddings

logger = logging.getLogger(__name__)

class GeminiEmbeddingService:
    """
    Google Gemini 嵌入服務類別，支援 MRL 技術與穩定向量化
    
    此服務提供非同步方法，使用 Google Gemini Embedding API 將文字轉換為向量，
    內建錯誤處理與重試機制，特別針對 Wazuh 安全警報分析場景優化。
    
    主要特性：
    - 支援 Matryoshka Representation Learning (MRL) 可調向量維度
    - 指數退避重試機制確保 API 穩定性
    - 專門的警報內容向量化方法
    - 完整的錯誤處理與日誌記錄
    
    Attributes:
        model_name (str): 使用的 Gemini 嵌入模型名稱
        dimension (Optional[int]): 向量維度 (1-768)，None 表示使用預設值
        max_retries (int): 最大重試次數
        retry_delay (float): 初始重試延遲時間（秒）
        client (GoogleGenerativeAIEmbeddings): Google 嵌入服務客戶端
    """
    
    def __init__(self):
        """
        初始化 Gemini 嵌入服務
        
        從環境變數讀取配置：
        - GOOGLE_API_KEY: Gemini API 金鑰（必要）
        - EMBEDDING_MODEL: 模型名稱（預設: models/text-embedding-004）
        - EMBEDDING_DIMENSION: 向量維度 1-768（預設: 768）
        - EMBEDDING_MAX_RETRIES: 最大重試次數（預設: 3）
        - EMBEDDING_RETRY_DELAY: 初始重試延遲秒數（預設: 1.0）
        
        Raises:
            ValueError: 當 GOOGLE_API_KEY 未設定時
        """
        self.model_name = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")
        self.dimension = self._get_embedding_dimension()
        self.max_retries = int(os.getenv("EMBEDDING_MAX_RETRIES", "3"))
        self.retry_delay = float(os.getenv("EMBEDDING_RETRY_DELAY", "1.0"))
        self.client = self._initialize_client()
        logger.info(f"GeminiEmbeddingService 已初始化 - 模型: {self.model_name}, 維度: {self.dimension or 768}")
        
    def _get_embedding_dimension(self) -> Optional[int]:
        """
        從環境變數讀取並驗證向量維度設定
        
        支援 Matryoshka Representation Learning，允許使用較小的向量維度
        以獲得更好的效能，同時保持語意準確性。
        
        Returns:
            Optional[int]: 驗證後的維度值，若無效則返回 None 使用預設值
            
        Note:
            text-embedding-004 模型支援 1-768 維度範圍
        """
        dim_str = os.getenv("EMBEDDING_DIMENSION")
        if not dim_str:
            logger.info("EMBEDDING_DIMENSION 未指定，使用模型預設值 (768)")
            return None

        try:
            dimension = int(dim_str)
            # text-embedding-004 支援 1-768 維度
            if not (1 <= dimension <= 768):
                logger.warning(f"維度必須在 1-768 範圍內: {dimension}。使用預設值")
                return None
            logger.info(f"使用 Matryoshka 向量維度: {dimension}")
            return dimension
        except ValueError:
            logger.warning(f"無效的維度設定: {dim_str}。使用預設值")
            return None
    
    def _initialize_client(self) -> GoogleGenerativeAIEmbeddings:
        """
        初始化 Google Generative AI 嵌入客戶端
        
        根據是否指定維度來配置客戶端，使用文件檢索任務類型以獲得最佳效能。
        
        Returns:
            GoogleGenerativeAIEmbeddings: 配置完成的客戶端實例
            
        Raises:
            ValueError: 當 GOOGLE_API_KEY 未設定時
            Exception: 客戶端初始化失敗時
        """
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY 環境變數必須設定")

        try:
            # 根據是否指定維度來初始化客戶端
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
            
            logger.info("Gemini 嵌入客戶端初始化成功")
            return client
            
        except Exception as e:
            logger.error(f"初始化 Gemini 嵌入模型失敗: {str(e)}")
            raise
    
    async def _retry_embedding_operation(self, operation, *args, **kwargs):
        """
        使用指數退避演算法執行嵌入操作的重試機制
        
        此方法確保在面對暫時性 API 錯誤時的系統穩定性，透過指數退避
        避免對 API 服務造成過度負載。
        
        Args:
            operation: 要執行的非同步操作函式
            *args: 操作的位置參數
            **kwargs: 操作的關鍵字參數
            
        Returns:
            操作的執行結果
            
        Raises:
            Exception: 所有重試失敗後拋出最後一次的例外
            
        Note:
            - 使用指數退避：第 n 次重試延遲 = retry_delay * (2^n)
            - 每次重試前會記錄警告日誌
            - 最終失敗時記錄錯誤日誌
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # 指數退避
                    logger.warning(f"嵌入操作失敗 (嘗試 {attempt + 1}/{self.max_retries}): {str(e)}")
                    logger.info(f"等待 {wait_time} 秒後重試...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"嵌入操作在 {self.max_retries} 次嘗試後失敗")
        
        raise last_exception
    
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        將文檔列表轉換為向量列表
        
        此方法適用於批次處理多個文檔，會自動清理和預處理文字內容，
        確保輸入符合 API 要求。
        
        Args:
            texts (List[str]): 要嵌入的文字字串列表
            
        Returns:
            List[List[float]]: 對應的嵌入向量列表
            
        Raises:
            Exception: 向量化失敗時拋出例外
            
        Note:
            - 空文字會被替換為 "empty content"
            - 文字會被截斷至 8000 字符以符合 API 限制
            - 使用重試機制確保穩定性
        """
        if not texts:
            logger.warning("收到空的文字列表")
            return []
        
        # 清理和預處理文字
        cleaned_texts = []
        for text in texts:
            if not text or not text.strip():
                cleaned_texts.append("empty content")
            else:
                # 限制文字長度以避免 API 限制
                cleaned_text = text.strip()[:8000]  # Gemini API 通常有文字長度限制
                cleaned_texts.append(cleaned_text)
        
        try:
            return await self._retry_embedding_operation(
                self.client.aembed_documents, 
                cleaned_texts
            )
        except Exception as e:
            logger.error(f"批次文檔向量化失敗: {str(e)}")
            raise
    
    async def embed_query(self, text: str) -> List[float]:
        """
        將查詢文字轉換為向量
        
        此方法專門用於單一查詢文字的向量化，適合用於相似度搜尋場景。
        
        Args:
            text (str): 要嵌入的文字字串
            
        Returns:
            List[float]: 文字的向量表示
            
        Raises:
            Exception: 向量化失敗時拋出例外
            
        Note:
            - 空文字會被替換為 "empty query"
            - 文字會被截斷至 8000 字符以符合 API 限制
            - 包含向量維度驗證日誌
        """
        if not text or not text.strip():
            logger.warning("收到空的查詢文字，使用預設值")
            text = "empty query"
        
        # 清理和預處理文字
        cleaned_text = text.strip()[:8000]  # 限制文字長度
        
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
        """
        取得實際向量維度
        
        Returns:
            int: 向量維度（若使用預設值則為 768）
        """
        return self.dimension if self.dimension else 768
    
    async def test_connection(self) -> bool:
        """
        測試嵌入服務連線狀態
        
        透過執行一個簡單的向量化操作來驗證服務是否正常運作。
        
        Returns:
            bool: 連線成功返回 True，失敗返回 False
            
        Note:
            - 使用簡短測試文字以最小化 API 消耗
            - 驗證返回向量的有效性
            - 記錄詳細的測試結果
        """
        try:
            test_vector = await self.embed_query("connection test")
            if test_vector and len(test_vector) > 0:
                logger.info(f"嵌入服務連線測試成功，向量維度: {len(test_vector)}")
                return True
            else:
                logger.error("嵌入服務測試失敗: 返回空向量")
                return False
        except Exception as e:
            logger.error(f"嵌入服務連線測試失敗: {str(e)}")
            return False
    
    async def embed_alert_content(self, alert_source: Dict[str, Any]) -> List[float]:
        """
        專門用於向量化警報內容的方法
        
        此方法針對 Wazuh 警報結構進行特殊處理，提取並結構化關鍵資訊後
        進行向量化，優化針對警報特定內容的語意表示。
        
        處理的警報欄位包括：
        - 規則描述與等級
        - 主機名稱與位置
        - 關鍵資料欄位（IP、端口、使用者等）
        - 解碼器資訊
        
        Args:
            alert_source (Dict[str, Any]): 來自 OpenSearch 的警報來源資料
            
        Returns:
            List[float]: 警報內容的向量表示
            
        Raises:
            Exception: 向量化失敗時，會嘗試使用後備文字
            
        Note:
            - 結構化提取重要警報欄位
            - 自動處理缺失欄位
            - 包含後備機制確保系統穩定性
        """
        try:
            rule = alert_source.get('rule', {})
            agent = alert_source.get('agent', {})
            data = alert_source.get('data', {})
            
            # 建構結構化警報描述
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
                alert_components.append(f"規則 ID: {rule['id']}")
            
            if rule.get('groups'):
                groups = ', '.join(rule['groups'])
                alert_components.append(f"規則群組: {groups}")
            
            # 資料內容（如果可用）
            if data:
                # 提取重要的資料欄位
                important_fields = ['srcip', 'dstip', 'srcport', 'dstport', 'protocol', 'url', 'user', 'command']
                for field in important_fields:
                    if field in data and data[field]:
                        alert_components.append(f"{field}: {data[field]}")
            
            # 額外上下文
            if alert_source.get('location'):
                alert_components.append(f"位置: {alert_source['location']}")
                
            if alert_source.get('decoder') and alert_source['decoder'].get('name'):
                alert_components.append(f"解碼器: {alert_source['decoder']['name']}")
            
            # 組合成完整描述
            alert_text = ' | '.join(alert_components)
            
            if not alert_text.strip():
                alert_text = "未知警報類型"
            
            logger.debug(f"建構警報文字: {alert_text[:200]}...")
            
            return await self.embed_query(alert_text)
            
        except Exception as e:
            logger.error(f"警報內容向量化失敗: {str(e)}")
            # 後備至基本描述
            fallback_text = f"規則: {alert_source.get('rule', {}).get('description', '未知')}"
            logger.info(f"使用後備文字: {fallback_text}")
            return await self.embed_query(fallback_text) 