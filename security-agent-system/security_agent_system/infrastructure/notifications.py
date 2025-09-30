"""通知服務實作。"""
import asyncio
from typing import Dict, Any, List, Optional
import json
import httpx
from slack_sdk.webhook.async_client import AsyncWebhookClient
import structlog

from ..core.interfaces import INotificationService
from ..core.models import ExecutionReport
from ..core.config import settings

logger = structlog.get_logger()


class SlackNotificationService(INotificationService):
    """Slack 通知服務實作。"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.slack_webhook_url
        if not self.webhook_url:
            logger.warning("未設定 Slack webhook URL")
            
        self.client = AsyncWebhookClient(self.webhook_url) if self.webhook_url else None
        self.channel = settings.slack_channel
        
    async def send_alert(
        self,
        title: str,
        message: str,
        severity: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """傳送警報通知到 Slack。"""
        if not self.client:
            logger.warning("未設定 Slack 客戶端，略過通知")
            return False
            
        try:
            # 將嚴重性對應到顏色
            color_map = {
                "low": "#36a64f",      # 綠色
                "medium": "#ff9900",   # 橘色
                "high": "#ff6600",     # 深橘色
                "critical": "#ff0000", # 紅色
                "info": "#0099ff"      # 藍色
            }
            
            color = color_map.get(severity.lower(), "#808080")
            
            # 建立 Slack 訊息
            slack_attachments = [{
                "fallback": f"{title}: {message}",
                "color": color,
                "pretext": title,
                "text": message,
                "footer": "安全代理系統",
                "ts": int(asyncio.get_event_loop().time())
            }]
            
            # 新增自訂附件
            if attachments:
                for att in attachments:
                    slack_attachments.append({
                        "color": color,
                        "title": att.get("title", ""),
                        "text": att.get("text", ""),
                        "fields": att.get("fields", [])
                    })
                    
            # 傳送到 Slack
            response = await self.client.send(
                text=title,
                attachments=slack_attachments,
                channel=self.channel
            )
            
            if response.status_code == 200:
                logger.debug("已傳送 Slack 警報", title=title)
                return True
            else:
                logger.error("Slack 警報傳送失敗",
                           status_code=response.status_code,
                           body=response.body)
                return False
                
        except Exception as e:
            logger.error("傳送 Slack 警報失敗", error=str(e))
            return False
            
    async def request_approval(
        self,
        title: str,
        message: str,
        actions: List[Dict[str, Any]],
        callback_url: str
    ) -> str:
        """使用互動式按鈕請求批准。"""
        if not self.client:
            logger.warning("未設定 Slack 客戶端，自動批准")
            return "auto-approved"
            
        try:
            # 建立帶有按鈕的互動式訊息
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": title
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message
                    }
                },
                {
                    "type": "divider"
                }
            ]
            
            # 新增動作詳細資訊
            for i, action in enumerate(actions):
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*動作 {i+1}:* {action['description']}\n"
                                f"*類型:* `{action['type']}`\n"
                                f"*風險:* {action['risk']}"
                    }
                })
                
            # 新增批准按鈕
            request_id = f"approval_{int(asyncio.get_event_loop().time())}"
            
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "全部批准"
                        },
                        "style": "primary",
                        "value": json.dumps({
                            "request_id": request_id,
                            "callback_url": callback_url,
                            "approved": True
                        }),
                        "action_id": "approve_all"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "全部拒絕"
                        },
                        "style": "danger",
                        "value": json.dumps({
                            "request_id": request_id,
                            "callback_url": callback_url,
                            "approved": False
                        }),
                        "action_id": "reject_all"
                    }
                ]
            })
            
            # 傳送互動式訊息
            response = await self.client.send(
                text=title,
                blocks=blocks,
                channel=self.channel
            )
            
            if response.status_code == 200:
                logger.info("已傳送批准請求",
                          request_id=request_id,
                          num_actions=len(actions))
                return request_id
            else:
                logger.error("傳送批准請求失敗",
                           status_code=response.status_code)
                return ""
                
        except Exception as e:
            logger.error("傳送批准請求失敗", error=str(e))
            return ""
            
    async def send_report(
        self,
        report: ExecutionReport,
        recipients: List[str]
    ) -> bool:
        """傳送執行報告。"""
        if not self.client:
            logger.warning("未設定 Slack 客戶端，略過報告")
            return False
            
        try:
            # 格式化 Slack 報告
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"安全報告 - {report.task_id}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*高階主管摘要:*\n{report.executive_summary}"
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*信賴度:* {report.analysis_confidence:.0%}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*誤報率:* {report.false_positive_probability:.0%}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*威脅敘述:*\n{report.threat_narrative[:500]}..."
                    }
                }
            ]
            
            # 新增建議摘要
            if report.recommended_actions:
                rec_text = "*建議動作:*\n"
                for i, action in enumerate(report.recommended_actions[:5]):
                    rec_text += f"{i+1}. {action.description} (優先級: {action.priority})\n"
                    
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": rec_text
                    }
                })
                
            # 新增時間軸摘要
            if report.timeline:
                timeline_text = "*關鍵事件:*\n"
                for event in report.timeline[:5]:
                    timeline_text += f"• {event['timestamp']}: {event['event']}\n"
                    
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": timeline_text
                    }
                })
                
            # 傳送到 Slack
            response = await self.client.send(
                text=f"安全報告 - {report.task_id}",
                blocks=blocks,
                channel=self.channel
            )
            
            if response.status_code == 200:
                logger.info("已傳送報告", report_id=report.report_id)
                
                # 透過提及通知收件人 (如果支援)
                if recipients:
                    mention_text = f"報告已傳送給: {', '.join(f'<@{r}>' for r in recipients)}"
                    await self.client.send(
                        text=mention_text,
                        channel=self.channel
                    )
                    
                return True
            else:
                logger.error("傳送報告失敗",
                           status_code=response.status_code)
                return False
                
        except Exception as e:
            logger.error("傳送報告失敗", error=str(e))
            return False
            
    async def handle_interaction(self, payload: Dict[str, Any]) -> None:
        """處理 Slack 互動回呼。"""
        try:
            # 提取動作詳細資訊
            action = payload["actions"][0]
            action_id = action["action_id"]
            value = json.loads(action["value"])
            
            user = payload["user"]["username"]
            
            # 處理批准/拒絕
            if action_id in ["approve_all", "reject_all"]:
                approved = value["approved"]
                request_id = value["request_id"]
                callback_url = value["callback_url"]
                
                # 傳送回呼給執行者代理
                async with httpx.AsyncClient() as client:
                    await client.post(
                        callback_url,
                        json={
                            "request_id": request_id,
                            "approved": approved,
                            "approver": user,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                    )
                    
                # 更新 Slack 訊息
                update_text = f"✅ 已由 {user} 批准" if approved else f"❌ 已由 {user} 拒絕"
                
                await self.client.send(
                    text=update_text,
                    channel=self.channel,
                    thread_ts=payload["message"]["ts"]
                )
                
                logger.info("已處理互動",
                          action_id=action_id,
                          approved=approved,
                          user=user)
                          
        except Exception as e:
            logger.error("處理互動失敗", error=str(e))


class EmailNotificationService(INotificationService):
    """電子郵件通知服務實作 (佔位符)。"""
    
    async def send_alert(
        self,
        title: str,
        message: str,
        severity: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """傳送電子郵件警報。"""
        logger.info("電子郵件通知 (未實作)",
                   title=title,
                   severity=severity)
        return True
        
    async def request_approval(
        self,
        title: str,
        message: str,
        actions: List[Dict[str, Any]],
        callback_url: str
    ) -> str:
        """請求電子郵件批准。"""
        logger.info("電子郵件批准請求 (未實作)",
                   title=title,
                   num_actions=len(actions))
        return "email-approval-123"
        
    async def send_report(
        self,
        report: ExecutionReport,
        recipients: List[str]
    ) -> bool:
        """傳送電子郵件報告。"""
        logger.info("電子郵件報告 (未實作)",
                   report_id=report.report_id,
                   recipients=recipients)
        return True


class MultiChannelNotificationService(INotificationService):
    """結合多個服務的多頻道通知服務。"""
    
    def __init__(self, services: List[INotificationService]):
        self.services = services
        
    async def send_alert(
        self,
        title: str,
        message: str,
        severity: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """傳送警報到所有頻道。"""
        results = await asyncio.gather(
            *[service.send_alert(title, message, severity, attachments)
              for service in self.services],
            return_exceptions=True
        )
        
        # 如果至少有一個成功，則返回 True
        return any(r is True for r in results if not isinstance(r, Exception))
        
    async def request_approval(
        self,
        title: str,
        message: str,
        actions: List[Dict[str, Any]],
        callback_url: str
    ) -> str:
        """從第一個可用的頻道請求批准。"""
        for service in self.services:
            try:
                request_id = await service.request_approval(
                    title, message, actions, callback_url
                )
                if request_id:
                    return request_id
            except Exception as e:
                logger.error("服務批准請求失敗",
                           service=type(service).__name__,
                           error=str(e))
                continue
                
        return ""
        
    async def send_report(
        self,
        report: ExecutionReport,
        recipients: List[str]
    ) -> bool:
        """傳送報告到所有頻道。"""
        results = await asyncio.gather(
            *[service.send_report(report, recipients)
              for service in self.services],
            return_exceptions=True
        )
        
        return any(r is True for r in results if not isinstance(r, Exception))