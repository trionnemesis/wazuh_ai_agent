# Wazuh GraphRAG 測試策略

## 📋 測試策略概述

本文件描述了 Wazuh GraphRAG AI Agent 專案的完整測試策略，包括單元測試、整合測試、效能測試和自動化測試流程。

## 🎯 測試目標

### 1. 品質保證
- **代碼覆蓋率**: 最低 80% 覆蓋率門檻
- **功能完整性**: 所有核心功能都有對應測試
- **錯誤處理**: 完整的異常情況測試
- **邊界條件**: 極端情況和邊界值測試

### 2. 穩定性保證
- **回歸測試**: 防止新功能破壞現有功能
- **整合測試**: 確保服務間協作正常
- **效能測試**: 驗證系統在負載下的表現
- **錯誤恢復**: 測試故障恢復機制

### 3. 開發效率
- **快速反饋**: 單元測試快速執行
- **自動化**: CI/CD 流程中的自動測試
- **可維護性**: 清晰的測試結構和文檔

## 🏗️ 測試架構

### 測試分類

#### 1. 單元測試 (`@pytest.mark.unit`)
- **範圍**: 單個函數、類別或模組
- **依賴**: 使用 Mock 模擬外部依賴
- **執行時間**: < 1 秒
- **覆蓋範圍**: 核心業務邏輯

```python
@pytest.mark.unit
@pytest.mark.mock
def test_embedding_service_initialization():
    """測試嵌入服務初始化"""
    with patch('app.services.embedding_service.GoogleGenerativeAIEmbeddings'):
        service = GeminiEmbeddingService()
        assert service.model_name == 'models/text-embedding-004'
```

#### 2. 整合測試 (`@pytest.mark.integration`)
- **範圍**: 多個服務的協作
- **依賴**: 模擬外部服務，但測試真實的服務間交互
- **執行時間**: 1-10 秒
- **覆蓋範圍**: 工作流程和數據流

```python
@pytest.mark.integration
@pytest.mark.mock
async def test_complete_alert_processing():
    """測試完整的警報處理流程"""
    # 測試從警報接收到圖形分析的完整流程
```

#### 3. 效能測試 (`@pytest.mark.performance`)
- **範圍**: 系統效能和可擴展性
- **依賴**: 模擬大量數據和負載
- **執行時間**: 10-60 秒
- **覆蓋範圍**: 響應時間、吞吐量、記憶體使用

```python
@pytest.mark.performance
@pytest.mark.slow
async def test_batch_processing_performance():
    """測試批次處理效能"""
    # 測試大量警報的處理效能
```

#### 4. 安全測試 (`@pytest.mark.security`)
- **範圍**: 安全相關功能
- **依賴**: 模擬攻擊場景
- **執行時間**: 5-30 秒
- **覆蓋範圍**: 輸入驗證、權限控制、數據保護

### 測試標記系統

```python
# 測試類型標記
@pytest.mark.unit          # 單元測試
@pytest.mark.integration   # 整合測試
@pytest.mark.performance   # 效能測試
@pytest.mark.security      # 安全測試

# 依賴標記
@pytest.mark.requires_neo4j      # 需要 Neo4j
@pytest.mark.requires_opensearch # 需要 OpenSearch
@pytest.mark.requires_llm        # 需要 LLM API
@pytest.mark.requires_api_key    # 需要 API 金鑰

# 執行特性標記
@pytest.mark.slow         # 慢速測試
@pytest.mark.mock         # 使用 Mock
@pytest.mark.smoke        # 冒煙測試
@pytest.mark.regression   # 回歸測試
```

## 🔧 測試工具和框架

### 核心工具
- **pytest**: 主要測試框架
- **pytest-cov**: 覆蓋率測試
- **pytest-asyncio**: 異步測試支持
- **pytest-mock**: Mock 支持
- **unittest.mock**: 標準庫 Mock

### 測試配置
```ini
# pytest.ini
[tool:pytest]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]

addopts = 
    --strict-markers
    --strict-config
    --disable-warnings
    --tb=short
    --durations=10
    --maxfail=3
    --cov=app
    --cov-report=html:htmlcov
    --cov-report=term-missing
    --cov-report=xml
    --cov-fail-under=80
    --cov-branch

markers =
    unit: 單元測試（快速執行）
    integration: 整合測試（需要外部服務）
    slow: 慢速測試（執行時間 > 5秒）
    mock: 使用 Mock 的測試
    performance: 效能測試
    security: 安全相關測試
```

## 📁 測試文件結構

