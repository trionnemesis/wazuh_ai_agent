"""Manager Agent Node for LangGraph implementation."""
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
    """Manager agent decision output."""
    action: str = Field(description="Action to take: investigate, remediate, escalate, or dismiss")
    priority: int = Field(description="Priority level 1-5, where 1 is highest")
    reasoning: str = Field(description="Reasoning for the decision")
    remediation_required: bool = Field(description="Whether remediation is required")
    escalation_required: bool = Field(description="Whether escalation is required")
    additional_context: Dict[str, Any] = Field(default_factory=dict)


class ManagerNode:
    """Manager agent node that coordinates security response."""
    
    def __init__(self, llm_provider):
        """Initialize Manager node with LLM provider."""
        self.llm = llm_provider
        self.parser = JsonOutputParser(pydantic_object=ManagerDecision)
        
        # Create the decision prompt template
        self.decision_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the Manager Agent in a security orchestration system.
            Your responsibilities include:
            1. Analyzing security alerts and determining appropriate response
            2. Prioritizing incidents based on severity and impact
            3. Deciding whether to investigate, remediate, escalate, or dismiss
            4. Creating remediation plans when necessary
            5. Coordinating with Hunter and Executor agents
            
            Consider factors like:
            - Alert severity and confidence
            - Potential business impact
            - Available resources
            - Historical context
            - Current threat landscape
            
            Output your decision in the specified JSON format."""),
            MessagesPlaceholder(variable_name="messages"),
            ("human", """Analyze this security alert and make a decision:
            
            Alert Details:
            ID: {alert_id}
            Type: {alert_type}
            Severity: {severity}
            Source: {source}
            Description: {description}
            
            Investigation Status: {investigation_status}
            
            Additional Context:
            {context}
            
            {format_instructions}""")
        ])
        
        # Create remediation plan prompt
        self.remediation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are creating a remediation plan for a security incident.
            Consider:
            1. Immediate containment actions
            2. Investigation requirements
            3. Long-term fixes
            4. Rollback procedures
            5. Impact on business operations
            
            Create a detailed, actionable remediation plan."""),
            ("human", """Create a remediation plan for:
            
            Alert: {alert_details}
            Investigation Findings: {investigation_findings}
            Decision: {decision}
            
            Output a structured remediation plan with specific actions.""")
        ])
        
        # Build LCEL chains
        self._build_chains()
    
    def _build_chains(self):
        """Build LCEL chains for decision making and remediation planning."""
        # Decision chain
        self.decision_chain = (
            RunnablePassthrough.assign(
                format_instructions=lambda x: self.parser.get_format_instructions()
            )
            | self.decision_prompt
            | self.llm
            | self.parser
        )
        
        # Remediation planning chain
        self.remediation_chain = (
            self.remediation_prompt
            | self.llm
            | RunnableLambda(self._parse_remediation_plan)
        )
    
    def _parse_remediation_plan(self, output) -> Dict[str, Any]:
        """Parse LLM output into remediation plan structure."""
        # Extract structured data from LLM response
        content = output.content if hasattr(output, 'content') else str(output)
        
        # Parse the plan (this is a simplified version)
        actions = []
        lines = content.split('\n')
        current_action = {}
        
        for line in lines:
            if line.strip().startswith('- Action:'):
                if current_action:
                    actions.append(current_action)
                current_action = {'description': line.replace('- Action:', '').strip()}
            elif line.strip().startswith('  '):
                # Additional details for current action
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
        """Process the current state and make management decisions."""
        logger.info("Manager node processing", 
                   alert_count=len(state.get("alert_queue", [])),
                   current_alert=state.get("current_alert"))
        
        try:
            # Get current alert
            current_alert = state.get("current_alert")
            if not current_alert:
                # Check queue for new alerts
                if state.get("alert_queue"):
                    current_alert = state["alert_queue"].pop(0)
                    state["current_alert"] = current_alert
                else:
                    logger.info("No alerts to process")
                    return state
            
            # Convert to dict if it's a SecurityAlert object
            if isinstance(current_alert, SecurityAlert):
                alert_dict = current_alert.model_dump()
            else:
                alert_dict = current_alert
            
            # Prepare context for decision
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
            
            # Make decision
            decision = await self.decision_chain.ainvoke(context)
            
            # Log decision
            logger.info("Manager decision made",
                       alert_id=context["alert_id"],
                       action=decision.action,
                       priority=decision.priority)
            
            # Update state with decision
            state["decisions"] = state.get("decisions", [])
            state["decisions"].append({
                "agent": "manager",
                "timestamp": datetime.now().isoformat(),
                "alert_id": context["alert_id"],
                "decision": decision.model_dump()
            })
            
            # Update workflow step based on decision
            if decision.action == "investigate":
                state["workflow_step"] = "investigation"
                state["agent_status"]["hunter"] = "pending"
            elif decision.action == "remediate":
                # Create remediation plan
                investigation = state.get("investigations", {}).get(context["alert_id"])
                
                plan_context = {
                    "alert_details": alert_dict,
                    "investigation_findings": investigation.model_dump() if investigation else {},
                    "decision": decision.model_dump()
                }
                
                remediation_result = await self.remediation_chain.ainvoke(plan_context)
                
                # Create RemediationPlan object
                plan = RemediationPlan(
                    alert_id=context["alert_id"],
                    priority=decision.priority,
                    actions=remediation_result["actions"],
                    estimated_impact="medium",  # This should be determined by the LLM
                    approval_required=decision.priority <= 2
                )
                
                state["remediation_plans"] = state.get("remediation_plans", {})
                state["remediation_plans"][context["alert_id"]] = plan
                
                state["workflow_step"] = "remediation"
                state["agent_status"]["executor"] = "pending"
            elif decision.action == "escalate":
                state["workflow_step"] = "escalation"
                # Handle escalation logic
            else:  # dismiss
                state["workflow_step"] = "completed"
                if isinstance(current_alert, dict):
                    current_alert["investigation_status"] = "dismissed"
                    current_alert["remediation_status"] = "not_required"
            
            # Update agent status
            state["agent_status"]["manager"] = "completed"
            
            # Add to workflow history
            state["workflow_history"] = state.get("workflow_history", [])
            state["workflow_history"].append({
                "step": "manager_decision",
                "timestamp": datetime.now().isoformat(),
                "result": decision.model_dump()
            })
            
        except Exception as e:
            logger.error("Manager node error", error=str(e), exc_info=True)
            state["errors"] = state.get("errors", [])
            state["errors"].append({
                "agent": "manager",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            state["agent_status"]["manager"] = "error"
        
        return state