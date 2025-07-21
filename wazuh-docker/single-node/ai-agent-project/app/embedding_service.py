# === Google Gemini 嵌入服務模組 ===
#
# 本模組實現了穩定、高效的文字向量化服務，專門針對安全警報分析場景優化。
# 採用 Google Gemini text-embedding-004 模型，支援 768 維語義向量生成，
# 並整合 Matryoshka Representation Learning (MRL) 技術，允許彈性調整向量維度。
#
# 核心特性：
# 1. 非同步 API 調用，支援高並發處理
# 2. 指數退避重試機制，確保服務穩定性
# 3. 專門的安全警報內容處理邏輯
# 4. 完整的錯誤處理與監控日誌
# 5. 智能快取機制，提升效能並降低 API 成本
#
# 版本: 2.1 (Stage 4 Compatible with Caching)
# 更新: 2024年12月

import os
import logging
import asyncio
from typing import List, Optional, Dict, Any
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from .utils.text_chunking import SmartTextChunker, get_optimal_text, smart_chunk_text
from .utils.cache_manager import get_cache_manager, embedding_cache, batch_embedding_cache


# 獲取當前模組的日誌記錄器
logger = logging.getLogger(__name__)

class GeminiEmbeddingService:
    """
    Google Gemini 嵌入服務類別，提供企業級向量化能力
    
    本類別封裝了 Google Gemini Embedding API，提供穩定的文字向量化服務。
    特別針對 Wazuh 安全警報分析場景進行優化，支援批量處理、錯誤恢復、
    以及 Matryoshka Representation Learning (MRL) 技術。
    
    主要功能特性：
    - 🔄 非同步處理：支援高並發向量化請求
    - 🛡️ 錯誤恢復：指數退避重試機制確保 API 穩定性
    - 📏 彈性維度：MRL 技術支援 1-768 維度調整
    - 🎯 專門優化：針對安全警報內容的專門處理邏輯
    - 📊 監控日誌：完整的執行狀態與效能監控
    - 💾 智能快取：LRU+TTL 快取機制減少重複運算
    
    技術規格：
    - 模型：Google Gemini text-embedding-004
    - 預設維度：768 維 (可調整至 1-768)
    - 最大輸入長度：8,192 個 token
    - 支援語言：多語言 (包括繁體中文)
    
    Attributes:
        model_name (str): 使用的 Gemini 嵌入模型名稱
        dimension (Optional[int]): 向量維度 (1-768)，None 表示使用預設 768 維
        max_retries (int): API 調用失敗時的最大重試次數
        retry_delay (float): 重試間的初始延遲時間（秒）
        client (GoogleGenerativeAIEmbeddings): Google 嵌入服務客戶端實例
        cache_manager: 快取管理器實例
    """
    
    def __init__(self):
        """
        初始化 Gemini 嵌入服務實例
        
        從環境變數讀取配置參數，初始化 Google Gemini 客戶端。
        所有配置參數都有合理的預設值，確保在不同環境下的穩定運行。
        
        環境變數配置：
        - GOOGLE_API_KEY: Gemini API 金鑰（必要，從 Google AI Studio 獲取）
        - EMBEDDING_MODEL: 嵌入模型名稱（預設: models/text-embedding-004）
        - EMBEDDING_DIMENSION: 向量維度 1-768（預設: 768，None 表示使用模型預設）
        - EMBEDDING_MAX_RETRIES: 最大重試次數（預設: 3）
        - EMBEDDING_RETRY_DELAY: 初始重試延遲秒數（預設: 1.0）
        - EMBEDDING_CACHE_SIZE: 快取大小（預設: 1000）
        - EMBEDDING_CACHE_TTL: 快取 TTL（預設: 3600 秒）
        
        Raises:
            ValueError: 當 GOOGLE_API_KEY 環境變數未設定時
            ConnectionError: 當無法連接到 Google Gemini API 時
            
        使用範例:
            service = GeminiEmbeddingService()
            vector = await service.embed_alert_content(alert_data)
        """
        # 從環境變數讀取模型配置
        self.model_name = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")
        self.dimension = self._get_embedding_dimension()
        self.max_retries = int(os.getenv("EMBEDDING_MAX_RETRIES", "3"))
        self.retry_delay = float(os.getenv("EMBEDDING_RETRY_DELAY", "1.0"))
        
        # 批次處理配置
        self.batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "20"))
        self.max_concurrent_batches = int(os.getenv("EMBEDDING_MAX_CONCURRENT", "3"))
        
        # 文本分塊配置
        self.max_text_length = int(os.getenv("EMBEDDING_MAX_TEXT_LENGTH", "8000"))
        self.chunker = SmartTextChunker(max_chunk_size=self.max_text_length)
        
        # 初始化 Google Gemini 客戶端
        self.client = self._initialize_client()
        
        # 初始化快取服務
        self._cache_service = get_cache_service()

        
        # 記錄初始化完成狀態
        dimension_info = self.dimension or 768
        cache_stats = self.cache_manager.get_stats()
        
        logger.info(f"GeminiEmbeddingService 已成功初始化")
        logger.info(f"  🤖 模型: {self.model_name}")
        logger.info(f"  📏 維度: {dimension_info}")
        logger.info(f"  🔄 最大重試: {self.max_retries}")
        logger.info(f"  ⏱️ 重試延遲: {self.retry_delay}秒")
        logger.info(f"  💾 快取: {'啟用' if cache_stats['enabled'] else '停用'} (大小: {cache_stats['maxsize']}, TTL: {cache_stats['ttl']}秒)")
        
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
        將文檔列表轉換為向量列表（支援智能快取）
        
        此方法適用於批次處理多個文檔，會自動清理和預處理文字內容，
        確保輸入符合 API 要求。支援部分快取命中以提升效能。
        
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
            - 支援智能快取機制
        """
        if not texts:
            logger.warning("收到空的文字列表")
            return []
        
        # 使用快取裝飾器包裝的內部方法
        @batch_embedding_cache(self.cache_manager, prefix="doc_embed")
        async def _embed_documents_with_cache(self, texts: List[str]) -> List[List[float]]:
            # 清理和預處理文字
            cleaned_texts = []
            for text in texts:
                if not text or not text.strip():
                    cleaned_texts.append("empty content")
                else:
                    # 使用智能文本分塊替代硬截斷
                    cleaned_text = get_optimal_text(text.strip(), self.max_text_length)
                    cleaned_texts.append(cleaned_text)
            
            try:
                return await self._retry_embedding_operation(
                    self.client.aembed_documents, 
                    cleaned_texts
                )
            except Exception as e:
                logger.error(f"批次文檔向量化失敗: {str(e)}")
                raise
        
        return await _embed_documents_with_cache(self, texts)
    
    async def embed_query(self, text: str) -> List[float]:
        """

        將查詢文字轉換為向量（支援快取）
        
        此方法專門用於單一查詢文字的向量化，適合用於相似度搜尋場景。
        新增智能快取功能，減少重複查詢的API調用。

        
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
            - 支援智能快取以優化效能
        """
        if not text or not text.strip():
            logger.warning("收到空的查詢文字，使用預設值")
            text = "empty query"
        
        # 清理和預處理文字
        cleaned_text = get_optimal_text(text.strip(), self.max_text_length)
        
        # 如果有快取服務，使用快取
        if self._cache_service:
            import hashlib
            cache_key = f"embed:{hashlib.md5(cleaned_text.encode()).hexdigest()}"
            
            async def compute_embedding():
                return await self._retry_embedding_operation(
                    self.client.aembed_query, 
                    cleaned_text
                )
            
            try:
                vector = await self._cache_service.get_or_compute(
                    cache_key=cache_key,
                    compute_func=compute_embedding,
                    cache_type='ttl',
                    ttl_override=3600  # 1小時快取
                )
                logger.debug(f"查詢向量化成功（使用快取），維度: {len(vector) if vector else 0}")
                return vector
            except Exception as e:
                logger.error(f"查詢向量化失敗: {str(e)}")
                raise
        else:
            # 沒有快取服務，直接執行
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
            # 暫時停用快取以確保真實測試
            original_enabled = self.cache_manager.enabled
            self.cache_manager.enabled = False
            
            test_vector = await self.embed_query("connection test")
            
            # 恢復快取設定
            self.cache_manager.enabled = original_enabled
            
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
        專門用於向量化警報內容的方法（支援智能快取）
        
        此方法針對 Wazuh 警報結構進行特殊處理，提取並結構化關鍵資訊後
        進行向量化，優化針對警報特定內容的語意表示。整合快取機制以提升
        重複警報的處理效能。
        
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
            - 支援智能快取機制
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
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        獲取快取統計資訊
        
        Returns:
            Dict[str, Any]: 快取統計資訊，包含命中率、使用率等
        """
        return self.cache_manager.get_stats()
    
    def clear_cache(self) -> None:
        """
        清空快取
        
        在需要時手動清空所有快取項目，例如：
        - 模型更新後
        - 記憶體不足時
        - 測試環境重置
        """
        self.cache_manager.clear()
        logger.info("向量嵌入快取已清空") 