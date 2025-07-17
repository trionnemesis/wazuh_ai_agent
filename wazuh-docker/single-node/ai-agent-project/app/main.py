import os
import logging
import traceback
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# LangChain 相關套件引入
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# OpenSearch 客戶端
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection

# 引入自定義的嵌入服務模組
from embedding_service import GeminiEmbeddingService

# 配置日誌系統
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 環境變數配置
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "https://wazuh.indexer:9200")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "SecretPassword")

# 大型語言模型配置
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# 初始化 OpenSearch 非同步客戶端
client = AsyncOpenSearch(
    hosts=[OPENSEARCH_URL],
    http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
    use_ssl=True,
    verify_certs=False,
    ssl_show_warn=False,
    connection_class=AsyncHttpConnection
)

def get_llm():
    """
    根據環境配置初始化大型語言模型
    
    支援的提供商：
    - gemini: Google Gemini 1.5 Flash 模型
    - anthropic: Anthropic Claude 3 Haiku 模型
    
    Returns:
        ChatModel: 配置完成的語言模型實例
        
    Raises:
        ValueError: 當提供商不支援或 API 金鑰未設定時
    """
    logger.info(f"正在初始化 LLM 提供商: {LLM_PROVIDER}")
    
    if LLM_PROVIDER == 'gemini':
        if not GEMINI_API_KEY:
            raise ValueError("LLM_PROVIDER 設為 'gemini' 但 GEMINI_API_KEY 未設定")
        return ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GEMINI_API_KEY)
    
    elif LLM_PROVIDER == 'anthropic':
        if not ANTHROPIC_API_KEY:
            raise ValueError("LLM_PROVIDER 設為 'anthropic' 但 ANTHROPIC_API_KEY 未設定")
        return ChatAnthropic(model="claude-3-haiku-20240307", anthropic_api_key=ANTHROPIC_API_KEY)
    
    else:
        raise ValueError(f"不支援的 LLM_PROVIDER: {LLM_PROVIDER}。請選擇 'gemini' 或 'anthropic'")

# 初始化 LangChain 組件
llm = get_llm()

# 階段二：針對 RAG 檢索增強生成的提示範本
prompt_template = ChatPromptTemplate.from_template(
    """您是一位資深的資安分析師。請使用下方提供的歷史相似警報上下文來分析新的 Wazuh 警報。

**相關歷史警報：**
{historical_context}

**待分析的新 Wazuh 警報：**
{alert_summary}

**分析任務：**
1. 簡要總結新事件。
2. 評估風險等級（嚴重、高、中、低、資訊），參考歷史上下文中的模式。
3. 提供明確的、上下文感知的建議，並參考相似歷史警報的相關模式。

**您的分流報告：**
"""
)

output_parser = StrOutputParser()
chain = prompt_template | llm | output_parser

# 初始化嵌入服務
embedding_service = GeminiEmbeddingService()

# === 階段二：核心 RAG 實作函式 ===

async def find_similar_alerts(query_vector: List[float], k: int = 5) -> List[Dict[Any, Any]]:
    """
    階段二：實現檢索模組 - 使用 k-NN 搜尋找到相似的歷史警報
    
    此函式透過向量相似度搜尋，從 OpenSearch 中檢索出與當前警報最相關的歷史警報。
    使用餘弦相似度作為距離度量，並透過 HNSW 演算法實現高效的近似最近鄰搜尋。
    
    Args:
        query_vector (List[float]): 新警報的向量表示（768 維）
        k (int): 要檢索的相似警報數量，預設為 5
        
    Returns:
        List[Dict[Any, Any]]: 最相似的 k 個歷史警報文檔，按相似度排序
        
    Note:
        - 只檢索已經經過 AI 分析的歷史警報（包含 ai_analysis 欄位）
        - 使用 OpenSearch 的原生 k-NN 查詢功能
        - 若發生錯誤則返回空列表，確保系統穩定性
    """
    try:
        # 構建 OpenSearch k-NN 搜尋查詢，使用餘弦相似度
        knn_search_body = {
            "size": k,
            "query": {
                "bool": {
                    "must": [
                        {
                            "knn": {
                                "alert_vector": {  # 使用標準化的向量欄位名稱
                                    "vector": query_vector,
                                    "k": k
                                }
                            }
                        }
                    ],
                    "filter": [
                        {
                            "exists": {
                                "field": "ai_analysis"  # 只檢索已經分析過的歷史警報
                            }
                        }
                    ]
                }
            },
            "_source": ["rule", "agent", "ai_analysis", "timestamp"]  # 只獲取必要的欄位以優化效能
        }
        
        logger.info(f"執行 k-NN 搜尋以找尋 {k} 個相似警報")
        logger.debug(f"k-NN 查詢內容: {knn_search_body}")
        
        # 執行向量搜尋
        response = await client.search(
            index="wazuh-alerts-*",
            body=knn_search_body
        )
        
        similar_alerts = response.get('hits', {}).get('hits', [])
        logger.info(f"找到 {len(similar_alerts)} 個相似的歷史警報")
        
        return similar_alerts
        
    except Exception as e:
        logger.error(f"find_similar_alerts 執行錯誤: {str(e)}")
        return []

