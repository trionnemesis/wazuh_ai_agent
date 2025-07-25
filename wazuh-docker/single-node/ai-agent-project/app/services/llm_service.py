"""
大型語言模型服務模組
管理 LangChain Prompts、Chains 和 LLM 互動邏輯
"""

import logging
from typing import Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from core.config import OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY

logger = logging.getLogger(__name__)

def get_llm():
    """
    根據環境配置動態初始化大型語言模型
    
    Returns:
        ChatModel: 已配置的語言模型實例，支援非同步調用
        
    Raises:
        ValueError: 當提供商不受支援或 API 金鑰未正確設定時拋出異常
    """
    logger.info(f"正在初始化 LLM 提供商: {LLM_PROVIDER}")
    
    if LLM_PROVIDER == 'gemini':
        if not GEMINI_API_KEY:
            raise ValueError("LLM_PROVIDER 設為 'gemini' 但 GEMINI_API_KEY 環境變數未設定")
        return ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GEMINI_API_KEY)
    
    elif LLM_PROVIDER == 'anthropic':
        if not ANTHROPIC_API_KEY:
            raise ValueError("LLM_PROVIDER 設為 'anthropic' 但 ANTHROPIC_API_KEY 環境變數未設定")
        return ChatAnthropic(model="claude-3-haiku-20240307", anthropic_api_key=ANTHROPIC_API_KEY)
    
    else:
        raise ValueError(f"不支援的 LLM_PROVIDER: {LLM_PROVIDER}。請選擇 'gemini' 或 'anthropic'")

# === Stage 4: GraphRAG 提示詞模板系統 ===

# 基礎 GraphRAG 提示詞模板
graphrag_prompt_template = ChatPromptTemplate.from_template(
    """你是一位資深的安全分析師，專精於基於圖形的威脅情報分析。
    請透過解讀提供的威脅上下文圖來分析新的 Wazuh 警報。

    **威脅上下文圖 (簡化 Cypher 路徑記號):**
    {graph_context}

    **新 Wazuh 警報分析:**
    {alert_summary}

    **你的分析任務:**
    1.  總結新事件的核心特徵與威脅類型。
    2.  **解讀威脅圖**: 描述攻擊路徑、關聯實體，以及潛在的橫向移動跡象。
    3.  基於圖中揭示的攻擊模式評估風險等級 (Critical/High/Medium/Low)。
    4.  提供基於圖形關聯的、更具體的應對建議與緩解措施。

    **你的深度威脅分析報告:**
    """
)

# 增強的 GraphRAG 提示詞模板
enhanced_graphrag_prompt_template = ChatPromptTemplate.from_template(
    """You are a senior cyber security analyst with expertise in graph-based threat hunting and advanced persistent threat (APT) analysis. Analyze the new Wazuh alert below using the comprehensive graph-native intelligence gathered from the security knowledge graph.

    **🔗 Threat Context Graph (Simplified Cypher Path Notation):**
    {graph_context}

    **🔄 橫向移動檢測 (Lateral Movement Detection):**
    {lateral_movement_analysis}

    **⏰ 時間序列關聯 (Temporal Correlation):**
    {temporal_correlation}

    **🌍 IP 信譽分析 (IP Reputation Analysis):**
    {ip_reputation_analysis}

    **👤 使用者行為分析 (User Behavior Analysis):**
    {user_behavior_analysis}

    **⚙️ 程序執行鏈分析 (Process Chain Analysis):**
    {process_chain_analysis}

    **📁 檔案交互分析 (File Interaction Analysis):**
    {file_interaction_analysis}

    **🌐 網路拓撲分析 (Network Topology Analysis):**
    {network_topology_analysis}

    **⚠️ 威脅全景分析 (Threat Landscape Analysis):**
    {threat_landscape_analysis}

    **📊 傳統檢索補充 (Traditional Retrieval Supplement):**
    {traditional_supplement}

    **🚨 當前分析的新警報：**
    {alert_summary}

    **您的圖形化威脅分析任務：**
    1. **事件摘要與分類：** 簡要總結新事件，並根據圖形上下文進行威脅分類
    2. **攻擊鏈重建：** 基於圖形關聯資料重建完整的攻擊時間線和路徑
    3. **橫向移動評估：** 評估攻擊者的橫向移動能力和已滲透的系統範圍
    4. **威脅行為者畫像：** 基於攻擊模式、IP信譽、時間模式分析威脅行為者特徵
    5. **風險等級評估：** 綜合所有圖形智能，評估風險等級（Critical, High, Medium, Low, Informational）
    6. **影響範圍分析：** 確定受影響的系統、使用者、檔案和網路資源
    7. **緩解建議：** 提供基於圖形分析的精確緩解和應急響應建議
    8. **持續威脅指標：** 識別需要持續監控的威脅指標（IOCs/IOAs）

    **您的 GraphRAG 威脅分析報告：**
    """
)

# 傳統提示詞模板（回退場景）
traditional_prompt_template = ChatPromptTemplate.from_template(
    """You are a senior security analyst with expertise in correlating security events with system performance data. Analyze the new Wazuh alert below using the provided multi-source contextual information.

**Historical Similar Alerts:**
{similar_alerts_context}

**Correlated System Metrics:**
{system_metrics_context}

**Process Information:**
{process_context}

**Network Data:**
{network_context}

**Additional Context:**
{additional_context}

**待分析的新 Wazuh 警報：**
{alert_summary}

**Your Analysis Task:**
1. Briefly summarize the new event.
2. Correlate the alert with system performance data and other contextual information.
3. Assess its risk level (Critical, High, Medium, Low, Informational) considering all available context.
4. Identify any patterns or anomalies by cross-referencing different data sources.
5. Provide actionable recommendations based on the comprehensive analysis.

**Your Comprehensive Triage Report:**
"""
)

def get_analysis_chain(context_data: Dict[str, Any]):
    """
    根據上下文資料類型選擇適當的分析鏈
    
    Args:
        context_data: 上下文資料字典
        
    Returns:
        適當的分析鏈
    """
    # 獲取 LLM 實例
    llm = get_llm()
    
    # 檢測是否為圖形檢索結果
    graph_indicators = ['attack_paths', 'lateral_movement', 'temporal_sequences']
    has_graph_data = any(context_data.get(indicator) for indicator in graph_indicators)
    
    if has_graph_data:
        logger.info("🔗 Using Enhanced GraphRAG analysis chain with graph context")
        return enhanced_graphrag_prompt_template | llm | StrOutputParser()
    else:
        logger.info("📊 Using traditional analysis chain")
        return traditional_prompt_template | llm | StrOutputParser()

def extract_risk_level_from_analysis(analysis_result: str) -> str:
    """
    從分析結果中提取風險等級
    
    Args:
        analysis_result: LLM 分析結果文本
        
    Returns:
        風險等級字符串
    """
    risk_levels = ['Critical', 'High', 'Medium', 'Low', 'Informational']
    for level in risk_levels:
        if level.lower() in analysis_result.lower():
            return level
    return 'Unknown'