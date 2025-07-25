"""
單元測試：Services 和 Core 模組
使用 Mock 模擬外部 API 和資料庫依賴
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

# 導入要測試的模組
from services.embedding_service import GeminiEmbeddingService
from services.graph_service import Neo4jGraphService
from services.retrieval_service import RetrievalService
from services.llm_service import LLMService
from core.graph_entity_extractor import GraphEntityExtractor
from core.graph_relationship_builder import GraphRelationshipBuilder
from core.graph_query_engine import GraphQueryEngine
from utils.text_chunking import SmartTextChunker, get_optimal_text, smart_chunk_text
from utils.error_handling import OpenSearchError, Neo4jError, LLMError, EmbeddingError


class TestGeminiEmbeddingService:
    """Gemini 嵌入服務單元測試"""
    
    @pytest.fixture
    def mock_env_vars(self):
        """模擬環境變數"""
        with patch.dict('os.environ', {
            'GOOGLE_API_KEY': 'test_api_key',
            'EMBEDDING_MODEL': 'models/text-embedding-004',
            'EMBEDDING_DIMENSION': '768',
            'EMBEDDING_MAX_RETRIES': '3',
            'EMBEDDING_RETRY_DELAY': '1.0',
            'EMBEDDING_MAX_TEXT_LENGTH': '8000'
        }):
            yield
    
    @pytest.fixture
    def mock_client(self):
        """模擬 Gemini 客戶端"""
        mock_client = Mock()
        mock_client.aembed_documents = AsyncMock()
        mock_client.aembed_query = AsyncMock()
        return mock_client
    
    @pytest.mark.unit
    @pytest.mark.mock
    def test_initialization(self, mock_env_vars, mock_client):
        """測試服務初始化"""
        with patch('app.services.embedding_service.GoogleGenerativeAIEmbeddings', return_value=mock_client):
            service = GeminiEmbeddingService()
            
            assert service.model_name == 'models/text-embedding-004'
            assert service.dimension == 768
            assert service.max_retries == 3
            assert service.retry_delay == 1.0
            assert service.max_text_length == 8000
    
    @pytest.mark.unit
    @pytest.mark.mock
    def test_embed_query_success(self, mock_env_vars, mock_client):
        """測試查詢向量化成功"""
        mock_client.aembed_query.return_value = [0.1, 0.2, 0.3] * 256  # 768維向量
        
        with patch('app.services.embedding_service.GoogleGenerativeAIEmbeddings', return_value=mock_client):
            service = GeminiEmbeddingService()
            
            async def test():
                result = await service.embed_query("test query")
                assert len(result) == 768
                assert all(isinstance(x, float) for x in result)
            
            asyncio.run(test())
    
    @pytest.mark.unit
    @pytest.mark.mock
    def test_embed_query_empty_text(self, mock_env_vars, mock_client):
        """測試空文本處理"""
        mock_client.aembed_query.return_value = [0.1, 0.2, 0.3] * 256
        
        with patch('app.services.embedding_service.GoogleGenerativeAIEmbeddings', return_value=mock_client):
            service = GeminiEmbeddingService()
            
            async def test():
                result = await service.embed_query("")
                assert result == [0.1, 0.2, 0.3] * 256
                mock_client.aembed_query.assert_called_with("empty query")
            
            asyncio.run(test())
    
    @pytest.mark.unit
    @pytest.mark.mock
    def test_embed_documents_batch(self, mock_env_vars, mock_client):
        """測試批次文檔向量化"""
        mock_client.aembed_documents.return_value = [
            [0.1, 0.2, 0.3] * 256,
            [0.4, 0.5, 0.6] * 256
        ]
        
        with patch('app.services.embedding_service.GoogleGenerativeAIEmbeddings', return_value=mock_client):
            service = GeminiEmbeddingService()
            
            async def test():
                texts = ["document 1", "document 2"]
                result = await service.embed_documents(texts)
                
                assert len(result) == 2
                assert all(len(vector) == 768 for vector in result)
            
            asyncio.run(test())
    
    @pytest.mark.unit
    @pytest.mark.mock
    def test_embed_alert_content(self, mock_env_vars, mock_client):
        """測試警報內容向量化"""
        mock_client.aembed_query.return_value = [0.1, 0.2, 0.3] * 256
        
        with patch('app.services.embedding_service.GoogleGenerativeAIEmbeddings', return_value=mock_client):
            service = GeminiEmbeddingService()
            
            async def test():
                alert_data = {
                    'rule': {
                        'description': 'Test alert',
                        'level': 5,
                        'id': '12345'
                    },
                    'agent': {
                        'name': 'test-host'
                    },
                    'data': {
                        'srcip': '192.168.1.1',
                        'dstip': '192.168.1.2'
                    }
                }
                
                result = await service.embed_alert_content(alert_data)
                assert len(result) == 768
                
                # 驗證調用的文本包含關鍵信息
                call_args = mock_client.aembed_query.call_args[0][0]
                assert 'Test alert' in call_args
                assert 'test-host' in call_args
                assert '192.168.1.1' in call_args
            
            asyncio.run(test())
    
    @pytest.mark.unit
    @pytest.mark.mock
    def test_retry_mechanism(self, mock_env_vars, mock_client):
        """測試重試機制"""
        # 第一次失敗，第二次成功
        mock_client.aembed_query.side_effect = [Exception("API Error"), [0.1, 0.2, 0.3] * 256]
        
        with patch('app.services.embedding_service.GoogleGenerativeAIEmbeddings', return_value=mock_client):
            service = GeminiEmbeddingService()
            
            async def test():
                result = await service.embed_query("test")
                assert len(result) == 768
                assert mock_client.aembed_query.call_count == 2
            
            asyncio.run(test())


class TestNeo4jGraphService:
    """Neo4j 圖形服務單元測試"""
    
    @pytest.fixture
    def mock_driver(self):
        """模擬 Neo4j 驅動"""
        mock_driver = Mock()
        mock_session = Mock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_driver.session.return_value.__exit__.return_value = None
        return mock_driver, mock_session
    
    @pytest.mark.unit
    @pytest.mark.mock
    def test_create_alert_node(self, mock_driver):
        """測試創建警報節點"""
        driver, session = mock_driver
        session.run.return_value = Mock()
        
        with patch('app.services.graph_service.GraphDatabase.driver', return_value=driver):
            service = Neo4jGraphService()
            
            async def test():
                alert_id = "test_alert_123"
                alert_data = {"rule": {"description": "Test alert"}}
                
                await service.create_alert_node(alert_id, alert_data)
                
                # 驗證 Cypher 查詢被執行
                session.run.assert_called_once()
                call_args = session.run.call_args[0][0]
                assert "CREATE" in call_args
                assert "Alert" in call_args
                assert alert_id in call_args
            
            asyncio.run(test())
    
    @pytest.mark.unit
    @pytest.mark.mock
    def test_create_entity_relationship(self, mock_driver):
        """測試創建實體關係"""
        driver, session = mock_driver
        session.run.return_value = Mock()
        
        with patch('app.services.graph_service.GraphDatabase.driver', return_value=driver):
            service = Neo4jGraphService()
            
            async def test():
                alert_id = "test_alert_123"
                entity_type = "IP"
                entity_value = "192.168.1.1"
                relationship_type = "HAS_SOURCE_IP"
                
                await service.create_entity_relationship(alert_id, entity_type, entity_value, relationship_type)
                
                session.run.assert_called_once()
                call_args = session.run.call_args[0][0]
                assert "MERGE" in call_args
                assert entity_type in call_args
                assert relationship_type in call_args
            
            asyncio.run(test())


class TestRetrievalService:
    """檢索服務單元測試"""
    
    @pytest.fixture
    def mock_opensearch(self):
        """模擬 OpenSearch 客戶端"""
        mock_client = Mock()
        mock_client.search.return_value = {
            'hits': {
                'hits': [
                    {
                        '_source': {'content': 'test document 1'},
                        '_score': 0.95
                    },
                    {
                        '_source': {'content': 'test document 2'},
                        '_score': 0.85
                    }
                ]
            }
        }
        return mock_client
    
    @pytest.mark.unit
    @pytest.mark.mock
    def test_vector_search(self, mock_opensearch):
        """測試向量搜尋"""
        with patch('app.services.retrieval_service.OpenSearch', return_value=mock_opensearch):
            service = RetrievalService()
            
            async def test():
                query_vector = [0.1, 0.2, 0.3] * 256
                results = await service.vector_search(query_vector, k=5)
                
                assert len(results) == 2
                assert results[0]['content'] == 'test document 1'
                assert results[0]['score'] == 0.95
            
            asyncio.run(test())


class TestLLMService:
    """LLM 服務單元測試"""
    
    @pytest.fixture
    def mock_llm(self):
        """模擬 LLM 客戶端"""
        mock_client = Mock()
        mock_client.invoke.return_value = Mock(content="Test response")
        return mock_client
    
    @pytest.mark.unit
    @pytest.mark.mock
    def test_analyze_alert(self, mock_llm):
        """測試警報分析"""
        with patch('app.services.llm_service.Anthropic', return_value=mock_llm):
            service = LLMService()
            
            async def test():
                alert_data = {"rule": {"description": "Test alert"}}
                context = "Test context"
                
                result = await service.analyze_alert(alert_data, context)
                
                assert result == "Test response"
                mock_llm.invoke.assert_called_once()
            
            asyncio.run(test())


class TestGraphEntityExtractor:
    """圖形實體提取器單元測試"""
    
    @pytest.mark.unit
    def test_extract_entities_from_alert(self):
        """測試從警報中提取實體"""
        extractor = GraphEntityExtractor()
        
        alert_data = {
            'data': {
                'srcip': '192.168.1.1',
                'dstip': '192.168.1.2',
                'user': 'admin',
                'command': 'sudo rm -rf /'
            },
            'agent': {
                'name': 'test-host'
            }
        }
        
        entities = extractor.extract_entities_from_alert(alert_data)
        
        assert len(entities) > 0
        assert any(entity['type'] == 'IP' for entity in entities)
        assert any(entity['type'] == 'User' for entity in entities)
        assert any(entity['type'] == 'Host' for entity in entities)


class TestGraphRelationshipBuilder:
    """圖形關係建構器單元測試"""
    
    @pytest.mark.unit
    def test_build_relationships(self):
        """測試建構實體關係"""
        builder = GraphRelationshipBuilder()
        
        entities = [
            {'type': 'IP', 'value': '192.168.1.1'},
            {'type': 'User', 'value': 'admin'},
            {'type': 'Host', 'value': 'test-host'}
        ]
        
        relationships = builder.build_relationships(entities)
        
        assert len(relationships) > 0
        assert all('source' in rel for rel in relationships)
        assert all('target' in rel for rel in relationships)
        assert all('type' in rel for rel in relationships)


class TestGraphQueryEngine:
    """圖形查詢引擎單元測試"""
    
    @pytest.mark.unit
    def test_generate_graph_query(self):
        """測試生成圖形查詢"""
        engine = GraphQueryEngine()
        
        entities = [
            {'type': 'IP', 'value': '192.168.1.1'},
            {'type': 'User', 'value': 'admin'}
        ]
        
        query = engine.generate_graph_query(entities)
        
        assert 'MATCH' in query
        assert 'RETURN' in query
        assert '192.168.1.1' in query
        assert 'admin' in query


class TestTextChunking:
    """文本分塊服務單元測試"""
    
    @pytest.mark.unit
    def test_smart_chunker_initialization(self):
        """測試智能分塊器初始化"""
        chunker = SmartTextChunker(max_chunk_size=1000, overlap_size=100)
        
        assert chunker.max_chunk_size == 1000
        assert chunker.overlap_size == 100
        assert len(chunker.alert_keywords) > 0
    
    @pytest.mark.unit
    def test_fixed_chunking(self):
        """測試固定長度分塊"""
        chunker = SmartTextChunker(max_chunk_size=10, overlap_size=2)
        text = "This is a test text that needs to be chunked"
        
        chunks = chunker.chunk_text(text, strategy="fixed")
        
        assert len(chunks) > 1
        assert all(len(chunk.content) <= 10 for chunk in chunks)
    
    @pytest.mark.unit
    def test_alert_optimized_chunking(self):
        """測試警報優化分塊"""
        chunker = SmartTextChunker(max_chunk_size=50)
        alert_text = "規則描述: 測試警報 | 警報等級: 5 | 主機名稱: test-host | srcip: 192.168.1.1 | dstip: 192.168.1.2"
        
        chunks = chunker.chunk_text(alert_text, strategy="alert_optimized")
        
        assert len(chunks) >= 1
        # 驗證優先級最高的塊包含關鍵信息
        best_chunk = min(chunks, key=lambda x: x.priority)
        assert "規則描述" in best_chunk.content
        assert "警報等級" in best_chunk.content
    
    @pytest.mark.unit
    def test_get_optimal_text(self):
        """測試獲取最優文本"""
        long_text = "規則描述: 重要警報 " * 1000  # 很長的文本
        
        optimal_text = get_optimal_text(long_text, max_size=100)
        
        assert len(optimal_text) <= 100
        assert "規則描述" in optimal_text  # 確保關鍵信息被保留
    
    @pytest.mark.unit
    def test_smart_chunk_text_function(self):
        """測試便捷函數"""
        text = "This is a test text"
        
        chunks = smart_chunk_text(text, max_size=10)
        
        assert isinstance(chunks, list)
        assert all(isinstance(chunk, str) for chunk in chunks)
        assert all(len(chunk) <= 10 for chunk in chunks)


class TestErrorHandling:
    """錯誤處理單元測試"""
    
    @pytest.mark.unit
    def test_custom_exceptions(self):
        """測試自定義異常"""
        # 測試 OpenSearchError
        opensearch_error = OpenSearchError("Connection failed", "CONNECTION_ERROR")
        assert opensearch_error.message == "Connection failed"
        assert opensearch_error.error_code == "CONNECTION_ERROR"
        assert opensearch_error.timestamp is not None
        
        # 測試 Neo4jError
        neo4j_error = Neo4jError("Query failed", "QUERY_ERROR", {"query": "MATCH n"})
        assert neo4j_error.message == "Query failed"
        assert neo4j_error.error_code == "QUERY_ERROR"
        assert neo4j_error.details["query"] == "MATCH n"
        
        # 測試 LLMError
        llm_error = LLMError("API rate limit exceeded")
        assert llm_error.message == "API rate limit exceeded"
        assert llm_error.error_code == "LLMError"
    
    @pytest.mark.unit
    def test_error_context_manager(self):
        """測試錯誤上下文管理器"""
        from utils.error_handling import ErrorContext
        
        with ErrorContext("test operation", reraise=False) as ctx:
            # 正常操作
            pass
        
        # 測試異常處理
        with ErrorContext("test operation", reraise=False) as ctx:
            raise ValueError("Test error")
        
        # 測試重新拋出異常
        with pytest.raises(ValueError):
            with ErrorContext("test operation", reraise=True):
                raise ValueError("Test error")


# 測試配置
@pytest.fixture(autouse=True)
def setup_test_environment():
    """設置測試環境"""
    # 設置測試日誌級別
    import logging
    logging.getLogger().setLevel(logging.ERROR)
    
    # 清理任何殘留的 mock
    yield
    
    # 清理工作
    pass 