def format_historical_context(alerts: List[Dict[Any, Any]]) -> str:
    """
    階段二：格式化歷史上下文函式 - 將檢索到的警報格式化為可讀字串
    
    此函式將向量搜尋結果轉換為結構化的文字格式，供 LLM 進行上下文感知分析。
    包含時間戳記、主機資訊、規則詳情、先前分析結果及相似度分數。
    
    Args:
        alerts (List[Dict[Any, Any]]): find_similar_alerts 返回的警報文檔列表
        
    Returns:
        str: 格式化的歷史上下文字串，適合作為 LLM 輸入
        
    Note:
        - 若無相關歷史警報則返回預設訊息
        - 長文本分析會被截斷至 200 字符以控制提示長度
        - 包含相似度分數以提供透明度
    """
    if not alerts:
        return "未找到相關的歷史警報。"
    
    context_parts = []
    for i, alert in enumerate(alerts, 1):
        source = alert.get('_source', {})
        rule = source.get('rule', {})
        agent = source.get('agent', {})
        timestamp = source.get('timestamp', '未知時間')
        
        # 提取 AI 分析結果
        ai_analysis = source.get('ai_analysis', {})
        previous_analysis = ai_analysis.get('triage_report', '無先前分析可用')
        
        # 格式化每個歷史警報的資訊
        context_part = f"""
{i}. **時間戳記：** {timestamp}
   **主機：** {agent.get('name', '未知')}
   **規則：** {rule.get('description', '無')} (等級: {rule.get('level', '無')})
   **先前分析：** {previous_analysis[:200]}{'...' if len(previous_analysis) > 200 else ''}
   **相似度分數：** {alert.get('_score', '無')}
"""
        context_parts.append(context_part)
    
    return "\n".join(context_parts)

async def process_single_alert(alert: Dict[Any, Any]) -> None:
    """
    階段二：修改後的單一警報處理流程 - 整合 RAG 功能
    
    這是核心的警報處理流程，整合了檢索增強生成技術。處理順序為：
    1. 獲取並準備新警報資料
    2. 使用 Gemini Embedding 對警報內容進行向量化
    3. 透過向量相似度搜尋檢索相關歷史警報
    4. 格式化歷史上下文資料
    5. 調用 LLM 進行上下文感知分析
    6. 將分析結果與向量資料更新至 OpenSearch
    
    Args:
        alert (Dict[Any, Any]): 來自 OpenSearch 的原始警報文檔
        
    Raises:
        Exception: 處理過程中的任何錯誤都會被記錄但不會中斷整體流程
        
    Note:
        - 每個處理步驟都有詳細的日誌記錄
        - 向量資料會被保存以供未來的相似度搜尋使用
        - 錯誤處理確保單一警報失敗不影響批次處理
    """
    alert_id = alert['_id']
    alert_index = alert['_index']
    alert_source = alert['_source']
    rule = alert_source.get('rule', {})
    agent = alert_source.get('agent', {})
    
    # 步驟一：準備警報摘要資訊
    alert_summary = f"規則: {rule.get('description', '無')} (等級: {rule.get('level', '無')}) 於主機: {agent.get('name', '無')}"
    logger.info(f"處理警報 {alert_id}: {alert_summary}")

    try:
        # 步驟二：對新警報進行向量化
        logger.info(f"正在向量化警報 {alert_id}")
        alert_vector = await embedding_service.embed_alert_content(alert_source)
        
        # 步驟三：檢索語意相似的歷史警報
        logger.info(f"正在檢索警報 {alert_id} 的相似警報")
        similar_alerts = await find_similar_alerts(alert_vector, k=5)
        
        # 步驟四：格式化歷史上下文資料
        historical_context = format_historical_context(similar_alerts)
        
        # 步驟五：調用 LLM 進行上下文感知分析
        logger.info(f"正在為警報 {alert_id} 生成包含歷史上下文的 AI 分析")
        analysis_result = await chain.ainvoke({
            "alert_summary": alert_summary,
            "historical_context": historical_context
        })
        
        logger.info(f"已為警報 {alert_id} 生成 AI 分析: {analysis_result[:100]}...")
        
        # 步驟六：更新 OpenSearch 文檔
        update_body = {
            "doc": {
                "ai_analysis": {
                    "triage_report": analysis_result,
                    "provider": LLM_PROVIDER,
                    "timestamp": datetime.utcnow().isoformat(),
                    "similar_alerts_count": len(similar_alerts)
                },
                "alert_vector": alert_vector  # 儲存向量以供未來檢索使用
            }
        }
        
        await client.update(index=alert_index, id=alert_id, body=update_body)
        logger.info(f"成功更新警報 {alert_id}，已整合 RAG 增強分析")
        
    except Exception as e:
        logger.error(f"處理警報 {alert_id} 時發生錯誤: {str(e)}")
        raise

