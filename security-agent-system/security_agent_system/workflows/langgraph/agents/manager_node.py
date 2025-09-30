"""LangGraph 實作的管理代理節點。"""
from typing import Dict, Any, List
from datetime import datetime
import structlog
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from ..state import AgentState, RemediationPlan, SecurityAlert

logger = structlog.get_logger()


class ManagerDecision(BaseModel):
    """管理代理決策輸出。"""
    action: str = Field(description="要採取的行動：investigate、remediate、escalate 或 dismiss")
    priority: int = Field(description="優先級 1-5，1為最高")
    reasoning: str = Field(description="決策的理由")
    remediation_required: bool = Field(description="是否需要修復")
    escalation_required: bool = Field(description="是否需要上報")
    additional_context: Dict[str, Any] = Field(default_factory=dict)


class ManagerNode:
    """協調安全應對的管理代理節點。"""
    
    def __init__(self, llm_provider):
        """使用 LLM 供應商初始化管理節點。"""
        self.llm = llm_provider
        self.parser = JsonOutputParser(pydantic_object=ManagerDecision)
        
        # 建立決策提示模板
        self.decision_prompt = ChatPromptTemplate.from_messages([
            ("system", """您是安全協調系統中的管理代理。
            您的職責包括：
            1. 分析安全警報並決定適當的回應
            2. 根據嚴重性和影響對事件進行優先級排序
            3. 決定是調查、修復、上報還是關閉
            4. 必要時建立修復計畫
            5. 與獵人和執行者代理協調
            
            考量因素如：
            - 警報的嚴重性和信賴度
            - 潛在的業務影響
            - 可用資源
            - 歷史上下文
            - 當前的威脅情勢
            
            以指定的 JSON 格式輸出您的決策。"""),
            MessagesPlaceholder(variable_name="messages"),
            ("human", """分析此安全警報並做出決策：
            
            警報詳細資訊：
            ID: {alert_id}
            類型: {alert_type}
            嚴重性: {severity}
            來源: {source}
            描述: {description}
            
            調查狀態：{investigation_status}
            
            額外上下文：
            {context}
            
            {format_instructions}""")
        ])
        
        # 建立修復計畫提示
        self.remediation_prompt = ChatPromptTemplate.from_messages([
            ("system", """您正在為安全事件建立修復計畫。
            考量：
            1. 立即的圍堵行動
            2. 調查需求
            3. 長期修復方案
            4. 回滾程序
            5. 對業務營運的影響
            
            建立一個詳細、可行的修復計畫。"""),
            ("human", """為以下項目建立修復計畫：
            
            警報：{alert_details}
            調查發現：{investigation_findings}
            決策：{decision}
            
            輸出一個包含具體行動的結構化修復計畫。""")
        ])
        
        # 建立 LCEL 鏈
        self._build_chains()
    
    def _build_chains(self):
        """建立用於決策和修復計畫的 LCEL 鏈。"""
        # 決策鏈
        self.decision_chain = (
            RunnablePassthrough.assign(
                format_instructions=lambda x: self.parser.get_format_instructions()
            )
            | self.decision_prompt
            | self.llm
            | self.parser
        )
        
        # 修復計畫鏈
        self.remediation_chain = (
            self.remediation_prompt
            | self.llm
            | RunnableLambda(self._parse_remediation_plan)
        )
    
    def _parse_remediation_plan(self, output) -> Dict[str, Any]:
        """將 LLM 輸出解析為修復計畫結構。"""
        # 從 LLM 回應中提取結構化資料
        content = output.content if hasattr(output, 'content') else str(output)
        
        # 解析計畫 (這是簡化版本)
        actions = []
        lines = content.split('\n')
        current_action = {}
        
        for line in lines:
            if line.strip().startswith('- Action:'):
                if current_action:
                    actions.append(current_action)
                current_action = {'description': line.replace('- Action:', '').strip()}
            elif line.strip().startswith('  '):
                # 目前行動的額外詳細資訊
                if 'details' not in current_action:
                    current_action['details'] = []
                current_action['details'].append(line.strip())
        
        if current_action:
            actions.append(current_action)
        
        return {
            'actions': actions,
            'raw_plan': content
        }
    
    async def __call__(self, state: AgentState) -> AgentState:
        """處理目前狀態並做出管理決策。"""
        logger.info("管理節點處理中",
                   alert_count=len(state.get("alert_queue", [])),
                   current_alert=state.get("current_alert"))
        
        try:
            # 獲取目前警報
            current_alert = state.get("current_alert")
            if not current_alert:
                # 檢查佇列中是否有新警報
                if state.get("alert_queue"):
                    current_alert = state["alert_queue"].pop(0)
                    state["current_alert"] = current_alert
                else:
                    logger.info("沒有要處理的警報")
                    return state
            
            # 如果是 SecurityAlert 物件，則轉換為字典
            if isinstance(current_alert, SecurityAlert):
                alert_dict = current_alert.model_dump()
            else:
                alert_dict = current_alert
            
            # 準備決策上下文
            context = {
                "alert_id": alert_dict.get("id", "unknown"),
                "alert_type": alert_dict.get("type", "unknown"),
                "severity": alert_dict.get("severity", "unknown"),
                "source": alert_dict.get("source", "unknown"),
                "description": alert_dict.get("description", ""),
                "investigation_status": alert_dict.get("investigation_status", "pending"),
                "context": str(alert_dict.get("context", {})),
                "messages": state.get("messages", [])
            }
            
            # 做出決策
            decision = await self.decision_chain.ainvoke(context)
            
            # 記錄決策
            logger.info("管理決策已做出",
                       alert_id=context["alert_id"],
                       action=decision.action,
                       priority=decision.priority)
            
            # 使用決策更新狀態
            state["decisions"] = state.get("decisions", [])
            state["decisions"].append({
                "agent": "manager",
                "timestamp": datetime.now().isoformat(),
                "alert_id": context["alert_id"],
                "decision": decision.model_dump()
            })
            
            # 根據決策更新工作流程步驟
            if decision.action == "investigate":
                state["workflow_step"] = "investigation"
                state["agent_status"]["hunter"] = "pending"
            elif decision.action == "remediate":
                # 建立修復計畫
                investigation = state.get("investigations", {}).get(context["alert_id"])
                
                plan_context = {
                    "alert_details": alert_dict,
                    "investigation_findings": investigation.model_dump() if investigation else {},
                    "decision": decision.model_dump()
                }
                
                remediation_result = await self.remediation_chain.ainvoke(plan_context)
                
                # 建立 RemediationPlan 物件
                plan = RemediationPlan(
                    alert_id=context["alert_id"],
                    priority=decision.priority,
                    actions=remediation_result["actions"],
                    estimated_impact="medium",  # 這應該由 LLM 決定
                    approval_required=decision.priority <= 2
                )
                
                state["remediation_plans"] = state.get("remediation_plans", {})
                state["remediation_plans"][context["alert_id"]] = plan
                
                state["workflow_step"] = "remediation"
                state["agent_status"]["executor"] = "pending"
            elif decision.action == "escalate":
                state["workflow_step"] = "escalation"
                # 處理上報邏輯
            else:  # dismiss
                state["workflow_step"] = "completed"
                if isinstance(current_alert, dict):
                    current_alert["investigation_status"] = "dismissed"
                    current_alert["remediation_status"] = "not_required"
            
            # 更新代理狀態
            state["agent_status"]["manager"] = "completed"
            
            # 新增到工作流程歷史記錄
            state["workflow_history"] = state.get("workflow_history", [])
            state["workflow_history"].append({
                "step": "manager_decision",
                "timestamp": datetime.now().isoformat(),
                "result": decision.model_dump()
            })
            
        except Exception as e:
            logger.error("管理節點錯誤", error=str(e), exc_info=True)
            state["errors"] = state.get("errors", [])
            state["errors"].append({
                "agent": "manager",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            state["agent_status"]["manager"] = "error"
        
        return state