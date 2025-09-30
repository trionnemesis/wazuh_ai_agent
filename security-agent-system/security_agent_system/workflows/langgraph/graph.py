"""使用 LangGraph 的安全代理圖。"""
from typing import Dict, Any, List, Literal
from datetime import datetime
import structlog
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import tools_condition
from langgraph.checkpoint.aiosqlite import AsyncSqliteSaver

from .state import AgentState, SecurityAlert
from .agents import ManagerNode, HunterNode, ExecutorNode

logger = structlog.get_logger()


class SecurityAgentGraph:
    """基於 LangGraph 的安全代理協調系統。"""
    
    def __init__(self, 
                 manager_node: ManagerNode,
                 hunter_node: HunterNode,
                 executor_node: ExecutorNode,
                 checkpointer: AsyncSqliteSaver = None):
        """初始化安全代理圖。"""
        self.manager_node = manager_node
        self.hunter_node = hunter_node
        self.executor_node = executor_node
        self.checkpointer = checkpointer
        
        # 建立圖
        self.graph = self._build_graph()
        
        # 編譯圖
        self.app = self.graph.compile(
            checkpointer=self.checkpointer,
            interrupt_before=["human_approval"] if checkpointer else None
        )
    
    def _build_graph(self) -> StateGraph:
        """建立 LangGraph 狀態圖。"""
        # 使用我們的狀態類型建立圖
        workflow = StateGraph(AgentState)
        
        # 新增節點
        workflow.add_node("alert_intake", self._alert_intake)
        workflow.add_node("manager_analysis", self.manager_node)
        workflow.add_node("hunter_investigation", self.hunter_node)
        workflow.add_node("manager_review", self.manager_node)
        workflow.add_node("executor_remediation", self.executor_node)
        workflow.add_node("human_approval", self._human_approval)
        workflow.add_node("completion", self._completion)
        workflow.add_node("error_handler", self._error_handler)
        
        # 定義邊
        # 進入點
        workflow.set_entry_point("alert_intake")
        
        # 從警報接收
        workflow.add_edge("alert_intake", "manager_analysis")
        
        # 從管理者分析
        workflow.add_conditional_edges(
            "manager_analysis",
            self._route_from_manager,
            {
                "investigate": "hunter_investigation",
                "remediate": "executor_remediation",
                "dismiss": "completion",
                "error": "error_handler"
            }
        )
        
        # 從獵人調查
        workflow.add_edge("hunter_investigation", "manager_review")
        
        # 從管理者審查 (調查後)
        workflow.add_conditional_edges(
            "manager_review",
            self._route_from_review,
            {
                "remediate": "executor_remediation",
                "escalate": "human_approval",
                "dismiss": "completion",
                "error": "error_handler"
            }
        )
        
        # 從執行者
        workflow.add_conditional_edges(
            "executor_remediation",
            self._route_from_executor,
            {
                "completed": "completion",
                "approval_needed": "human_approval",
                "error": "error_handler"
            }
        )
        
        # 從人工批准
        workflow.add_conditional_edges(
            "human_approval",
            self._route_from_approval,
            {
                "approved": "executor_remediation",
                "rejected": "completion",
                "modify": "manager_review"
            }
        )
        
        # 從完成
        workflow.add_edge("completion", END)
        
        # 從錯誤處理器
        workflow.add_conditional_edges(
            "error_handler",
            self._route_from_error,
            {
                "retry": "manager_analysis",
                "escalate": "human_approval",
                "abort": END
            }
        )
        
        return workflow
    
    async def _alert_intake(self, state: AgentState) -> AgentState:
        """處理傳入的警報並準備進行分析。"""
        logger.info("警報接收處理中",
                   queue_size=len(state.get("alert_queue", [])))
        
        # 如果需要，初始化狀態
        if "agent_status" not in state:
            state["agent_status"] = {
                "manager": "idle",
                "hunter": "idle",
                "executor": "idle"
            }
        
        if "workflow_history" not in state:
            state["workflow_history"] = []
        
        if "metrics" not in state:
            state["metrics"] = {
                "alerts_processed": 0,
                "investigations_completed": 0,
                "remediations_completed": 0,
                "actions_executed": 0
            }
        
        # 檢查新警報
        if not state.get("current_alert") and state.get("alert_queue"):
            # 從佇列中獲取下一個警報
            state["current_alert"] = state["alert_queue"].pop(0)
            state["workflow_step"] = "analysis"
            state["agent_status"]["manager"] = "pending"
            
            # 更新指標
            state["metrics"]["alerts_processed"] += 1
            
            # 記錄工作流程開始
            state["workflow_history"].append({
                "step": "alert_intake",
                "timestamp": datetime.now().isoformat(),
                "alert_id": state["current_alert"].get("id", "unknown")
            })
        
        return state
    
    async def _human_approval(self, state: AgentState) -> AgentState:
        """處理人工批准工作流程。"""
        logger.info("等待人工批准")
        
        # 在真實系統中，這將與 UI 或票務系統整合
        # 目前，我們模擬批准
        state["workflow_step"] = "approval_pending"
        
        # 新增到工作流程歷史記錄
        state["workflow_history"].append({
            "step": "human_approval_requested",
            "timestamp": datetime.now().isoformat(),
            "reason": "高風險修復需要批准"
        })
        
        # 在生產環境中，這將等待實際的人工輸入
        # 為了示範，記錄後自動批准
        state["approval_decision"] = "approved"
        
        return state
    
    async def _completion(self, state: AgentState) -> AgentState:
        """處理工作流程完成。"""
        logger.info("工作流程已完成",
                   alert_id=state.get("current_alert", {}).get("id", "unknown"))
        
        # 清除目前警報
        state["current_alert"] = None
        state["workflow_step"] = "completed"
        
        # 重設代理狀態
        state["agent_status"] = {
            "manager": "idle",
            "hunter": "idle",
            "executor": "idle"
        }
        
        # 記錄完成
        state["workflow_history"].append({
            "step": "workflow_completed",
            "timestamp": datetime.now().isoformat()
        })
        
        return state
    
    async def _error_handler(self, state: AgentState) -> AgentState:
        """處理工作流程中的錯誤。"""
        logger.error("錯誤處理器已觸發",
                    errors=state.get("errors", []))
        
        # 分析錯誤並決定下一步行動
        error_count = len(state.get("errors", []))
        
        if error_count < 3:
            # 重試
            state["error_action"] = "retry"
            logger.info("錯誤後重試", retry_count=error_count)
        elif error_count < 5:
            # 上報給人工
            state["error_action"] = "escalate"
            logger.warning("錯誤後上報給人工", error_count=error_count)
        else:
            # 中止
            state["error_action"] = "abort"
            logger.error("錯誤過多，中止工作流程", error_count=error_count)
        
        return state
    
    def _route_from_manager(self, state: AgentState) -> Literal["investigate", "remediate", "dismiss", "error"]:
        """根據管理者的決定進行路由。"""
        # 檢查錯誤
        if state.get("agent_status", {}).get("manager") == "error":
            return "error"
        
        # 獲取最新決定
        decisions = state.get("decisions", [])
        if decisions:
            latest_decision = decisions[-1]
            if latest_decision.get("agent") == "manager":
                action = latest_decision.get("decision", {}).get("action", "dismiss")
                
                if action == "investigate":
                    return "investigate"
                elif action == "remediate":
                    return "remediate"
                elif action == "dismiss":
                    return "dismiss"
        
        # 如果沒有明確決定，預設為關閉
        return "dismiss"
    
    def _route_from_review(self, state: AgentState) -> Literal["remediate", "escalate", "dismiss", "error"]:
        """根據調查後管理者的審查進行路由。"""
        # 檢查錯誤
        if state.get("agent_status", {}).get("manager") == "error":
            return "error"
        
        # 檢查工作流程步驟
        if state.get("workflow_step") == "remediation":
            return "remediate"
        elif state.get("workflow_step") == "escalation":
            return "escalate"
        elif state.get("workflow_step") == "completed":
            return "dismiss"
        
        # 如果調查發現問題，預設為修復
        investigations = state.get("investigations", {})
        current_alert_id = state.get("current_alert", {}).get("id")
        
        if current_alert_id and current_alert_id in investigations:
            investigation = investigations[current_alert_id]
            if hasattr(investigation, 'risk_score') and investigation.risk_score > 50:
                return "remediate"
        
        return "dismiss"
    
    def _route_from_executor(self, state: AgentState) -> Literal["completed", "approval_needed", "error"]:
        """根據執行者的結果進行路由。"""
        # 檢查錯誤
        if state.get("agent_status", {}).get("executor") == "error":
            return "error"
        
        # 檢查是否需要批准
        current_alert_id = state.get("current_alert", {}).get("id")
        remediation_plan = state.get("remediation_plans", {}).get(current_alert_id)
        
        if remediation_plan and getattr(remediation_plan, 'approval_required', False):
            # 檢查是否已批准
            if not state.get("approval_decision"):
                return "approval_needed"
        
        # 檢查工作流程步驟
        if state.get("workflow_step") == "completed":
            return "completed"
        
        return "completed"
    
    def _route_from_approval(self, state: AgentState) -> Literal["approved", "rejected", "modify"]:
        """根據人工批准決定進行路由。"""
        decision = state.get("approval_decision", "rejected")
        
        if decision == "approved":
            return "approved"
        elif decision == "modify":
            return "modify"
        else:
            return "rejected"
    
    def _route_from_error(self, state: AgentState) -> Literal["retry", "escalate", "abort"]:
        """根據錯誤處理器的決定進行路由。"""
        return state.get("error_action", "abort")
    
    async def process_alert(self, alert: SecurityAlert, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """透過圖處理單一安全警報。"""
        # 使用警報初始化狀態
        initial_state = {
            "current_alert": alert.model_dump() if hasattr(alert, 'model_dump') else alert,
            "alert_queue": [],
            "investigations": {},
            "remediation_plans": {},
            "execution_results": [],
            "agent_status": {},
            "workflow_step": "intake",
            "workflow_history": [],
            "errors": [],
            "metrics": {},
            "config": config or {},
            "messages": [],
            "decisions": [],
            "external_context": {}
        }
        
        # 執行圖
        final_state = await self.app.ainvoke(initial_state)
        
        # 提取結果
        return {
            "alert_id": alert.id if hasattr(alert, 'id') else alert.get("id"),
            "status": final_state.get("workflow_step"),
            "investigation": final_state.get("investigations", {}).get(alert.id if hasattr(alert, 'id') else alert.get("id")),
            "remediation": final_state.get("remediation_plans", {}).get(alert.id if hasattr(alert, 'id') else alert.get("id")),
            "execution_results": final_state.get("execution_results", []),
            "workflow_history": final_state.get("workflow_history", []),
            "errors": final_state.get("errors", []),
            "metrics": final_state.get("metrics", {})
        }
    
    async def process_alert_stream(self, alerts: List[SecurityAlert], config: Dict[str, Any] = None) -> None:
        """透過圖處理警報串流。"""
        # 使用警報佇列初始化狀態
        initial_state = {
            "current_alert": None,
            "alert_queue": [a.model_dump() if hasattr(a, 'model_dump') else a for a in alerts],
            "investigations": {},
            "remediation_plans": {},
            "execution_results": [],
            "agent_status": {},
            "workflow_step": "intake",
            "workflow_history": [],
            "errors": [],
            "metrics": {},
            "config": config or {},
            "messages": [],
            "decisions": [],
            "external_context": {}
        }
        
        # 透過圖進行串流處理
        async for event in self.app.astream(initial_state):
            logger.info("圖事件",
                       node=event.get("node"),
                       step=event.get("data", {}).get("workflow_step"))
            
            # 根據需要處理事件
            if event.get("node") == "completion":
                # 警報已完成，檢查佇列中是否有更多
                if event.get("data", {}).get("alert_queue"):
                    # 繼續處理
                    continue
                else:
                    # 所有警報已處理
                    break