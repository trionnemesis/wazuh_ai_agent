"""Security Agent Graph using LangGraph."""
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
    """LangGraph-based security agent orchestration system."""
    
    def __init__(self, 
                 manager_node: ManagerNode,
                 hunter_node: HunterNode,
                 executor_node: ExecutorNode,
                 checkpointer: AsyncSqliteSaver = None):
        """Initialize the security agent graph."""
        self.manager_node = manager_node
        self.hunter_node = hunter_node
        self.executor_node = executor_node
        self.checkpointer = checkpointer
        
        # Build the graph
        self.graph = self._build_graph()
        
        # Compile the graph
        self.app = self.graph.compile(
            checkpointer=self.checkpointer,
            interrupt_before=["human_approval"] if checkpointer else None
        )
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state graph."""
        # Create the graph with our state type
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("alert_intake", self._alert_intake)
        workflow.add_node("manager_analysis", self.manager_node)
        workflow.add_node("hunter_investigation", self.hunter_node)
        workflow.add_node("manager_review", self.manager_node)
        workflow.add_node("executor_remediation", self.executor_node)
        workflow.add_node("human_approval", self._human_approval)
        workflow.add_node("completion", self._completion)
        workflow.add_node("error_handler", self._error_handler)
        
        # Define edges
        # Entry point
        workflow.set_entry_point("alert_intake")
        
        # From alert intake
        workflow.add_edge("alert_intake", "manager_analysis")
        
        # From manager analysis
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
        
        # From hunter investigation
        workflow.add_edge("hunter_investigation", "manager_review")
        
        # From manager review (after investigation)
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
        
        # From executor
        workflow.add_conditional_edges(
            "executor_remediation",
            self._route_from_executor,
            {
                "completed": "completion",
                "approval_needed": "human_approval",
                "error": "error_handler"
            }
        )
        
        # From human approval
        workflow.add_conditional_edges(
            "human_approval",
            self._route_from_approval,
            {
                "approved": "executor_remediation",
                "rejected": "completion",
                "modify": "manager_review"
            }
        )
        
        # From completion
        workflow.add_edge("completion", END)
        
        # From error handler
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
        """Process incoming alerts and prepare for analysis."""
        logger.info("Alert intake processing", 
                   queue_size=len(state.get("alert_queue", [])))
        
        # Initialize state if needed
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
        
        # Check for new alert
        if not state.get("current_alert") and state.get("alert_queue"):
            # Get next alert from queue
            state["current_alert"] = state["alert_queue"].pop(0)
            state["workflow_step"] = "analysis"
            state["agent_status"]["manager"] = "pending"
            
            # Update metrics
            state["metrics"]["alerts_processed"] += 1
            
            # Log workflow start
            state["workflow_history"].append({
                "step": "alert_intake",
                "timestamp": datetime.now().isoformat(),
                "alert_id": state["current_alert"].get("id", "unknown")
            })
        
        return state
    
    async def _human_approval(self, state: AgentState) -> AgentState:
        """Handle human approval workflow."""
        logger.info("Awaiting human approval")
        
        # In a real system, this would integrate with a UI or ticketing system
        # For now, we'll simulate approval
        state["workflow_step"] = "approval_pending"
        
        # Add to workflow history
        state["workflow_history"].append({
            "step": "human_approval_requested",
            "timestamp": datetime.now().isoformat(),
            "reason": "High-risk remediation requires approval"
        })
        
        # In production, this would wait for actual human input
        # For demo, auto-approve after logging
        state["approval_decision"] = "approved"
        
        return state
    
    async def _completion(self, state: AgentState) -> AgentState:
        """Handle workflow completion."""
        logger.info("Workflow completed",
                   alert_id=state.get("current_alert", {}).get("id", "unknown"))
        
        # Clear current alert
        state["current_alert"] = None
        state["workflow_step"] = "completed"
        
        # Reset agent status
        state["agent_status"] = {
            "manager": "idle",
            "hunter": "idle",
            "executor": "idle"
        }
        
        # Log completion
        state["workflow_history"].append({
            "step": "workflow_completed",
            "timestamp": datetime.now().isoformat()
        })
        
        return state
    
    async def _error_handler(self, state: AgentState) -> AgentState:
        """Handle errors in the workflow."""
        logger.error("Error handler triggered",
                    errors=state.get("errors", []))
        
        # Analyze errors and determine next action
        error_count = len(state.get("errors", []))
        
        if error_count < 3:
            # Retry
            state["error_action"] = "retry"
            logger.info("Retrying after error", retry_count=error_count)
        elif error_count < 5:
            # Escalate to human
            state["error_action"] = "escalate"
            logger.warning("Escalating to human after errors", error_count=error_count)
        else:
            # Abort
            state["error_action"] = "abort"
            logger.error("Aborting workflow after too many errors", error_count=error_count)
        
        return state
    
    def _route_from_manager(self, state: AgentState) -> Literal["investigate", "remediate", "dismiss", "error"]:
        """Route based on manager's decision."""
        # Check for errors
        if state.get("agent_status", {}).get("manager") == "error":
            return "error"
        
        # Get latest decision
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
        
        # Default to dismiss if no clear decision
        return "dismiss"
    
    def _route_from_review(self, state: AgentState) -> Literal["remediate", "escalate", "dismiss", "error"]:
        """Route based on manager's review after investigation."""
        # Check for errors
        if state.get("agent_status", {}).get("manager") == "error":
            return "error"
        
        # Check workflow step
        if state.get("workflow_step") == "remediation":
            return "remediate"
        elif state.get("workflow_step") == "escalation":
            return "escalate"
        elif state.get("workflow_step") == "completed":
            return "dismiss"
        
        # Default to remediate if investigation found issues
        investigations = state.get("investigations", {})
        current_alert_id = state.get("current_alert", {}).get("id")
        
        if current_alert_id and current_alert_id in investigations:
            investigation = investigations[current_alert_id]
            if hasattr(investigation, 'risk_score') and investigation.risk_score > 50:
                return "remediate"
        
        return "dismiss"
    
    def _route_from_executor(self, state: AgentState) -> Literal["completed", "approval_needed", "error"]:
        """Route based on executor's result."""
        # Check for errors
        if state.get("agent_status", {}).get("executor") == "error":
            return "error"
        
        # Check if approval is needed
        current_alert_id = state.get("current_alert", {}).get("id")
        remediation_plan = state.get("remediation_plans", {}).get(current_alert_id)
        
        if remediation_plan and getattr(remediation_plan, 'approval_required', False):
            # Check if already approved
            if not state.get("approval_decision"):
                return "approval_needed"
        
        # Check workflow step
        if state.get("workflow_step") == "completed":
            return "completed"
        
        return "completed"
    
    def _route_from_approval(self, state: AgentState) -> Literal["approved", "rejected", "modify"]:
        """Route based on human approval decision."""
        decision = state.get("approval_decision", "rejected")
        
        if decision == "approved":
            return "approved"
        elif decision == "modify":
            return "modify"
        else:
            return "rejected"
    
    def _route_from_error(self, state: AgentState) -> Literal["retry", "escalate", "abort"]:
        """Route based on error handler decision."""
        return state.get("error_action", "abort")
    
    async def process_alert(self, alert: SecurityAlert, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process a single security alert through the graph."""
        # Initialize state with the alert
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
        
        # Run the graph
        final_state = await self.app.ainvoke(initial_state)
        
        # Extract results
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
        """Process a stream of alerts through the graph."""
        # Initialize state with alert queue
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
        
        # Stream through the graph
        async for event in self.app.astream(initial_state):
            logger.info("Graph event", 
                       node=event.get("node"),
                       step=event.get("data", {}).get("workflow_step"))
            
            # Process events as needed
            if event.get("node") == "completion":
                # Alert completed, check for more in queue
                if event.get("data", {}).get("alert_queue"):
                    # Continue processing
                    continue
                else:
                    # All alerts processed
                    break