async def query_new_alerts(limit: int = 10) -> List[Dict[str, Any]]:
    """
    從 OpenSearch 查詢尚未分析的新警報
    
    此函式會搜尋所有不包含 ai_analysis 欄位的警報，這表示這些警報尚未經過
    AI 分析處理。結果按時間戳記降序排列，確保最新的警報優先處理。
    
    Args:
        limit (int): 要檢索的警報數量上限，預設為 10
        
    Returns:
        List[Dict[str, Any]]: 待處理的警報文檔列表
        
    Raises:
        Exception: 查詢失敗時拋出例外
        
    Note:
        - 使用布林查詢的 must_not 子句來排除已分析的警報
        - 按時間戳記降序排序確保處理最新警報
        - 包含詳細的日誌記錄以便監控
    """
    try:
        # 查找未經 AI 分析的警報
        response = await client.search(
            index="wazuh-alerts-*",
            body={
                "query": {
                    "bool": {
                        "must_not": [{"exists": {"field": "ai_analysis"}}]
                    }
                },
                "sort": [{"timestamp": {"order": "desc"}}]
            },
            size=limit
        )
        
        alerts = response['hits']['hits']
        logger.info(f"找到 {len(alerts)} 個新警報待處理")
        return alerts
        
    except Exception as e:
        logger.error(f"查詢新警報失敗: {str(e)}")
        raise

async def ensure_index_template() -> None:
    """
    確保 OpenSearch 索引範本存在並包含向量欄位映射
    
    此函式會檢查並建立必要的索引範本，以確保新建立的 Wazuh 警報索引
    包含正確的向量欄位配置。範本包括：
    - alert_vector: 768 維的密集向量欄位，使用 HNSW 索引
    - ai_analysis: 結構化的 AI 分析結果欄位
    - 適當的 k-NN 搜尋配置
    
    Note:
        - 使用 HNSW 演算法實現高效的向量搜尋
        - 餘弦相似度適合語意搜尋場景
        - 索引範本優先級設為 1，適用於所有 wazuh-alerts-* 索引
    """
    template_name = "wazuh-alerts-vector-template"
    template_body = {
        "index_patterns": ["wazuh-alerts-*"],
        "priority": 1,
        "template": {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 1,
                "index": {
                    "knn": True,
                    "knn.algo_param.ef_search": 512
                }
            },
            "mappings": {
                "properties": {
                    "alert_vector": {
                        "type": "dense_vector",
                        "dims": 768,
                        "index": True,
                        "similarity": "cosine",
                        "index_options": {
                            "type": "hnsw",
                            "m": 16,
                            "ef_construction": 512
                        }
                    },
                    "ai_analysis": {
                        "type": "object",
                        "properties": {
                            "triage_report": {"type": "text"},
                            "provider": {"type": "keyword"},
                            "timestamp": {"type": "date"},
                            "similar_alerts_count": {"type": "integer"}
                        }
                    }
                }
            }
        }
    }
    
    try:
        # 檢查範本是否已存在
        try:
            await client.indices.get_index_template(name=template_name)
            logger.info(f"索引範本 {template_name} 已存在")
        except Exception:
            # 範本不存在，建立新範本
            await client.indices.put_index_template(name=template_name, body=template_body)
            logger.info(f"成功建立索引範本: {template_name}")
            
    except Exception as e:
        logger.error(f"確保索引範本存在時失敗: {str(e)}")
        raise

# === 主要處理函式 ===

