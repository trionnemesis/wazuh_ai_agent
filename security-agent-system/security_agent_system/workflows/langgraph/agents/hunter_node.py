"""LangGraph 實作的獵人代理節點。"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda, RunnableParallel
from langchain_core.tools import Tool
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from ..state import AgentState, Investigation, SecurityAlert

logger = structlog.get_logger()


class ThreatIntelligence(BaseModel):
    """威脅情報發現。"""
    indicators: List[str] = Field(description="發現的威脅指標")
    ttps: List[str] = Field(description="識別出的戰術、技術和程序")
    related_campaigns: List[str] = Field(description="相關的威脅活動")
    confidence_score: float = Field(description="信賴度分數 0-1")


class InvestigationResult(BaseModel):
    """獵人調查結果。"""
    risk_score: float = Field(description="風險分數 0-100")
    affected_assets: List[str] = Field(description="受影響的資產清單")
    attack_indicators: List[str] = Field(description="發現的攻擊指標")
    findings: List[Dict[str, Any]] = Field(description="詳細的發現")
    recommendations: List[str] = Field(description="建議的行動")
    evidence: Dict[str, Any] = Field(default_factory=dict)
    threat_intel: Optional[ThreatIntelligence] = None


class HunterNode:
    """執行威脅調查的獵人代理節點。"""
    
    def __init__(self, llm_provider, graph_db=None, vector_db=None):
        """使用 LLM 供應商和資料庫初始化獵人節點。"""
        self.llm = llm_provider
        self.graph_db = graph_db
        self.vector_db = vector_db
        self.parser = JsonOutputParser(pydantic_object=InvestigationResult)
        
        # 建立調查提示
        self.investigation_prompt = ChatPromptTemplate.from_messages([
            ("system", """您是安全協調系統中的獵人代理。
            您的職責包括：
            1. 對安全警報進行深度調查
            2. 威脅狩獵和關聯
            3. 識別攻擊模式和指標
            4. 風險評估和評分
            5. 收集證據和上下文
            6. 提供可行的建議
            
            調查方法：
            - 徹底分析警報詳細資訊
            - 尋找模式和異常
            - 與歷史資料關聯
            - 識別潛在的攻擊向量
            - 評估業務影響
            - 收集鑑識證據
            
            以指定的 JSON 格式輸出您的發現。"""),
            MessagesPlaceholder(variable_name="messages", optional=True),
            ("human", """調查此安全警報：
            
            警報詳細資訊：
            ID: {alert_id}
            類型: {alert_type}
            嚴重性: {severity}
            來源: {source}
            描述: {description}
            時間戳: {timestamp}
            
            警報上下文：
            {alert_context}
            
            歷史上下文：
            {historical_context}
            
            外部情報：
            {threat_intel}
            
            進行徹底調查並提供發現。
            
            {format_instructions}""")
        ])
        
        # 建立基於工具的調查鏈
        self._setup_investigation_tools()
        self._build_chains()
    
    def _setup_investigation_tools(self):
        """為獵人代理設定調查工具。"""
        self.tools = []
        
        # 圖形資料庫查詢工具
        if self.graph_db:
            graph_tool = Tool(
                name="query_graph_db",
                description="查詢圖形資料庫以獲取實體關係和模式",
                func=self._query_graph_db
            )
            self.tools.append(graph_tool)
        
        # 向量資料庫搜索工具
        if self.vector_db:
            vector_tool = Tool(
                name="search_vector_db",
                description="搜索向量資料庫以查找相似的警報和模式",
                func=self._search_vector_db
            )
            self.tools.append(vector_tool)
        
        # 威脅情報查詢工具
        threat_intel_tool = Tool(
            name="lookup_threat_intel",
            description="查詢指標的威脅情報",
            func=self._lookup_threat_intel
        )
        self.tools.append(threat_intel_tool)
        
        # 如果有可用的工具，則建立工具節點
        if self.tools:
            self.tool_node = ToolNode(self.tools)
    
    def _build_chains(self):
        """建立用於調查的 LCEL 鏈。"""
        # 主要調查鏈
        self.investigation_chain = (
            RunnablePassthrough.assign(
                format_instructions=lambda x: self.parser.get_format_instructions()
            )
            | self.investigation_prompt
            | self.llm
            | self.parser
        )
        
        # 用於收集上下文的平行調查鏈
        self.context_gathering_chain = RunnableParallel(
            historical_context=RunnableLambda(self._get_historical_context),
            threat_intel=RunnableLambda(self._get_threat_intelligence),
            graph_analysis=RunnableLambda(self._analyze_graph_relationships)
        )
    
    async def _query_graph_db(self, query: str) -> str:
        """查詢圖形資料庫。"""
        if not self.graph_db:
            return "圖形資料庫不可用"
        
        try:
            # 實作實際的圖形查詢邏輯
            result = await self.graph_db.query(query)
            return str(result)
        except Exception as e:
            logger.error("圖形資料庫查詢錯誤", error=str(e))
            return f"查詢圖形資料庫時發生錯誤：{str(e)}"
    
    async def _search_vector_db(self, query: str) -> str:
        """搜索向量資料庫。"""
        if not self.vector_db:
            return "向量資料庫不可用"
        
        try:
            # 實作實際的向量搜索邏輯
            results = await self.vector_db.search(query, limit=5)
            return str(results)
        except Exception as e:
            logger.error("向量資料庫搜索錯誤", error=str(e))
            return f"搜索向量資料庫時發生錯誤：{str(e)}"
    
    async def _lookup_threat_intel(self, indicators: str) -> str:
        """查詢給定指標的威脅情報。"""
        # 這將與實際的威脅情報來源整合
        # 目前，返回模擬資料
        return f"查詢威脅情報：{indicators} - 未識別出已知活動"
    
    async def _get_historical_context(self, alert_data: Dict[str, Any]) -> str:
        """獲取警報的歷史上下文。"""
        # 查詢歷史資料
        if self.vector_db:
            similar_alerts = await self._search_vector_db(
                f"與 {alert_data.get('type', 'unknown')} 相似的警報"
            )
            return f"歷史上下文：{similar_alerts}"
        return "無可用歷史資料"
    
    async def _get_threat_intelligence(self, alert_data: Dict[str, Any]) -> str:
        """獲取警報的威脅情報。"""
        # 從警報中提取指標
        indicators = []
        if "details" in alert_data:
            # 提取 IP、域名、雜湊值等
            details = alert_data["details"]
            if isinstance(details, dict):
                indicators.extend(details.get("indicators", []))
        
        if indicators:
            return await self._lookup_threat_intel(", ".join(indicators))
        return "沒有可查詢的指標"
    
    async def _analyze_graph_relationships(self, alert_data: Dict[str, Any]) -> str:
        """分析圖形資料庫中的實體關係。"""
        if self.graph_db:
            # 從警報中提取實體
            entities = alert_data.get("details", {}).get("entities", [])
            if entities:
                query = f"MATCH path = (n)-[*..3]-(m) WHERE n.name IN {entities} RETURN path"
                return await self._query_graph_db(query)
        return "未執行圖形分析"
    
    async def __call__(self, state: AgentState) -> AgentState:
        """處理目前狀態並執行調查。"""
        logger.info("獵人節點處理中",
                   workflow_step=state.get("workflow_step"),
                   current_alert=state.get("current_alert"))
        
        try:
            # 檢查是否應進行調查
            if state.get("workflow_step") != "investigation":
                logger.info("不在調查階段，略過")
                return state
            
            # 獲取目前警報
            current_alert = state.get("current_alert")
            if not current_alert:
                logger.warning("沒有要調查的目前警報")
                return state
            
            # 如果需要，轉換為字典
            if isinstance(current_alert, SecurityAlert):
                alert_dict = current_alert.model_dump()
            else:
                alert_dict = current_alert
            
            # 平行收集上下文
            context_data = await self.context_gathering_chain.ainvoke(alert_dict)
            
            # 準備調查上下文
            investigation_context = {
                "alert_id": alert_dict.get("id", "unknown"),
                "alert_type": alert_dict.get("type", "unknown"),
                "severity": alert_dict.get("severity", "unknown"),
                "source": alert_dict.get("source", "unknown"),
                "description": alert_dict.get("description", ""),
                "timestamp": alert_dict.get("timestamp", ""),
                "alert_context": str(alert_dict.get("context", {})),
                "historical_context": context_data.get("historical_context", ""),
                "threat_intel": context_data.get("threat_intel", ""),
                "messages": state.get("messages", [])
            }
            
            # 執行調查
            investigation_result = await self.investigation_chain.ainvoke(investigation_context)
            
            # 記錄調查結果
            logger.info("調查完成",
                       alert_id=investigation_context["alert_id"],
                       risk_score=investigation_result.risk_score,
                       affected_assets=len(investigation_result.affected_assets))
            
            # 建立調查物件
            investigation = Investigation(
                alert_id=investigation_context["alert_id"],
                findings=investigation_result.findings,
                risk_score=investigation_result.risk_score,
                affected_assets=investigation_result.affected_assets,
                attack_indicators=investigation_result.attack_indicators,
                recommendations=investigation_result.recommendations,
                evidence=investigation_result.evidence
            )
            
            # 更新狀態
            state["investigations"] = state.get("investigations", {})
            state["investigations"][investigation_context["alert_id"]] = investigation
            
            # 更新警報狀態
            if isinstance(current_alert, dict):
                current_alert["investigation_status"] = "completed"
            
            # 更新工作流程
            state["workflow_step"] = "decision"
            state["agent_status"]["hunter"] = "completed"
            state["agent_status"]["manager"] = "pending"  # 管理者需要審查
            
            # 新增到工作流程歷史記錄
            state["workflow_history"] = state.get("workflow_history", [])
            state["workflow_history"].append({
                "step": "hunter_investigation",
                "timestamp": datetime.now().isoformat(),
                "result": {
                    "risk_score": investigation.risk_score,
                    "indicators_found": len(investigation.attack_indicators),
                    "affected_assets": len(investigation.affected_assets)
                }
            })
            
            # 更新指標
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["investigations_completed"] = \
                state["metrics"].get("investigations_completed", 0) + 1
            
        except Exception as e:
            logger.error("獵人節點錯誤", error=str(e), exc_info=True)
            state["errors"] = state.get("errors", [])
            state["errors"].append({
                "agent": "hunter",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            state["agent_status"]["hunter"] = "error"
            # 退回到管理者進行決策
            state["workflow_step"] = "decision"
            state["agent_status"]["manager"] = "pending"
        
        return state