```
tests/
├── test_unit_services.py          # 服務層單元測試
├── test_integration_workflow.py   # 工作流程整合測試
├── test_stage3_agentic.py         # Stage 3 功能測試
├── test_graphrag_retrieval.py     # GraphRAG 檢索測試
├── test_graph_persistence.py      # 圖形持久化測試
├── conftest.py                    # 共享測試配置
└── fixtures/                      # 測試夾具
    ├── alert_data.py             # 警報數據夾具
    ├── mock_services.py          # 服務 Mock 夾具
    └── test_data.py              # 測試數據夾具
```

## 🎭 Mock 策略

### 外部依賴 Mock

#### 1. API 服務 Mock
```python
@pytest.fixture
def mock_gemini_client():
    """模擬 Gemini API 客戶端"""
    mock_client = Mock()
    mock_client.aembed_query = AsyncMock(return_value=[0.1, 0.2, 0.3] * 256)
    mock_client.aembed_documents = AsyncMock(return_value=[[0.1, 0.2, 0.3] * 256])
    return mock_client
```

#### 2. 資料庫 Mock
```python
@pytest.fixture
def mock_neo4j_driver():
    """模擬 Neo4j 驅動"""
    mock_driver = Mock()
    mock_session = Mock()
    mock_driver.session.return_value.__enter__.return_value = mock_session
    return mock_driver, mock_session
```

#### 3. 環境變數 Mock
```python
@pytest.fixture
def mock_env_vars():
    """模擬環境變數"""
    with patch.dict('os.environ', {
        'GOOGLE_API_KEY': 'test_api_key',
        'EMBEDDING_MODEL': 'models/text-embedding-004',
        'EMBEDDING_DIMENSION': '768'
    }):
        yield
```

### Mock 最佳實踐

1. **隔離性**: 每個測試獨立，不依賴其他測試
2. **真實性**: Mock 行為盡可能接近真實服務
3. **驗證性**: 驗證 Mock 被正確調用
4. **可維護性**: 使用夾具減少重複代碼

## 🚀 測試執行

### 命令行執行

```bash
# 執行所有測試
./run_tests.sh all

# 執行單元測試
./run_tests.sh unit

# 執行整合測試
./run_tests.sh integration

# 執行覆蓋率測試
./run_tests.sh coverage

# 執行效能測試
./run_tests.sh performance

# 快速測試（僅單元測試）
./run_tests.sh quick

# CI/CD 測試
./run_tests.sh ci

# 清理測試緩存
./run_tests.sh clean

# 生成測試報告
./run_tests.sh report
```

### CI/CD 集成

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio
      
      - name: Run tests
        run: |
          ./run_tests.sh ci
      
      - name: Upload coverage
        uses: codecov/codecov-action@v1
        with:
          file: ./coverage.xml
