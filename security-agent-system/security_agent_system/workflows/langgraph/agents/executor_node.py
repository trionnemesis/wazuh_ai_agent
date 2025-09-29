"""Executor Agent Node for LangGraph implementation."""
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import structlog
import asyncio
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.tools import Tool
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from ..state import AgentState, ExecutionResult, RemediationPlan

logger = structlog.get_logger()


class ActionExecution(BaseModel):
    """Action execution details."""
    action_type: str = Field(description="Type of action: block_ip, isolate_host, update_rule, patch_system, etc.")
    target: str = Field(description="Target of the action")
    parameters: Dict[str, Any] = Field(description="Action parameters")
    validation_steps: List[str] = Field(description="Steps to validate action")
    rollback_procedure: Optional[Dict[str, Any]] = Field(description="Rollback procedure if needed")
    estimated_duration: int = Field(description="Estimated duration in seconds")
    risk_level: str = Field(description="Risk level: low, medium, high")


class ExecutionPlan(BaseModel):
    """Detailed execution plan."""
    actions: List[ActionExecution] = Field(description="List of actions to execute")
    execution_order: List[int] = Field(description="Order of execution (action indices)")
    dependencies: Dict[str, List[str]] = Field(description="Action dependencies")
    pre_checks: List[str] = Field(description="Pre-execution checks")
    post_checks: List[str] = Field(description="Post-execution validation")
    total_estimated_time: int = Field(description="Total estimated time in seconds")


