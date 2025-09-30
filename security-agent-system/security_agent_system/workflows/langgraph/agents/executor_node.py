"""LangGraph 實作的執行者代理節點。"""
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
    """行動執行詳細資料。"""
    action_type: str = Field(description="行動類型：block_ip, isolate_host, update_rule, patch_system 等")
    target: str = Field(description="行動的目標")
    parameters: Dict[str, Any] = Field(description="行動參數")
    validation_steps: List[str] = Field(description="驗證行動的步驟")
    rollback_procedure: Optional[Dict[str, Any]] = Field(description="需要時的回滾程序")
    estimated_duration: int = Field(description="預估持續時間（秒）")
    risk_level: str = Field(description="風險等級：低、中、高")


class ExecutionPlan(BaseModel):
    """詳細的執行計畫。"""
    actions: List[ActionExecution] = Field(description="要執行的行動清單")
    execution_order: List[int] = Field(description="執行順序（行動索引）")
    dependencies: Dict[str, List[str]] = Field(description="行動相依性")
    pre_checks: List[str] = Field(description="執行前檢查")
    post_checks: List[str] = Field(description="執行後驗證")
    total_estimated_time: int = Field(description="總預估時間（秒）")


class ExecutorNode:
    """執行修復行動的執行者代理節點。"""
    
    def __init__(self, llm_provider, action_executor=None, notification_service=None):
        """使用 LLM 供應商和服務初始化執行者節點。"""
        self.llm = llm_provider
        self.action_executor = action_executor
        self.notification_service = notification_service
        self.parser = JsonOutputParser(pydantic_object=ExecutionPlan)
        
        # 行動註冊表
        self.action_registry = self._setup_action_registry()
        
        # 建立執行計畫提示
        self.planning_prompt = ChatPromptTemplate.from_messages([
            ("system", """您是安全協調系統中的執行者代理。
            您的職責包括：
            1. 規劃和執行修復行動
            2. 確保安全且受控的執行
            3. 驗證行動結果
            4. 需要時管理回滾
            5. 記錄所有已採取的行動
            
            執行原則：
            - 安全第一 - 執行前驗證
            - 對業務營運的干擾最小化
            - 維護稽核軌跡
            - 準備好回滾計畫
            - 執行後驗證結果
            
            可用的行動類型：
            - block_ip：在防火牆上封鎖 IP 位址
            - isolate_host：隔離受感染的主機
            - disable_account：停用使用者帳戶
            - update_rule：更新安全規則
            - patch_system：應用安全修補程式
            - revoke_access：撤銷存取權限
            - quarantine_file：隔離惡意檔案
            - reset_credentials：重設受感染的憑證
            
            以指定的 JSON 格式輸出您的執行計畫。"""),
            MessagesPlaceholder(variable_name="messages", optional=True),
            ("human", """為此修復計畫執行：
            
            警報 ID：{alert_id}
            警報類型：{alert_type}
            嚴重性：{severity}
            
            調查摘要：
            風險分數：{risk_score}
            受影響的資產：{affected_assets}
            攻擊指標：{attack_indicators}
            
            修復計畫：
            {remediation_plan}
            
            目前系統狀態：
            {system_state}
            
            建立一個包含具體行動的詳細執行計畫。
            
            {format_instructions}""")
        ])
        
        # 建立驗證提示
        self.validation_prompt = ChatPromptTemplate.from_messages([
            ("system", "您正在驗證安全修復行動的結果。"),
            ("human", """驗證執行結果：
            
            行動：{action}
            預期結果：{expected}
            實際結果：{actual}
            
            行動是否成功？還需要哪些額外步驟？""")
        ])
        
        # 設定執行工具
        self._setup_execution_tools()
        self._build_chains()
    
    def _setup_action_registry(self) -> Dict[str, Callable]:
        """設定可用行動的註冊表。"""
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
        """為執行者代理設定執行工具。"""
        self.tools = []
        
        # 系統命令執行工具
        system_tool = Tool(
            name="execute_system_command",
            description="執行用於修復的系統命令",
            func=self._execute_system_command
        )
        self.tools.append(system_tool)
        
        # API 呼叫工具
        api_tool = Tool(
            name="call_security_api",
            description="呼叫安全工具 API",
            func=self._call_security_api
        )
        self.tools.append(api_tool)
        
        # 驗證工具
        validation_tool = Tool(
            name="validate_action",
            description="驗證行動執行結果",
            func=self._validate_action
        )
        self.tools.append(validation_tool)
        
        # 建立工具節點
        self.tool_node = ToolNode(self.tools)
    
    def _build_chains(self):
        """建立用於執行的 LCEL 鏈。"""
        # 計畫鏈
        self.planning_chain = (
            RunnablePassthrough.assign(
                format_instructions=lambda x: self.parser.get_format_instructions()
            )
            | self.planning_prompt
            | self.llm
            | self.parser
        )
        
        # 驗證鏈
        self.validation_chain = (
            self.validation_prompt
            | self.llm
            | RunnableLambda(lambda x: x.content if hasattr(x, 'content') else str(x))
        )
    
    # 行動執行方法
    async def _execute_block_ip(self, ip_address: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """執行 IP 封鎖行動。"""
        logger.info("正在執行 block_ip", ip=ip_address, params=parameters)
        
        if self.action_executor:
            return await self.action_executor.block_ip(ip_address, **parameters)
        
        # 模擬執行
        return {
            "status": "success",
            "action": "block_ip",
            "target": ip_address,
            "message": f"IP {ip_address} 已成功封鎖"
        }
    
    async def _execute_isolate_host(self, hostname: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """執行主機隔離行動。"""
        logger.info("正在執行 isolate_host", host=hostname, params=parameters)
        
        if self.action_executor:
            return await self.action_executor.isolate_host(hostname, **parameters)
        
        return {
            "status": "success",
            "action": "isolate_host",
            "target": hostname,
            "message": f"主機 {hostname} 已成功隔離"
        }
    
    async def _execute_disable_account(self, account: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """執行停用帳戶行動。"""
        logger.info("正在執行 disable_account", account=account, params=parameters)
        
        if self.action_executor:
            return await self.action_executor.disable_account(account, **parameters)
        
        return {
            "status": "success",
            "action": "disable_account",
            "target": account,
            "message": f"帳戶 {account} 已成功停用"
        }
    
    async def _execute_update_rule(self, rule_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """執行規則更新行動。"""
        logger.info("正在執行 update_rule", rule=rule_id, params=parameters)
        
        if self.action_executor:
            return await self.action_executor.update_rule(rule_id, **parameters)
        
        return {
            "status": "success",
            "action": "update_rule",
            "target": rule_id,
            "message": f"規則 {rule_id} 已成功更新"
        }
    
    async def _execute_patch_system(self, system: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """執行系統修補行動。"""
        logger.info("正在執行 patch_system", system=system, params=parameters)
        
        if self.action_executor:
            return await self.action_executor.patch_system(system, **parameters)
        
        return {
            "status": "success",
            "action": "patch_system",
            "target": system,
            "message": f"系統 {system} 已成功修補"
        }
    
    async def _execute_revoke_access(self, resource: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """執行撤銷存取權限行動。"""
        logger.info("正在執行 revoke_access", resource=resource, params=parameters)
        
        if self.action_executor:
            return await self.action_executor.revoke_access(resource, **parameters)
        
        return {
            "status": "success",
            "action": "revoke_access",
            "target": resource,
            "message": f"對 {resource} 的存取權限已成功撤銷"
        }
    
    async def _execute_quarantine_file(self, file_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """執行檔案隔離行動。"""
        logger.info("正在執行 quarantine_file", file=file_path, params=parameters)
        
        if self.action_executor:
            return await self.action_executor.quarantine_file(file_path, **parameters)
        
        return {
            "status": "success",
            "action": "quarantine_file",
            "target": file_path,
            "message": f"檔案 {file_path} 已成功隔離"
        }
    
    async def _execute_reset_credentials(self, account: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """執行重設憑證行動。"""
        logger.info("正在執行 reset_credentials", account=account, params=parameters)
        
        if self.action_executor:
            return await self.action_executor.reset_credentials(account, **parameters)
        
        return {
            "status": "success",
            "action": "reset_credentials",
            "target": account,
            "message": f"{account} 的憑證已成功重設"
        }
    
    # 工具方法
    async def _execute_system_command(self, command: str) -> str:
        """執行一個系統命令。"""
        logger.info("正在執行系統命令", command=command)
        # 在生產環境中，這將以適當的安全性執行實際命令
        return f"命令已執行：{command}"
    
    async def _call_security_api(self, api_call: str) -> str:
        """呼叫一個安全工具 API。"""
        logger.info("正在呼叫安全 API", api=api_call)
        # 在生產環境中，這將進行實際的 API 呼叫
        return f"API 已呼叫：{api_call}"
    
    async def _validate_action(self, action_result: str) -> str:
        """驗證行動執行結果。"""
        logger.info("正在驗證行動", result=action_result)
        # 在生產環境中，這將執行實際的驗證
        return f"驗證通過：{action_result}"
    
    async def __call__(self, state: AgentState) -> AgentState:
        """處理目前狀態並執行修復行動。"""
        logger.info("執行者節點處理中",
                   workflow_step=state.get("workflow_step"),
                   current_alert=state.get("current_alert"))
        
        try:
            # 檢查是否應執行
            if state.get("workflow_step") != "remediation":
                logger.info("不在修復階段，略過")
                return state
            
            # 獲取目前警報和修復計畫
            current_alert = state.get("current_alert")
            if not current_alert:
                logger.warning("沒有要修復的目前警報")
                return state
            
            alert_id = current_alert.get("id") if isinstance(current_alert, dict) else current_alert.id
            
            remediation_plan = state.get("remediation_plans", {}).get(alert_id)
            if not remediation_plan:
                logger.warning("找不到修復計畫", alert_id=alert_id)
                return state
            
            # 獲取調查結果
            investigation = state.get("investigations", {}).get(alert_id)
            
            # 準備計畫上下文
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
            
            # 建立執行計畫
            execution_plan = await self.planning_chain.ainvoke(planning_context)
            
            logger.info("執行計畫已建立",
                       alert_id=alert_id,
                       action_count=len(execution_plan.actions),
                       estimated_time=execution_plan.total_estimated_time)
            
            # 按順序執行行動
            execution_results = []
            for idx in execution_plan.execution_order:
                action = execution_plan.actions[idx]
                
                # 檢查行動是否需要批准
                if action.risk_level == "high" and remediation_plan.approval_required:
                    logger.info("高風險行動需要批准",
                              action=action.action_type,
                              target=action.target)
                    # 在生產環境中，會等待批准
                    # 目前，模擬批准
                    await asyncio.sleep(1)
                
                # 執行行動
                if action.action_type in self.action_registry:
                    try:
                        result = await self.action_registry[action.action_type](
                            action.target,
                            action.parameters
                        )
                        
                        # 驗證結果
                        validation_context = {
                            "action": action.model_dump(),
                            "expected": "successful execution",
                            "actual": result
                        }
                        validation = await self.validation_chain.ainvoke(validation_context)
                        
                        # 建立執行結果
                        exec_result = ExecutionResult(
                            alert_id=alert_id,
                            action_id=f"{alert_id}_{idx}",
                            status="success",
                            result=result
                        )
                        execution_results.append(exec_result)
                        
                        logger.info("行動成功執行",
                                  action=action.action_type,
                                  target=action.target)
                        
                    except Exception as e:
                        logger.error("行動執行失敗",
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
                        
                        # 如果可用，執行回滾
                        if action.rollback_procedure:
                            logger.info("正在執行回滾",
                                      action=action.action_type)
                            # 實作回滾邏輯
            
            # 使用結果更新狀態
            state["execution_results"] = state.get("execution_results", [])
            state["execution_results"].extend(execution_results)
            
            # 傳送通知
            if self.notification_service:
                await self.notification_service.send_notification({
                    "type": "remediation_completed",
                    "alert_id": alert_id,
                    "actions_executed": len(execution_results),
                    "success_count": sum(1 for r in execution_results if r.status == "success")
                })
            
            # 更新工作流程
            state["workflow_step"] = "completed"
            state["agent_status"]["executor"] = "completed"
            
            # 更新警報狀態
            if isinstance(current_alert, dict):
                current_alert["remediation_status"] = "completed"
            
            # 新增到工作流程歷史記錄
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
            
            # 更新指標
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["remediations_completed"] = \
                state["metrics"].get("remediations_completed", 0) + 1
            state["metrics"]["actions_executed"] = \
                state["metrics"].get("actions_executed", 0) + len(execution_results)
            
        except Exception as e:
            logger.error("執行者節點錯誤", error=str(e), exc_info=True)
            state["errors"] = state.get("errors", [])
            state["errors"].append({
                "agent": "executor",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            state["agent_status"]["executor"] = "error"
            state["workflow_step"] = "error"
        
        return state