async def triage_new_alerts():
    """
    階段二：修改後的主要分流函式以使用新的 RAG 流程
    
    這是系統的核心排程任務，負責：
    1. 確保索引範本正確配置
    2. 查詢待處理的新警報
    3. 使用 RAG 技術對每個警報進行處理
    4. 記錄處理統計資料
    
    該函式每分鐘執行一次，提供持續的警報分析服務。
    錯誤處理機制確保單一警報失敗不會影響整個批次的處理。
    
    Note:
        - 使用非同步處理以提高效能
        - 包含詳細的執行統計
        - 關鍵錯誤會觸發詳細的錯誤報告
    """
    print("--- RAG 功能分流作業執行中 ---")
    logger.info(f"使用 {LLM_PROVIDER} 模型和 RAG 檢索技術分析警報...")
    
    try:
        # 1. 確保索引範本存在
        await ensure_index_template()
        
        # 2. 查詢新警報
        alerts = await query_new_alerts(limit=10)
        
        if not alerts:
            print("--- 未找到新警報 ---")
            logger.info("未找到新警報")
            return
            
        logger.info(f"找到 {len(alerts)} 個新警報使用 RAG 技術處理")
        
        # 3. 使用新的 RAG 工作流程處理每個警報
        processed_count = 0
        for alert in alerts:
            try:
                await process_single_alert(alert)
                processed_count += 1
                print(f"--- 成功使用 RAG 技術處理警報 {alert['_id']} ---")
            except Exception as e:
                print(f"--- 處理警報 {alert['_id']} 時發生錯誤: {str(e)} ---")
                logger.error(f"處理警報 {alert['_id']} 失敗: {str(e)}")
                continue
        
        print(f"--- RAG 批次處理完成: {processed_count}/{len(alerts)} 個警報 ---")
        logger.info(f"RAG 批次處理完成: {processed_count}/{len(alerts)} 個警報")
        
    except Exception as e:
        print(f"!!!!!! RAG 分流作業發生嚴重錯誤 !!!!!!")
        logger.error(f"RAG 分流過程中發生錯誤: {e}", exc_info=True)
        traceback.print_exc()

# === FastAPI 應用程式與排程器 ===

app = FastAPI(title="Wazuh AI 分流代理 - 階段二 RAG")

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    """應用程式啟動事件處理器"""
    logger.info("具備 RAG 功能的 AI 代理啟動中...")
    scheduler.add_job(triage_new_alerts, 'interval', seconds=60, id='triage_job', misfire_grace_time=30)
    scheduler.start()
    logger.info("排程器已啟動。RAG 分流作業已排程")

@app.get("/")
def read_root():
    """根端點 - 返回服務狀態資訊"""
    return {
        "status": "具備 RAG 功能的 AI 分流代理正在運行", 
        "scheduler_status": str(scheduler.get_jobs()),
        "stage": "階段二 - 核心 RAG 實作"
    }

@app.get("/health")
async def health_check():
    """
    詳細健康檢查端點
    
    提供完整的系統狀態資訊，包括：
    - OpenSearch 連線狀態
    - 嵌入服務可用性
    - 向量化統計資料
    - 系統配置資訊
    
    Returns:
        Dict: 詳細的健康檢查報告
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0",
        "stage": "階段二 - 核心 RAG 實作"
    }
    
    try:
        # 檢查 OpenSearch 連線狀態
        cluster_health = await client.cluster.health()
        health_status["opensearch"] = {
            "status": "connected",
            "cluster_name": cluster_health.get("cluster_name", "unknown"),
            "cluster_status": cluster_health.get("status", "unknown"),
            "number_of_nodes": cluster_health.get("number_of_nodes", 0)
        }
        
        # 檢查嵌入服務狀態
        embedding_test = await embedding_service.test_connection()
        health_status["embedding_service"] = {
            "status": "working" if embedding_test else "failed",
            "model": embedding_service.model_name,
            "dimension": embedding_service.get_vector_dimension()
        }
        
        # 檢查向量化警報統計
        vectorized_count_response = await client.count(
            index="wazuh-alerts-*",
            body={"query": {"exists": {"field": "alert_vector"}}}
        )
        
        total_alerts_response = await client.count(index="wazuh-alerts-*")
        
        health_status["processing_stats"] = {
            "vectorized_alerts": vectorized_count_response.get("count", 0),
            "total_alerts": total_alerts_response.get("count", 0),
            "vectorization_rate": round(
                (vectorized_count_response.get("count", 0) / max(total_alerts_response.get("count", 1), 1)) * 100, 2
            )
        }
        
        # LLM 配置資訊
        health_status["llm_config"] = {
            "provider": LLM_PROVIDER,
            "model_configured": True
        }
        
        # 排程器狀態
        jobs = scheduler.get_jobs()
        health_status["scheduler"] = {
            "status": "running" if jobs else "no_jobs",
            "active_jobs": len(jobs),
            "next_run": str(jobs[0].next_run_time) if jobs else None
        }
        
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)
        logger.error(f"健康檢查失敗: {str(e)}")
    
    return health_status

@app.on_event("shutdown")
def shutdown_event():
    """應用程式關閉事件處理器"""
    scheduler.shutdown()
    logger.info("排程器已關閉")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)