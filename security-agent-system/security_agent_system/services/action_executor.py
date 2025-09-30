"""安全應對行動的行動執行器服務。"""
import asyncio
from typing import Dict, Any, Optional, List
import httpx
import structlog
from datetime import datetime

from ..core.interfaces import IActionExecutor
from ..core.models import ActionType
from ..core.config import settings

logger = structlog.get_logger()


class ActionExecutorService(IActionExecutor):
    """用於執行安全應對行動的服務。"""
    
    def __init__(self):
        self.action_handlers = {
            ActionType.ISOLATE_HOST: self._isolate_host,
            ActionType.BLOCK_IP: self._block_ip,
            ActionType.DISABLE_USER: self._disable_user,
            ActionType.QUARANTINE_FILE: self._quarantine_file,
            ActionType.CREATE_TICKET: self._create_ticket,
            ActionType.SEND_NOTIFICATION: self._send_notification,
            ActionType.CUSTOM_SCRIPT: self._execute_custom_script
        }
        
        # 追蹤已執行的行動以供回滾
        self.executed_actions: Dict[str, Dict[str, Any]] = {}
        
    async def execute(
        self,
        action_type: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """執行一個安全行動。"""
        try:
            action_enum = ActionType[action_type]
            handler = self.action_handlers.get(action_enum)
            
            if not handler:
                raise ValueError(f"未知的行動類型：{action_type}")
                
            logger.info("執行行動中",
                       action_type=action_type,
                       parameters=parameters)
                       
            # 執行行動
            result = await handler(parameters)
            
            # 儲存以供可能的回滾
            action_id = result.get("action_id", str(datetime.utcnow().timestamp()))
            self.executed_actions[action_id] = {
                "action_type": action_type,
                "parameters": parameters,
                "result": result,
                "timestamp": datetime.utcnow()
            }
            
            return result
            
        except Exception as e:
            logger.error("行動執行失敗",
                        action_type=action_type,
                        error=str(e))
            return {
                "success": False,
                "error": str(e),
                "action_type": action_type
            }
            
    async def validate_action(
        self,
        action_type: str,
        parameters: Dict[str, Any]
    ) -> bool:
        """在執行前驗證行動參數。"""
        try:
            action_enum = ActionType[action_type]
            
            # 基本驗證規則
            if action_enum == ActionType.ISOLATE_HOST:
                return "hosts" in parameters and len(parameters["hosts"]) > 0
                
            elif action_enum == ActionType.BLOCK_IP:
                return "ips" in parameters and len(parameters["ips"]) > 0
                
            elif action_enum == ActionType.DISABLE_USER:
                return "users" in parameters and len(parameters["users"]) > 0
                
            elif action_enum == ActionType.QUARANTINE_FILE:
                return "file_paths" in parameters and len(parameters["file_paths"]) > 0
                
            elif action_enum == ActionType.CREATE_TICKET:
                return all(k in parameters for k in ["title", "description", "severity"])
                
            elif action_enum == ActionType.SEND_NOTIFICATION:
                return all(k in parameters for k in ["message", "recipients"])
                
            elif action_enum == ActionType.CUSTOM_SCRIPT:
                return "script_path" in parameters or "script_content" in parameters
                
            return False
            
        except Exception as e:
            logger.error("行動驗證失敗",
                        action_type=action_type,
                        error=str(e))
            return False
            
    async def rollback(self, action_id: str) -> bool:
        """回滾先前執行的行動。"""
        if action_id not in self.executed_actions:
            logger.warning("找不到要回滾的行動", action_id=action_id)
            return False
            
        try:
            action_data = self.executed_actions[action_id]
            action_type = ActionType[action_data["action_type"]]
            
            logger.info("正在回滾行動",
                       action_id=action_id,
                       action_type=action_data["action_type"])
                       
            # 根據行動類型執行回滾
            if action_type == ActionType.ISOLATE_HOST:
                await self._unisolate_host(action_data["parameters"])
                
            elif action_type == ActionType.BLOCK_IP:
                await self._unblock_ip(action_data["parameters"])
                
            elif action_type == ActionType.DISABLE_USER:
                await self._enable_user(action_data["parameters"])
                
            elif action_type == ActionType.QUARANTINE_FILE:
                await self._restore_file(action_data["parameters"])
                
            else:
                logger.warning("此行動類型沒有可用的回滾",
                             action_type=action_data["action_type"])
                return False
                
            # 從已執行的行動中移除
            del self.executed_actions[action_id]
            
            return True
            
        except Exception as e:
            logger.error("回滾失敗",
                        action_id=action_id,
                        error=str(e))
            return False
            
    # 行動實作方法
    
    async def _isolate_host(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """將主機與網路隔離。"""
        hosts = parameters.get("hosts", [])
        results = []
        
        for host in hosts:
            try:
                # 模擬對 EDR/防火牆的 API 呼叫
                logger.info("正在隔離主機", host=host)
                
                # 在實際實作中，會呼叫：
                # - EDR API (CrowdStrike, SentinelOne 等)
                # - 防火牆 API
                # - 網路交換器 API
                
                await asyncio.sleep(0.5)  # 模擬 API 延遲
                
                results.append({
                    "host": host,
                    "status": "isolated",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
            except Exception as e:
                logger.error("隔離主機失敗", host=host, error=str(e))
                results.append({
                    "host": host,
                    "status": "failed",
                    "error": str(e)
                })
                
        return {
            "success": all(r["status"] == "isolated" for r in results),
            "action_id": f"isolate_{datetime.utcnow().timestamp()}",
            "results": results
        }
        
    async def _block_ip(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """在防火牆上封鎖 IP 位址。"""
        ips = parameters.get("ips", [])
        duration = parameters.get("duration_hours", 24)
        results = []
        
        for ip in ips:
            try:
                logger.info("正在封鎖 IP", ip=ip, duration_hours=duration)
                
                # 在實際實作中，會呼叫：
                # - 防火牆 API (Palo Alto, Fortinet 等)
                # - 雲端安全群組 API
                # - CDN/WAF API
                
                await asyncio.sleep(0.3)  # 模擬 API 延遲
                
                results.append({
                    "ip": ip,
                    "status": "blocked",
                    "expiry": f"{duration} hours",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
            except Exception as e:
                logger.error("封鎖 IP 失敗", ip=ip, error=str(e))
                results.append({
                    "ip": ip,
                    "status": "failed",
                    "error": str(e)
                })
                
        return {
            "success": all(r["status"] == "blocked" for r in results),
            "action_id": f"block_ip_{datetime.utcnow().timestamp()}",
            "results": results
        }
        
    async def _disable_user(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """停用使用者帳戶。"""
        users = parameters.get("users", [])
        results = []
        
        for user in users:
            try:
                logger.info("正在停用使用者", user=user)
                
                # 在實際實作中，會呼叫：
                # - Active Directory API
                # - Azure AD Graph API
                # - LDAP
                # - 特定應用程式的使用者管理
                
                await asyncio.sleep(0.4)  # 模擬 API 延遲
                
                results.append({
                    "user": user,
                    "status": "disabled",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
            except Exception as e:
                logger.error("停用使用者失敗", user=user, error=str(e))
                results.append({
                    "user": user,
                    "status": "failed",
                    "error": str(e)
                })
                
        return {
            "success": all(r["status"] == "disabled" for r in results),
            "action_id": f"disable_user_{datetime.utcnow().timestamp()}",
            "results": results
        }
        
    async def _quarantine_file(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """隔離惡意檔案。"""
        file_paths = parameters.get("file_paths", [])
        hosts = parameters.get("hosts", [])
        results = []
        
        for file_path in file_paths:
            for host in hosts:
                try:
                    logger.info("正在隔離檔案",
                               file_path=file_path,
                               host=host)
                               
                    # 在實際實作中，會呼叫：
                    # - 用於檔案隔離的 EDR API
                    # - 防毒軟體 API
                    # - 遠端檔案系統操作
                    
                    await asyncio.sleep(0.6)  # 模擬 API 延遲
                    
                    results.append({
                        "file": file_path,
                        "host": host,
                        "status": "quarantined",
                        "backup_location": f"/quarantine/{datetime.utcnow().timestamp()}/{file_path}",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                except Exception as e:
                    logger.error("隔離檔案失敗",
                                file_path=file_path,
                                host=host,
                                error=str(e))
                    results.append({
                        "file": file_path,
                        "host": host,
                        "status": "failed",
                        "error": str(e)
                    })
                    
        return {
            "success": all(r["status"] == "quarantined" for r in results),
            "action_id": f"quarantine_{datetime.utcnow().timestamp()}",
            "results": results
        }
        
    async def _create_ticket(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """建立事件工單。"""
        try:
            logger.info("正在建立工單", parameters=parameters)
            
            # 在實際實作中，會呼叫：
            # - ServiceNow API
            # - Jira API
            # - PagerDuty API
            
            ticket_data = {
                "title": parameters.get("title"),
                "description": parameters.get("description"),
                "severity": parameters.get("severity", "medium"),
                "assignee": parameters.get("assignee", "soc-team"),
                "tags": parameters.get("tags", ["security", "automated"]),
                "created_at": datetime.utcnow().isoformat()
            }
            
            await asyncio.sleep(0.3)  # 模擬 API 延遲
            
            ticket_id = f"INC{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            
            return {
                "success": True,
                "action_id": f"ticket_{ticket_id}",
                "ticket_id": ticket_id,
                "ticket_url": f"https://tickets.company.com/incident/{ticket_id}",
                "data": ticket_data
            }
            
        except Exception as e:
            logger.error("建立工單失敗", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }
            
    async def _send_notification(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """傳送通知給收件人。"""
        try:
            message = parameters.get("message")
            recipients = parameters.get("recipients", [])
            priority = parameters.get("priority", "normal")
            
            logger.info("正在傳送通知",
                       num_recipients=len(recipients),
                       priority=priority)
                       
            # 在實際實作中，會使用通知服務
            
            await asyncio.sleep(0.2)  # 模擬傳送
            
            return {
                "success": True,
                "action_id": f"notify_{datetime.utcnow().timestamp()}",
                "recipients": recipients,
                "sent_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("傳送通知失敗", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }
            
    async def _execute_custom_script(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """執行自訂修復腳本。"""
        try:
            script_path = parameters.get("script_path")
            script_content = parameters.get("script_content")
            target_hosts = parameters.get("target_hosts", [])
            
            logger.info("正在執行自訂腳本",
                       script_path=script_path,
                       num_targets=len(target_hosts))
                       
            # 在實際實作中，會：
            # - 驗證腳本安全性
            # - 透過 SSH/WinRM/代理執行
            # - 收集結果
            
            await asyncio.sleep(1.0)  # 模擬執行
            
            return {
                "success": True,
                "action_id": f"script_{datetime.utcnow().timestamp()}",
                "script": script_path or "inline_script",
                "targets": target_hosts,
                "execution_time": "1.0s"
            }
            
        except Exception as e:
            logger.error("執行腳本失敗", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }
            
    # 回滾方法
    
    async def _unisolate_host(self, parameters: Dict[str, Any]) -> None:
        """恢復隔離主機的網路存取。"""
        hosts = parameters.get("hosts", [])
        for host in hosts:
            logger.info("正在解除隔離主機", host=host)
            await asyncio.sleep(0.3)
            
    async def _unblock_ip(self, parameters: Dict[str, Any]) -> None:
        """從防火牆移除 IP 封鎖。"""
        ips = parameters.get("ips", [])
        for ip in ips:
            logger.info("正在解除封鎖 IP", ip=ip)
            await asyncio.sleep(0.2)
            
    async def _enable_user(self, parameters: Dict[str, Any]) -> None:
        """重新啟用已停用的使用者帳戶。"""
        users = parameters.get("users", [])
        for user in users:
            logger.info("正在重新啟用使用者", user=user)
            await asyncio.sleep(0.3)
            
    async def _restore_file(self, parameters: Dict[str, Any]) -> None:
        """還原已隔離的檔案。"""
        file_paths = parameters.get("file_paths", [])
        hosts = parameters.get("hosts", [])
        for file_path in file_paths:
            for host in hosts:
                logger.info("正在還原檔案", file_path=file_path, host=host)
                await asyncio.sleep(0.4)