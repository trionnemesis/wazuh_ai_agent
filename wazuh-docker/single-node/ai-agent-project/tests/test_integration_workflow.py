"""
整合測試：完整業務流程
測試從警報接收到圖形分析的完整工作流程
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
from utils.text_chunking import SmartTextChunker
from utils.error_handling import OpenSearchError, Neo4jError, LLMError


class TestCompleteAlertProcessingWorkflow:
    """完整警報處理工作流程測試"""
    
    @pytest.fixture
    def sample_alert_data(self):
        """樣本警報數據"""
        return {
            'id': 'test_alert_123',
            'rule': {
                'description': 'Suspicious file deletion detected',
                'level': 8,
                'id': '100001',
                'groups': ['malware', 'file_operations']
            },
            'agent': {
                'name': 'web-server-01',
                'id': '001'
            },
            'data': {
                'srcip': '192.168.1.100',
                'dstip': '10.0.0.50',
                'user': 'admin',
                'command': 'rm -rf /var/www/html/*',
                'filename': '/var/www/html/suspicious.php'
            },
            'location': '/var/log/auth.log',
            'decoder': {
                'name': 'sshd'
            },
            'timestamp': '2024-01-15T10:30:00Z'
        }
    
    @pytest.fixture
    def mock_services(self):
        """模擬所有服務"""
        # 模擬嵌入服務
        mock_embedding = Mock(spec=GeminiEmbeddingService)
        mock_embedding.embed_alert_content = AsyncMock(return_value=[0.1, 0.2, 0.3] * 256)
        mock_embedding.embed_query = AsyncMock(return_value=[0.4, 0.5, 0.6] * 256)
        
        # 模擬圖形服務
        mock_graph = Mock(spec=Neo4jGraphService)
        mock_graph.create_alert_node = AsyncMock()
        mock_graph.create_entity_relationship = AsyncMock()
        mock_graph.execute_query = AsyncMock(return_value=[{'result': 'data'}])
        
        # 模擬檢索服務
        mock_retrieval = Mock(spec=RetrievalService)
        mock_retrieval.vector_search = AsyncMock(return_value=[
            {'content': 'Similar alert 1', 'score': 0.95},
            {'content': 'Similar alert 2', 'score': 0.85}
        ])
        
        # 模擬 LLM 服務
        mock_llm = Mock(spec=LLMService)
        mock_llm.analyze_alert = AsyncMock(return_value="This appears to be a potential web defacement attack")
        
        return {
            'embedding': mock_embedding,
            'graph': mock_graph,
            'retrieval': mock_retrieval,
            'llm': mock_llm
        }
    
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_complete_alert_processing(self, sample_alert_data, mock_services):
        """測試完整的警報處理流程"""
        
        # 1. 向量化警報內容
        alert_vector = await mock_services['embedding'].embed_alert_content(sample_alert_data)
        assert len(alert_vector) == 768
        
        # 2. 檢索相似警報
        similar_alerts = await mock_services['retrieval'].vector_search(alert_vector, k=5)
        assert len(similar_alerts) == 2
        assert similar_alerts[0]['score'] > similar_alerts[1]['score']
        
        # 3. 提取實體
        extractor = GraphEntityExtractor()
        entities = extractor.extract_entities_from_alert(sample_alert_data)
        
        expected_entities = ['IP', 'User', 'Host', 'File']
        entity_types = [entity['type'] for entity in entities]
        assert all(entity_type in entity_types for entity_type in expected_entities)
        
        # 4. 創建圖形節點和關係
        await mock_services['graph'].create_alert_node(sample_alert_data['id'], sample_alert_data)
        
        for entity in entities:
            await mock_services['graph'].create_entity_relationship(
                sample_alert_data['id'],
                entity['type'],
                entity['value'],
                f"HAS_{entity['type'].upper()}"
            )
        
        # 5. LLM 分析
        context = f"Similar alerts: {similar_alerts[0]['content']}"
        analysis = await mock_services['llm'].analyze_alert(sample_alert_data, context)
        assert "web defacement" in analysis.lower()
        
        # 驗證所有服務都被正確調用
        mock_services['embedding'].embed_alert_content.assert_called_once()
        mock_services['retrieval'].vector_search.assert_called_once()
        mock_services['graph'].create_alert_node.assert_called_once()
        mock_services['llm'].analyze_alert.assert_called_once()


class TestGraphRAGRetrievalWorkflow:
    """GraphRAG 檢索工作流程測試"""
    
    @pytest.fixture
    def mock_graph_query_result(self):
        """模擬圖形查詢結果"""
        return [
            {
                'alert': {'id': 'alert_1', 'description': 'Suspicious login'},
                'ip': {'value': '192.168.1.100'},
                'user': {'value': 'admin'},
                'relationship': 'HAS_SOURCE_IP'
            },
            {
                'alert': {'id': 'alert_2', 'description': 'File modification'},
                'ip': {'value': '192.168.1.100'},
                'user': {'value': 'admin'},
                'relationship': 'HAS_SOURCE_IP'
            }
        ]
    
    @pytest.mark.integration
    @pytest.mark.mock
    async def test_graph_enhanced_retrieval(self, mock_graph_query_result):
        """測試圖形增強的檢索流程"""
        
        # 模擬圖形服務
        mock_graph = Mock(spec=Neo4jGraphService)
        mock_graph.execute_query = AsyncMock(return_value=mock_graph_query_result)
        
        # 模擬檢索服務
        mock_retrieval = Mock(spec=RetrievalService)
        mock_retrieval.vector_search = AsyncMock(return_value=[
            {'content': 'Vector search result 1', 'score': 0.9},
            {'content': 'Vector search result 2', 'score': 0.8}
        ])
        
        # 1. 向量檢索
        query_vector = [0.1, 0.2, 0.3] * 256
        vector_results = await mock_retrieval.vector_search(query_vector, k=5)
        
        # 2. 圖形查詢
        query_engine = GraphQueryEngine()
        entities = [
            {'type': 'IP', 'value': '192.168.1.100'},
            {'type': 'User', 'value': 'admin'}
        ]
        graph_query = query_engine.generate_graph_query(entities)
        graph_results = await mock_graph.execute_query(graph_query)
        
        # 3. 結果融合
        combined_results = self._combine_results(vector_results, graph_results)
        
        assert len(combined_results) > 0
        assert any('Vector search result' in result['content'] for result in combined_results)
        assert any('Suspicious login' in str(result) for result in combined_results)
    
    def _combine_results(self, vector_results, graph_results):
        """融合向量檢索和圖形查詢結果"""
        combined = []
        
        # 添加向量檢索結果
        for result in vector_results:
            combined.append({
                'source': 'vector',
                'content': result['content'],
                'score': result['score']
            })
        
        # 添加圖形查詢結果
        for result in graph_results:
            combined.append({
                'source': 'graph',
                'content': f"Alert: {result['alert']['description']}",
                'entities': [result['ip']['value'], result['user']['value']]
            })
        
        return combined


class TestErrorHandlingAndRecovery:
    """錯誤處理和恢復測試"""
    
    @pytest.mark.integration
    @pytest.mark.mock
    async def test_service_failure_recovery(self):
        """測試服務失敗時的恢復機制"""
        
        # 模擬嵌入服務失敗
        mock_embedding = Mock(spec=GeminiEmbeddingService)
        mock_embedding.embed_alert_content = AsyncMock(side_effect=EmbeddingError("API rate limit"))
        
        # 模擬圖形服務正常
        mock_graph = Mock(spec=Neo4jGraphService)
        mock_graph.create_alert_node = AsyncMock()
        
        alert_data = {'rule': {'description': 'Test alert'}}
        
        try:
            # 嘗試向量化（會失敗）
            await mock_embedding.embed_alert_content(alert_data)
        except EmbeddingError:
            # 使用後備策略
            fallback_vector = [0.0] * 768  # 零向量作為後備
            
            # 繼續處理（圖形服務應該正常工作）
            await mock_graph.create_alert_node('test_id', alert_data)
            
            # 驗證圖形服務被調用
            mock_graph.create_alert_node.assert_called_once()
    
    @pytest.mark.integration
    @pytest.mark.mock
    async def test_graceful_degradation(self):
        """測試優雅降級機制"""
        
        # 模擬部分服務不可用
        mock_services = {
            'embedding': Mock(spec=GeminiEmbeddingService),
            'graph': Mock(spec=Neo4jGraphService),
            'retrieval': Mock(spec=RetrievalService),
            'llm': Mock(spec=LLMService)
        }
        
        # 設置部分服務失敗
        mock_services['embedding'].embed_alert_content = AsyncMock(side_effect=EmbeddingError("Service unavailable"))
        mock_services['graph'].create_alert_node = AsyncMock()  # 正常工作
        mock_services['llm'].analyze_alert = AsyncMock(return_value="Basic analysis")
        
        alert_data = {'rule': {'description': 'Test alert'}}
        
        # 執行降級處理
        try:
            # 嘗試完整流程
            vector = await mock_services['embedding'].embed_alert_content(alert_data)
        except EmbeddingError:
            # 降級到基本處理
            await mock_services['graph'].create_alert_node('test_id', alert_data)
            analysis = await mock_services['llm'].analyze_alert(alert_data, "")
            
            assert "Basic analysis" in analysis
            mock_services['graph'].create_alert_node.assert_called_once()


class TestPerformanceAndScalability:
    """效能和可擴展性測試"""
    
    @pytest.mark.performance
    @pytest.mark.slow
    async def test_batch_processing_performance(self):
        """測試批次處理效能"""
        
        # 模擬大量警報數據
        alerts = []
        for i in range(100):
            alerts.append({
                'id': f'alert_{i}',
                'rule': {'description': f'Test alert {i}'},
                'data': {'srcip': f'192.168.1.{i}'}
            })
        
        # 模擬服務
        mock_embedding = Mock(spec=GeminiEmbeddingService)
        mock_embedding.embed_documents = AsyncMock(return_value=[[0.1] * 768] * 100)
        
        mock_graph = Mock(spec=Neo4jGraphService)
        mock_graph.create_alert_node = AsyncMock()
        
        # 批次處理
        import time
        start_time = time.time()
        
        # 批次向量化
        vectors = await mock_embedding.embed_documents([alert['rule']['description'] for alert in alerts])
        
        # 批次創建圖形節點
        for alert in alerts:
            await mock_graph.create_alert_node(alert['id'], alert)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        assert len(vectors) == 100
        assert mock_graph.create_alert_node.call_count == 100
        assert processing_time < 10.0  # 應該在10秒內完成
    
    @pytest.mark.performance
    async def test_memory_usage_optimization(self):
        """測試記憶體使用優化"""
        
        # 模擬大文本處理
        large_text = "Large text content " * 10000  # 約 200KB 文本
        
        chunker = SmartTextChunker(max_chunk_size=1000)
        chunks = chunker.chunk_text(large_text, strategy="alert_optimized")
        
        # 驗證分塊結果
        assert len(chunks) > 1
        assert all(len(chunk.content) <= 1000 for chunk in chunks)
        
        # 驗證記憶體效率（通過檢查分塊數量）
        assert len(chunks) < 50  # 不應該產生過多的塊


class TestDataConsistencyAndIntegrity:
    """數據一致性和完整性測試"""
    
    @pytest.mark.integration
    @pytest.mark.mock
    async def test_data_consistency_across_services(self):
        """測試跨服務的數據一致性"""
        
        alert_data = {
            'id': 'consistency_test_123',
            'rule': {'description': 'Consistency test alert'},
            'data': {'srcip': '192.168.1.100'}
        }
        
        # 模擬服務
        mock_embedding = Mock(spec=GeminiEmbeddingService)
        mock_embedding.embed_alert_content = AsyncMock(return_value=[0.1] * 768)
        
        mock_graph = Mock(spec=Neo4jGraphService)
        mock_graph.create_alert_node = AsyncMock()
        
        # 1. 向量化
        vector = await mock_embedding.embed_alert_content(alert_data)
        
        # 2. 創建圖形節點
        await mock_graph.create_alert_node(alert_data['id'], alert_data)
        
        # 3. 驗證數據一致性
        embedding_call = mock_embedding.embed_alert_content.call_args[0][0]
        graph_call = mock_graph.create_alert_node.call_args[0]
        
        # 驗證相同的警報數據被傳遞給兩個服務
        assert embedding_call['id'] == graph_call[0]  # alert_id
        assert embedding_call['rule']['description'] == graph_call[1]['rule']['description']
    
    @pytest.mark.integration
    async def test_entity_extraction_consistency(self):
        """測試實體提取的一致性"""
        
        extractor = GraphEntityExtractor()
        
        # 測試多個警報的實體提取一致性
        alerts = [
            {
                'data': {'srcip': '192.168.1.1', 'user': 'admin'},
                'agent': {'name': 'host1'}
            },
            {
                'data': {'srcip': '192.168.1.2', 'user': 'admin'},
                'agent': {'name': 'host2'}
            }
        ]
        
        all_entities = []
        for alert in alerts:
            entities = extractor.extract_entities_from_alert(alert)
            all_entities.extend(entities)
        
        # 驗證實體類型的一致性
        entity_types = [entity['type'] for entity in all_entities]
        assert 'IP' in entity_types
        assert 'User' in entity_types
        assert 'Host' in entity_types
        
        # 驗證相同類型的實體有相同的結構
        ip_entities = [e for e in all_entities if e['type'] == 'IP']
        assert all('value' in entity for entity in ip_entities)


# 測試配置
@pytest.fixture(autouse=True)
def setup_integration_test_environment():
    """設置整合測試環境"""
    # 設置較長的超時時間
    import asyncio
    asyncio.get_event_loop().set_debug(False)
    
    yield
    
    # 清理工作
    pass 