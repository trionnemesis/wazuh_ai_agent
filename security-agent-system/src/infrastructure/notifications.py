"""Notification service implementations."""
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
    """Slack notification service implementation."""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.slack_webhook_url
        if not self.webhook_url:
            logger.warning("Slack webhook URL not configured")
            
        self.client = AsyncWebhookClient(self.webhook_url) if self.webhook_url else None
        self.channel = settings.slack_channel
        
    async def send_alert(
        self,
        title: str,
        message: str,
        severity: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Send an alert notification to Slack."""
        if not self.client:
            logger.warning("Slack client not configured, skipping notification")
            return False
            
        try:
            # Map severity to color
            color_map = {
                "low": "#36a64f",      # Green
                "medium": "#ff9900",   # Orange
                "high": "#ff6600",     # Dark Orange
                "critical": "#ff0000", # Red
                "info": "#0099ff"      # Blue
            }
            
            color = color_map.get(severity.lower(), "#808080")
            
            # Build Slack message
            slack_attachments = [{
                "fallback": f"{title}: {message}",
                "color": color,
                "pretext": title,
                "text": message,
                "footer": "Security Agent System",
                "ts": int(asyncio.get_event_loop().time())
            }]
            
            # Add custom attachments
            if attachments:
                for att in attachments:
                    slack_attachments.append({
                        "color": color,
                        "title": att.get("title", ""),
                        "text": att.get("text", ""),
                        "fields": att.get("fields", [])
                    })
                    
            # Send to Slack
            response = await self.client.send(
                text=title,
                attachments=slack_attachments,
                channel=self.channel
            )
            
            if response.status_code == 200:
                logger.debug("Slack alert sent", title=title)
                return True
            else:
                logger.error("Slack alert failed",
                           status_code=response.status_code,
                           body=response.body)
                return False
                
        except Exception as e:
            logger.error("Failed to send Slack alert", error=str(e))
            return False
            
    async def request_approval(
        self,
        title: str,
        message: str,
        actions: List[Dict[str, Any]],
        callback_url: str
    ) -> str:
        """Request approval with interactive buttons."""
        if not self.client:
            logger.warning("Slack client not configured, auto-approving")
            return "auto-approved"
            
        try:
            # Create interactive message with buttons
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
            
            # Add action details
            for i, action in enumerate(actions):
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Action {i+1}:* {action['description']}\n"
                                f"*Type:* `{action['type']}`\n"
                                f"*Risk:* {action['risk']}"
                    }
                })
                
            # Add approval buttons
            request_id = f"approval_{int(asyncio.get_event_loop().time())}"
            
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Approve All"
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
                            "text": "Reject All"
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
            
            # Send interactive message
            response = await self.client.send(
                text=title,
                blocks=blocks,
                channel=self.channel
            )
            
            if response.status_code == 200:
                logger.info("Approval request sent",
                          request_id=request_id,
                          num_actions=len(actions))
                return request_id
            else:
                logger.error("Failed to send approval request",
                           status_code=response.status_code)
                return ""
                
        except Exception as e:
            logger.error("Failed to send approval request", error=str(e))
            return ""
            
    async def send_report(
        self,
        report: ExecutionReport,
        recipients: List[str]
    ) -> bool:
        """Send execution report."""
        if not self.client:
            logger.warning("Slack client not configured, skipping report")
            return False
            
        try:
            # Format report for Slack
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"Security Report - {report.task_id}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Executive Summary:*\n{report.executive_summary}"
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
                            "text": f"*Confidence:* {report.analysis_confidence:.0%}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*False Positive:* {report.false_positive_probability:.0%}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Threat Narrative:*\n{report.threat_narrative[:500]}..."
                    }
                }
            ]
            
            # Add recommendations summary
            if report.recommended_actions:
                rec_text = "*Recommended Actions:*\n"
                for i, action in enumerate(report.recommended_actions[:5]):
                    rec_text += f"{i+1}. {action.description} (Priority: {action.priority})\n"
                    
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": rec_text
                    }
                })
                
            # Add timeline summary
            if report.timeline:
                timeline_text = "*Key Events:*\n"
                for event in report.timeline[:5]:
                    timeline_text += f"• {event['timestamp']}: {event['event']}\n"
                    
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": timeline_text
                    }
                })
                
            # Send to Slack
            response = await self.client.send(
                text=f"Security Report - {report.task_id}",
                blocks=blocks,
                channel=self.channel
            )
            
            if response.status_code == 200:
                logger.info("Report sent", report_id=report.report_id)
                
                # Notify recipients via mention (if supported)
                if recipients:
                    mention_text = f"Report sent to: {', '.join(f'<@{r}>' for r in recipients)}"
                    await self.client.send(
                        text=mention_text,
                        channel=self.channel
                    )
                    
                return True
            else:
                logger.error("Failed to send report",
                           status_code=response.status_code)
                return False
                
        except Exception as e:
            logger.error("Failed to send report", error=str(e))
            return False
            
    async def handle_interaction(self, payload: Dict[str, Any]) -> None:
        """Handle Slack interaction callbacks."""
        try:
            # Extract action details
            action = payload["actions"][0]
            action_id = action["action_id"]
            value = json.loads(action["value"])
            
            user = payload["user"]["username"]
            
            # Process approval/rejection
            if action_id in ["approve_all", "reject_all"]:
                approved = value["approved"]
                request_id = value["request_id"]
                callback_url = value["callback_url"]
                
                # Send callback to executor agent
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
                    
                # Update Slack message
                update_text = f"✅ Approved by {user}" if approved else f"❌ Rejected by {user}"
                
                await self.client.send(
                    text=update_text,
                    channel=self.channel,
                    thread_ts=payload["message"]["ts"]
                )
                
                logger.info("Interaction processed",
                          action_id=action_id,
                          approved=approved,
                          user=user)
                          
        except Exception as e:
            logger.error("Failed to handle interaction", error=str(e))


class EmailNotificationService(INotificationService):
    """Email notification service implementation (placeholder)."""
    
    async def send_alert(
        self,
        title: str,
        message: str,
        severity: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Send email alert."""
        logger.info("Email notification (not implemented)",
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
        """Request email approval."""
        logger.info("Email approval request (not implemented)",
                   title=title,
                   num_actions=len(actions))
        return "email-approval-123"
        
    async def send_report(
        self,
        report: ExecutionReport,
        recipients: List[str]
    ) -> bool:
        """Send email report."""
        logger.info("Email report (not implemented)",
                   report_id=report.report_id,
                   recipients=recipients)
        return True


class MultiChannelNotificationService(INotificationService):
    """Multi-channel notification service that combines multiple services."""
    
    def __init__(self, services: List[INotificationService]):
        self.services = services
        
    async def send_alert(
        self,
        title: str,
        message: str,
        severity: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Send alert to all channels."""
        results = await asyncio.gather(
            *[service.send_alert(title, message, severity, attachments)
              for service in self.services],
            return_exceptions=True
        )
        
        # Return True if at least one succeeded
        return any(r is True for r in results if not isinstance(r, Exception))
        
    async def request_approval(
        self,
        title: str,
        message: str,
        actions: List[Dict[str, Any]],
        callback_url: str
    ) -> str:
        """Request approval from first available channel."""
        for service in self.services:
            try:
                request_id = await service.request_approval(
                    title, message, actions, callback_url
                )
                if request_id:
                    return request_id
            except Exception as e:
                logger.error("Service approval request failed",
                           service=type(service).__name__,
                           error=str(e))
                continue
                
        return ""
        
    async def send_report(
        self,
        report: ExecutionReport,
        recipients: List[str]
    ) -> bool:
        """Send report to all channels."""
        results = await asyncio.gather(
            *[service.send_report(report, recipients)
              for service in self.services],
            return_exceptions=True
        )
        
        return any(r is True for r in results if not isinstance(r, Exception))