class ExecutorNode:
    """Executor agent node that performs remediation actions."""
    
    def __init__(self, llm_provider, action_executor=None, notification_service=None):
        """Initialize Executor node with LLM provider and services."""
        self.llm = llm_provider
        self.action_executor = action_executor
        self.notification_service = notification_service
        self.parser = JsonOutputParser(pydantic_object=ExecutionPlan)
        
        # Action registry
        self.action_registry = self._setup_action_registry()
        
        # Create execution planning prompt
        self.planning_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the Executor Agent in a security orchestration system.
            Your responsibilities include:
            1. Planning and executing remediation actions
            2. Ensuring safe and controlled execution
            3. Validating action results
            4. Managing rollbacks if needed
            5. Documenting all actions taken
            
            Execution principles:
            - Safety first - verify before executing
            - Minimal disruption to business operations
            - Maintain audit trail
            - Have rollback plans ready
            - Validate results after execution
            
            Available action types:
            - block_ip: Block IP address at firewall
            - isolate_host: Isolate compromised host
            - disable_account: Disable user account
            - update_rule: Update security rules
            - patch_system: Apply security patches
            - revoke_access: Revoke access permissions
            - quarantine_file: Quarantine malicious files
            - reset_credentials: Reset compromised credentials
            
            Output your execution plan in the specified JSON format."""),
            MessagesPlaceholder(variable_name="messages", optional=True),
            ("human", """Plan execution for this remediation:
            
            Alert ID: {alert_id}
            Alert Type: {alert_type}
            Severity: {severity}
            
            Investigation Summary:
            Risk Score: {risk_score}
            Affected Assets: {affected_assets}
            Attack Indicators: {attack_indicators}
            
            Remediation Plan:
            {remediation_plan}
            
            Current System State:
            {system_state}
            
            Create a detailed execution plan with specific actions.
            
            {format_instructions}""")
        ])
        
        # Create validation prompt
        self.validation_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are validating the results of security remediation actions."),
            ("human", """Validate the execution results:
            
            Action: {action}
            Expected Result: {expected}
            Actual Result: {actual}
            
            Is the action successful? What additional steps are needed?""")
        ])
        
        # Setup execution tools
        self._setup_execution_tools()
        self._build_chains()
    
    def _setup_action_registry(self) -> Dict[str, Callable]:
        """Setup registry of available actions."""
        return {
            "block_ip": self._execute_block_ip,
            "isolate_host": self._execute_isolate_host,
            "disable_account": self._execute_disable_account,
            "update_rule": self._execute_update_rule,
            "patch_system": self._execute_patch_system,
            "revoke_access": self._execute_revoke_access,
            "quarantine_file": self._execute_quarantine_file,
            "reset_credentials": self._execute_reset_credentials
        }
    
    def _setup_execution_tools(self):
        """Setup execution tools for the Executor agent."""
        self.tools = []
        
        # System command execution tool
        system_tool = Tool(
            name="execute_system_command",
            description="Execute system commands for remediation",
            func=self._execute_system_command
        )
        self.tools.append(system_tool)
        
        # API call tool
        api_tool = Tool(
            name="call_security_api",
            description="Call security tool APIs",
            func=self._call_security_api
        )
        self.tools.append(api_tool)
        
        # Validation tool
        validation_tool = Tool(
            name="validate_action",
            description="Validate action execution results",
            func=self._validate_action
        )
        self.tools.append(validation_tool)
        
        # Create tool node
        self.tool_node = ToolNode(self.tools)
    
    def _build_chains(self):
        """Build LCEL chains for execution."""
        # Planning chain
        self.planning_chain = (
            RunnablePassthrough.assign(
                format_instructions=lambda x: self.parser.get_format_instructions()
            )
            | self.planning_prompt
            | self.llm
            | self.parser
        )
        
        # Validation chain
        self.validation_chain = (
            self.validation_prompt
            | self.llm
            | RunnableLambda(lambda x: x.content if hasattr(x, 'content') else str(x))
        )
    
    # Action execution methods
    async def _execute_block_ip(self, ip_address: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute IP blocking action."""
        logger.info("Executing block_ip", ip=ip_address, params=parameters)
        
        if self.action_executor:
            return await self.action_executor.block_ip(ip_address, **parameters)
        
        # Simulate execution
        return {
            "status": "success",
            "action": "block_ip",
            "target": ip_address,
            "message": f"IP {ip_address} blocked successfully"
        }
    
    async def _execute_isolate_host(self, hostname: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute host isolation action."""
        logger.info("Executing isolate_host", host=hostname, params=parameters)
        
        if self.action_executor:
            return await self.action_executor.isolate_host(hostname, **parameters)
        
        return {
            "status": "success",
            "action": "isolate_host",
            "target": hostname,
            "message": f"Host {hostname} isolated successfully"
        }
    
    async def _execute_disable_account(self, account: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute account disable action."""
        logger.info("Executing disable_account", account=account, params=parameters)
        
        if self.action_executor:
            return await self.action_executor.disable_account(account, **parameters)
        
        return {
            "status": "success",
            "action": "disable_account",
            "target": account,
            "message": f"Account {account} disabled successfully"
        }
    
    async def _execute_update_rule(self, rule_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute rule update action."""
        logger.info("Executing update_rule", rule=rule_id, params=parameters)
        
        if self.action_executor:
            return await self.action_executor.update_rule(rule_id, **parameters)
        
        return {
            "status": "success",
            "action": "update_rule",
            "target": rule_id,
            "message": f"Rule {rule_id} updated successfully"
        }
    
    async def _execute_patch_system(self, system: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute system patching action."""
        logger.info("Executing patch_system", system=system, params=parameters)
        
        if self.action_executor:
            return await self.action_executor.patch_system(system, **parameters)
        
        return {
            "status": "success",
            "action": "patch_system",
            "target": system,
            "message": f"System {system} patched successfully"
        }
    
    async def _execute_revoke_access(self, resource: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute access revocation action."""
        logger.info("Executing revoke_access", resource=resource, params=parameters)
        
        if self.action_executor:
            return await self.action_executor.revoke_access(resource, **parameters)
        
        return {
            "status": "success",
            "action": "revoke_access",
            "target": resource,
            "message": f"Access to {resource} revoked successfully"
        }
    
    async def _execute_quarantine_file(self, file_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute file quarantine action."""
        logger.info("Executing quarantine_file", file=file_path, params=parameters)
        
        if self.action_executor:
            return await self.action_executor.quarantine_file(file_path, **parameters)
        
        return {
            "status": "success",
            "action": "quarantine_file",
            "target": file_path,
            "message": f"File {file_path} quarantined successfully"
        }
    
    async def _execute_reset_credentials(self, account: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute credential reset action."""
        logger.info("Executing reset_credentials", account=account, params=parameters)
        
        if self.action_executor:
            return await self.action_executor.reset_credentials(account, **parameters)
        
        return {
            "status": "success",
            "action": "reset_credentials",
            "target": account,
            "message": f"Credentials for {account} reset successfully"
        }
    
    # Tool methods
    async def _execute_system_command(self, command: str) -> str:
        """Execute a system command."""
        logger.info("Executing system command", command=command)
        # In production, this would execute actual commands with proper security
        return f"Command executed: {command}"
    
    async def _call_security_api(self, api_call: str) -> str:
        """Call a security tool API."""
        logger.info("Calling security API", api=api_call)
        # In production, this would make actual API calls
        return f"API called: {api_call}"
    
    async def _validate_action(self, action_result: str) -> str:
        """Validate action execution results."""
        logger.info("Validating action", result=action_result)
        # In production, this would perform actual validation
        return f"Validation passed for: {action_result}"
    
    async def __call__(self, state: AgentState) -> AgentState:
        """Process the current state and execute remediation actions."""
        logger.info("Executor node processing", 
                   workflow_step=state.get("workflow_step"),
                   current_alert=state.get("current_alert"))
        
        try:
            # Check if we should execute
            if state.get("workflow_step") != "remediation":
                logger.info("Not in remediation phase, skipping")
                return state
            
            # Get current alert and remediation plan
            current_alert = state.get("current_alert")
            if not current_alert:
                logger.warning("No current alert to remediate")
                return state
            
            alert_id = current_alert.get("id") if isinstance(current_alert, dict) else current_alert.id
            
            remediation_plan = state.get("remediation_plans", {}).get(alert_id)
            if not remediation_plan:
                logger.warning("No remediation plan found", alert_id=alert_id)
                return state
            
            # Get investigation results
            investigation = state.get("investigations", {}).get(alert_id)
            
            # Prepare planning context
            planning_context = {
                "alert_id": alert_id,
                "alert_type": current_alert.get("type", "unknown"),
                "severity": current_alert.get("severity", "unknown"),
                "risk_score": investigation.risk_score if investigation else 0,
                "affected_assets": investigation.affected_assets if investigation else [],
                "attack_indicators": investigation.attack_indicators if investigation else [],
                "remediation_plan": remediation_plan.model_dump() if hasattr(remediation_plan, 'model_dump') else remediation_plan,
                "system_state": state.get("external_context", {}),
                "messages": state.get("messages", [])
            }
            
            # Create execution plan
            execution_plan = await self.planning_chain.ainvoke(planning_context)
            
            logger.info("Execution plan created",
                       alert_id=alert_id,
                       action_count=len(execution_plan.actions),
                       estimated_time=execution_plan.total_estimated_time)
            
            # Execute actions in order
            execution_results = []
            for idx in execution_plan.execution_order:
                action = execution_plan.actions[idx]
                
                # Check if action requires approval
                if action.risk_level == "high" and remediation_plan.approval_required:
                    logger.info("High-risk action requires approval", 
                              action=action.action_type,
                              target=action.target)
                    # In production, would wait for approval
                    # For now, simulate approval
                    await asyncio.sleep(1)
                
                # Execute action
                if action.action_type in self.action_registry:
                    try:
                        result = await self.action_registry[action.action_type](
                            action.target,
                            action.parameters
                        )
                        
                        # Validate result
                        validation_context = {
                            "action": action.model_dump(),
                            "expected": "successful execution",
                            "actual": result
                        }
                        validation = await self.validation_chain.ainvoke(validation_context)
                        
                        # Create execution result
                        exec_result = ExecutionResult(
                            alert_id=alert_id,
                            action_id=f"{alert_id}_{idx}",
                            status="success",
                            result=result
                        )
                        execution_results.append(exec_result)
                        
                        logger.info("Action executed successfully",
                                  action=action.action_type,
                                  target=action.target)
                        
                    except Exception as e:
                        logger.error("Action execution failed",
                                   action=action.action_type,
                                   target=action.target,
                                   error=str(e))
                        
                        exec_result = ExecutionResult(
                            alert_id=alert_id,
                            action_id=f"{alert_id}_{idx}",
                            status="failed",
                            result={},
                            error=str(e)
                        )
                        execution_results.append(exec_result)
                        
                        # Execute rollback if available
                        if action.rollback_procedure:
                            logger.info("Executing rollback",
                                      action=action.action_type)
                            # Implement rollback logic
            
            # Update state with results
            state["execution_results"] = state.get("execution_results", [])
            state["execution_results"].extend(execution_results)
            
            # Send notifications
            if self.notification_service:
                await self.notification_service.send_notification({
                    "type": "remediation_completed",
                    "alert_id": alert_id,
                    "actions_executed": len(execution_results),
                    "success_count": sum(1 for r in execution_results if r.status == "success")
                })
            
            # Update workflow
            state["workflow_step"] = "completed"
            state["agent_status"]["executor"] = "completed"
            
            # Update alert status
            if isinstance(current_alert, dict):
                current_alert["remediation_status"] = "completed"
            
            # Add to workflow history
            state["workflow_history"] = state.get("workflow_history", [])
            state["workflow_history"].append({
                "step": "executor_remediation",
                "timestamp": datetime.now().isoformat(),
                "result": {
                    "actions_planned": len(execution_plan.actions),
                    "actions_executed": len(execution_results),
                    "success_count": sum(1 for r in execution_results if r.status == "success")
                }
            })
            
            # Update metrics
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["remediations_completed"] = \
                state["metrics"].get("remediations_completed", 0) + 1
            state["metrics"]["actions_executed"] = \
                state["metrics"].get("actions_executed", 0) + len(execution_results)
            
        except Exception as e:
            logger.error("Executor node error", error=str(e), exc_info=True)
            state["errors"] = state.get("errors", [])
            state["errors"].append({
                "agent": "executor",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            state["agent_status"]["executor"] = "error"
            state["workflow_step"] = "error"
        
        return state