```

## 📊 覆蓋率要求

### 覆蓋率門檻
- **總覆蓋率**: 最低 80%
- **分支覆蓋率**: 最低 70%
- **關鍵模組**: 最低 90%

### 覆蓋率排除
```python
# 排除的行
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod
    class .*Error\(.*\):
    def .*Error\(.*\):
    pass
    raise .*Error
    logger\.
    print\(
    # type: ignore
    # noqa
```

## 🔍 測試數據管理

### 測試數據策略

#### 1. 固定測試數據
```python
@pytest.fixture
def sample_alert_data():
    """樣本警報數據"""
    return {
        'id': 'test_alert_123',
        'rule': {
            'description': 'Suspicious file deletion detected',
            'level': 8,
            'id': '100001'
        },
        'agent': {
            'name': 'web-server-01',
            'id': '001'
        },
        'data': {
            'srcip': '192.168.1.100',
            'dstip': '10.0.0.50',
            'user': 'admin',
            'command': 'rm -rf /var/www/html/*'
        }
    }
```

#### 2. 動態測試數據
```python
@pytest.fixture
def random_alert_data():
    """隨機警報數據"""
    import random
    return {
        'id': f'alert_{random.randint(1000, 9999)}',
        'rule': {
            'description': f'Test alert {random.randint(1, 100)}',
            'level': random.randint(1, 15)
        }
    }
```

### 數據清理
```python
@pytest.fixture(autouse=True)
def cleanup_test_data():
    """自動清理測試數據"""
    yield
    # 清理測試產生的數據
    cleanup_test_database()
```

## 🛡️ 錯誤處理測試

### 異常測試策略

#### 1. 預期異常測試
```python
@pytest.mark.unit
def test_invalid_api_key():
    """測試無效 API 金鑰"""
    with patch.dict('os.environ', {}, clear=True):
        with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
            GeminiEmbeddingService()
```

#### 2. 重試機制測試
```python
@pytest.mark.unit
@pytest.mark.mock
def test_retry_mechanism():
    """測試重試機制"""
    mock_client.aembed_query.side_effect = [
        Exception("API Error"),
        [0.1, 0.2, 0.3] * 256
    ]
    
    result = await service.embed_query("test")
    assert len(result) == 768
    assert mock_client.aembed_query.call_count == 2
```

#### 3. 優雅降級測試
```python
@pytest.mark.integration
@pytest.mark.mock
async def test_graceful_degradation():
    """測試優雅降級"""
    # 模擬部分服務失敗
    mock_services['embedding'].embed_alert_content = AsyncMock(
        side_effect=EmbeddingError("Service unavailable")
    )
    
    # 驗證系統仍能提供基本功能
    await mock_services['graph'].create_alert_node('test_id', alert_data)
    mock_services['graph'].create_alert_node.assert_called_once()
```

## 📈 效能測試

### 效能指標

#### 1. 響應時間
- **單次請求**: < 2 秒
- **批次處理**: < 10 秒（100 個警報）
- **向量化**: < 1 秒

#### 2. 吞吐量
- **並發處理**: 支持 10+ 並發請求
- **記憶體使用**: < 1GB 常駐記憶體
- **CPU 使用**: < 80% 峰值使用率

#### 3. 可擴展性
- **線性擴展**: 處理能力隨資源增加
- **資源效率**: 合理的記憶體和 CPU 使用

### 效能測試範例
```python
@pytest.mark.performance
@pytest.mark.slow
async def test_batch_processing_performance():
    """測試批次處理效能"""
    alerts = [create_test_alert(i) for i in range(100)]
    
    start_time = time.time()
    vectors = await embedding_service.embed_documents(
        [alert['rule']['description'] for alert in alerts]
    )
    end_time = time.time()
    
    processing_time = end_time - start_time
    assert processing_time < 10.0  # 10秒內完成
    assert len(vectors) == 100
```

## 🔄 持續改進

### 測試維護

#### 1. 定期審查
- **每月**: 審查測試覆蓋率
- **每季度**: 評估測試策略有效性
- **每次發布**: 更新測試用例

#### 2. 測試優化
- **執行時間**: 持續優化測試執行速度
- **維護成本**: 減少測試代碼重複
- **可讀性**: 提高測試代碼可讀性

#### 3. 新功能測試
- **功能測試**: 新功能必須有對應測試
- **回歸測試**: 確保不破壞現有功能
- **文檔更新**: 更新測試文檔

### 測試指標

#### 1. 覆蓋率指標
- **代碼覆蓋率**: 目標 80%+
- **分支覆蓋率**: 目標 70%+
- **關鍵路徑**: 目標 95%+

#### 2. 品質指標
- **測試通過率**: 目標 95%+
- **測試穩定性**: 減少間歇性失敗
- **執行時間**: 單元測試 < 30 秒

#### 3. 維護指標
- **測試維護成本**: 新功能測試時間 < 開發時間的 20%
- **測試可讀性**: 測試代碼文檔化
- **測試重用性**: 夾具和工具函數重用

## 📚 最佳實踐

### 1. 測試命名
```python
# 好的命名
def test_embedding_service_initialization_with_valid_config():
def test_alert_processing_workflow_with_malware_detection():
def test_graph_entity_extraction_with_multiple_entities():

# 避免的命名
def test_1():
def test_something():
def test_function():
```

### 2. 測試結構
```python
def test_function_name():
    """測試描述"""
    # Arrange (準備)
    service = create_service()
    input_data = create_test_data()
    
    # Act (執行)
    result = service.process(input_data)
    
    # Assert (驗證)
    assert result is not None
    assert result.status == 'success'
    assert len(result.data) > 0
```

### 3. 測試隔離
```python
@pytest.fixture(autouse=True)
def setup_test_environment():
    """每個測試的環境設置"""
    # 設置
    setup_test_db()
    yield
    # 清理
    cleanup_test_db()
```

### 4. 錯誤處理測試
```python
def test_error_handling():
    """測試錯誤處理"""
    with pytest.raises(ExpectedError) as exc_info:
        function_that_should_fail()
    
    assert "expected error message" in str(exc_info.value)
```

---

**測試策略版本**: 1.0  
**最後更新**: 2025年1月  
**維護者**: AI Agent 開發團隊 