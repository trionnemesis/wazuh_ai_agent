"""Executor Agent: Final analysis and response execution specialist."""
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
import structlog
from enum import Enum

from ..core.interfaces import (
    IExecutorAgent, IMessageBroker, ILLMProvider,
    INotificationService, IActionExecutor
)
from ..core.models import (
    Task, TaskStatus, ExecutionMessage, ThreatProfile,
    ExecutionReport, ApprovalRequest, ExecutionResult,
    RecommendedAction, ActionType
)
from ..core.config import settings

logger = structlog.get_logger()


class ExecutorAgent(IExecutorAgent):
    """
    Executor Agent - The Action Specialist
    
    Responsibilities:
    1. Final threat analysis and synthesis
    2. Generate human-readable reports
    3. Request human approval for actions
    4. Execute approved security responses
    """
    
    def __init__(
        self,
        message_broker: IMessageBroker,
        llm_provider: ILLMProvider,
        notification_service: INotificationService,
        action_executor: IActionExecutor
    ):
        self._agent_id = f"executor-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        self._agent_type = "executor"
        self.broker = message_broker
        self.llm = llm_provider
        self.notifier = notification_service
        self.action_executor = action_executor
        
        # Execution state
        self.active_executions: Dict[str, ExecutionMessage] = {}
        self.pending_approvals: Dict[str, ApprovalRequest] = {}
        self.execution_reports: Dict[str, ExecutionReport] = {}
        
        # Performance tracking
        self.metrics = {
            "reports_generated": 0,
            "approvals_requested": 0,
            "approvals_received": 0,
            "actions_executed": 0,
            "actions_failed": 0,
            "avg_analysis_time": 0.0,
            "avg_approval_time": 0.0
        }
        
    @property
    def agent_id(self) -> str:
        return self._agent_id
        
    @property
    def agent_type(self) -> str:
        return self._agent_type
        
    async def initialize(self) -> None:
        """Initialize the Executor Agent."""
        await self.broker.connect()
        
        # Subscribe to execution queue
        await self.broker.subscribe(
            settings.execution_queue,
            self._handle_execution_request
        )
        
        logger.info("Executor Agent initialized", agent_id=self.agent_id)
        
    async def start(self) -> None:
        """Start the Executor Agent's main loop."""
        logger.info("Executor Agent starting", agent_id=self.agent_id)
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self._approval_monitor_loop()),
            asyncio.create_task(self._metrics_reporting_loop()),
            asyncio.create_task(self._cleanup_loop())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Executor Agent stopping")
            for task in tasks:
                task.cancel()
                
    async def stop(self) -> None:
        """Stop the Executor Agent."""
        await self.broker.disconnect()
        logger.info("Executor Agent stopped", agent_id=self.agent_id)
        
    async def health_check(self) -> Dict[str, Any]:
        """Return agent health status."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "status": "healthy",
            "active_executions": len(self.active_executions),
            "pending_approvals": len(self.pending_approvals),
            "metrics": dict(self.metrics)
        }
        
    async def analyze_threat(self, message: ExecutionMessage) -> ExecutionReport:
        """Perform final comprehensive threat analysis."""
        start_time = datetime.utcnow()
        task = message.task
        profile = message.threat_profile
        
        logger.info("Starting threat analysis",
                   task_id=task.task_id,
                   risk_score=profile.overall_risk_score,
                   category=profile.threat_category)
                   
        self.metrics["reports_generated"] += 1
        
        try:
            # Generate executive summary
            executive_summary = await self._generate_executive_summary(profile)
            
            # Generate threat narrative
            threat_narrative = await self._generate_threat_narrative(profile)
            
            # Generate technical details
            technical_details = await self._generate_technical_analysis(profile)
            
            # Create timeline
            timeline = await self._create_incident_timeline(profile)
            
            # Generate recommendations
            recommendations = await self.generate_recommendations(profile)
            
            # Calculate confidence metrics
            confidence_metrics = self._calculate_confidence_metrics(profile)
            
            # Compile evidence
            evidence = self._compile_evidence(profile)
            
            # Create execution report
            report = ExecutionReport(
                task_id=task.task_id,
                executive_summary=executive_summary,
                threat_narrative=threat_narrative,
                technical_details=technical_details,
                ioc_summary=self._extract_iocs(profile),
                timeline=timeline,
                recommended_actions=recommendations,
                analysis_confidence=confidence_metrics["confidence"],
                false_positive_probability=confidence_metrics["false_positive_prob"],
                evidence=evidence,
                references=self._generate_references(profile)
            )
            
            # Store report
            self.execution_reports[task.task_id] = report
            
            # Update metrics
            analysis_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_avg_analysis_time(analysis_time)
            
            logger.info("Threat analysis completed",
                       task_id=task.task_id,
                       num_recommendations=len(recommendations),
                       analysis_time_seconds=analysis_time)
                       
            return report
            
        except Exception as e:
            logger.error("Threat analysis failed",
                        task_id=task.task_id,
                        error=str(e))
            raise
            
    async def generate_recommendations(
        self,
        threat_profile: ThreatProfile
    ) -> List[RecommendedAction]:
        """Generate detailed action recommendations using advanced LLM."""
        prompt = f"""
        Based on this comprehensive threat analysis, generate specific security response recommendations:
        
        Threat Category: {threat_profile.threat_category}
        Risk Score: {threat_profile.overall_risk_score:.2f}
        Threat Actor: {threat_profile.threat_actor or 'Unknown'}
        
        Key Findings:
        - Attack Paths: {len(threat_profile.graph_context.attack_paths)} identified
        - Similar Incidents: {len(threat_profile.vector_context.similar_alerts)} found
        - Affected Assets: {list(threat_profile.asset_criticality.keys())}
        - Detected Patterns: {', '.join(threat_profile.vector_context.detected_patterns)}
        
        Asset Criticality:
        {json.dumps(threat_profile.asset_criticality, indent=2)}
        
        Generate 3-5 specific, actionable recommendations with:
        1. Action type (ISOLATE_HOST, BLOCK_IP, DISABLE_USER, etc.)
        2. Priority (1-5, where 1 is highest)
        3. Specific parameters
        4. Risk assessment
        5. Estimated impact
        
        Consider the organization's security posture and minimize business disruption.
        Return as JSON list.
        """
        
        try:
            response = await self.llm.generate(
                prompt=prompt,
                temperature=0.2,
                max_tokens=1000
            )
            
            recommendations_data = json.loads(response)
            recommendations = []
            
            for rec_data in recommendations_data:
                recommendation = RecommendedAction(
                    action_type=ActionType[rec_data["action_type"]],
                    priority=rec_data["priority"],
                    description=rec_data["description"],
                    parameters=rec_data["parameters"],
                    risk_level=rec_data["risk_level"],
                    potential_impact=rec_data["potential_impact"],
                    rollback_available=rec_data.get("rollback_available", False),
                    automation_ready=rec_data.get("automation_ready", True),
                    requires_approval=rec_data.get("requires_approval", True),
                    estimated_duration_seconds=rec_data.get("duration", 60)
                )
                recommendations.append(recommendation)
                
            # Sort by priority
            recommendations.sort(key=lambda x: x.priority)
            
            return recommendations
            
        except Exception as e:
            logger.error("Failed to generate recommendations", error=str(e))
            
            # Fallback recommendations based on threat category
            return self._generate_fallback_recommendations(threat_profile)
            
    async def request_approval(self, report: ExecutionReport) -> bool:
        """Request human approval for recommended actions."""
        task_id = report.task_id
        
        logger.info("Requesting approval",
                   task_id=task_id,
                   num_actions=len(report.recommended_actions))
                   
        self.metrics["approvals_requested"] += 1
        
        # Filter actions requiring approval
        actions_for_approval = [
            action for action in report.recommended_actions
            if action.requires_approval
        ]
        
        # Auto-execute low-risk actions if enabled
        if settings.auto_execute_low_risk:
            auto_actions = [
                action for action in report.recommended_actions
                if not action.requires_approval and action.risk_level == "low"
            ]
            
            for action in auto_actions:
                asyncio.create_task(
                    self._execute_action_async(action, task_id, "auto-approved")
                )
                
        if not actions_for_approval:
            return True  # No approval needed
            
        # Create approval request
        approval_request = ApprovalRequest(
            task_id=task_id,
            execution_report=report,
            requested_actions=actions_for_approval,
            timeout_minutes=30,
            escalation_contacts=["security-manager@company.com"]
        )
        
        self.pending_approvals[approval_request.request_id] = approval_request
        
        # Send notification
        approval_sent = await self._send_approval_notification(approval_request)
        
        if not approval_sent:
            logger.error("Failed to send approval request", task_id=task_id)
            return False
            
        # Wait for approval (async - handled by callback)
        return True
        
    async def execute_action(
        self,
        action: Dict[str, Any],
        approval_id: str
    ) -> Dict[str, Any]:
        """Execute an approved security action."""
        start_time = datetime.utcnow()
        
        logger.info("Executing action",
                   action_type=action["action_type"],
                   approval_id=approval_id)
                   
        self.metrics["actions_executed"] += 1
        
        try:
            # Validate action
            is_valid = await self.action_executor.validate_action(
                action["action_type"],
                action["parameters"]
            )
            
            if not is_valid:
                raise ValueError("Action validation failed")
                
            # Execute action
            result = await self.action_executor.execute(
                action["action_type"],
                action["parameters"]
            )
            
            # Create execution result
            execution_result = ExecutionResult(
                action_id=action["action_id"],
                task_id=action.get("task_id", "unknown"),
                success=result.get("success", False),
                execution_time_seconds=(datetime.utcnow() - start_time).total_seconds(),
                output=result,
                executed_by=self.agent_id,
                approval_id=approval_id
            )
            
            logger.info("Action executed successfully",
                       action_id=action["action_id"],
                       duration_seconds=execution_result.execution_time_seconds)
                       
            return execution_result.dict()
            
        except Exception as e:
            logger.error("Action execution failed",
                        action_type=action["action_type"],
                        error=str(e))
                        
            self.metrics["actions_failed"] += 1
            
            return {
                "success": False,
                "error": str(e),
                "action_id": action.get("action_id"),
                "timestamp": datetime.utcnow().isoformat()
            }
            
    async def _handle_execution_request(self, message: Dict[str, Any]) -> None:
        """Handle incoming execution request from Hunter Agent."""
        try:
            execution_message = ExecutionMessage(**message)
            task_id = execution_message.task.task_id
            
            # Store active execution
            self.active_executions[task_id] = execution_message
            
            # Perform threat analysis
            report = await self.analyze_threat(execution_message)
            
            # Send initial notification
            await self._send_threat_notification(report)
            
            # Request approval if needed
            if settings.enable_human_approval:
                await self.request_approval(report)
            else:
                # Execute all recommendations automatically (dangerous!)
                logger.warning("Human approval disabled - executing all actions",
                             task_id=task_id)
                             
                for action in report.recommended_actions:
                    await self._execute_action_async(action, task_id, "auto-approved")
                    
            # Clean up
            del self.active_executions[task_id]
            
        except Exception as e:
            logger.error("Failed to handle execution request", error=str(e))
            
    async def _generate_executive_summary(self, profile: ThreatProfile) -> str:
        """Generate executive summary using LLM."""
        prompt = f"""
        Generate a concise executive summary (3-4 sentences) for this security incident:
        
        Threat Type: {profile.threat_category}
        Risk Level: {profile.overall_risk_score:.2f} (scale 0-1)
        Affected Assets: {len(profile.asset_criticality)} systems
        Impact: {json.dumps(profile.impact_assessment)}
        
        The summary should be suitable for C-level executives and board members.
        Focus on business impact and required actions.
        """
        
        summary = await self.llm.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=200
        )
        
        return summary.strip()
        
    async def _generate_threat_narrative(self, profile: ThreatProfile) -> str:
        """Generate detailed threat narrative."""
        prompt = f"""
        Create a detailed threat narrative that tells the story of this security incident:
        
        Initial Alert: {profile.alert.title}
        Time: {profile.alert.timestamp}
        
        Attack Patterns Detected:
        {json.dumps(profile.graph_context.attack_paths[:3], indent=2)}
        
        Similar Historical Incidents: {len(profile.vector_context.similar_alerts)}
        
        Threat Actor: {profile.threat_actor or 'Unknown'}
        Campaign: {profile.campaign_id or 'Not linked to known campaign'}
        
        Write a narrative that explains:
        1. How the attack likely started
        2. What the attacker did
        3. What their objectives might be
        4. Current status and risk
        
        Use clear, non-technical language where possible.
        """
        
        narrative = await self.llm.generate(
            prompt=prompt,
            temperature=0.4,
            max_tokens=800
        )
        
        return narrative.strip()
        
    async def _generate_technical_analysis(self, profile: ThreatProfile) -> Dict[str, Any]:
        """Generate detailed technical analysis."""
        return {
            "attack_vectors": self._analyze_attack_vectors(profile),
            "vulnerability_analysis": self._analyze_vulnerabilities(profile),
            "network_analysis": self._analyze_network_activity(profile),
            "behavioral_analysis": self._analyze_behavior_patterns(profile),
            "threat_intelligence": self._compile_threat_intel(profile),
            "forensic_artifacts": self._identify_forensic_artifacts(profile)
        }
        
    async def _create_incident_timeline(self, profile: ThreatProfile) -> List[Dict[str, Any]]:
        """Create detailed incident timeline."""
        timeline = []
        
        # Initial detection
        timeline.append({
            "timestamp": profile.alert.timestamp.isoformat(),
            "event": "Initial Alert",
            "description": profile.alert.title,
            "severity": profile.alert.severity,
            "source": profile.alert.source
        })
        
        # Add events from graph analysis
        for path in profile.graph_context.attack_paths[:5]:  # Limit to 5 paths
            for i, node in enumerate(path):
                if isinstance(node, dict) and "timestamp" in node:
                    timeline.append({
                        "timestamp": node["timestamp"],
                        "event": f"Attack Step {i+1}",
                        "description": node.get("description", "Unknown action"),
                        "entity": node.get("entity"),
                        "confidence": node.get("confidence", 0.5)
                    })
                    
        # Add similar incidents
        for alert in profile.vector_context.similar_alerts[:3]:
            timeline.append({
                "timestamp": alert.get("timestamp", profile.alert.timestamp).isoformat(),
                "event": "Similar Alert",
                "description": alert.get("title", "Related incident"),
                "correlation": alert.get("score", 0)
            })
            
        # Sort by timestamp
        timeline.sort(key=lambda x: x["timestamp"])
        
        return timeline
        
    def _calculate_confidence_metrics(self, profile: ThreatProfile) -> Dict[str, float]:
        """Calculate confidence in the analysis."""
        factors = {
            "graph_evidence": min(len(profile.graph_context.attack_paths) / 5, 1.0) * 0.3,
            "vector_similarity": (1 - profile.vector_context.anomaly_score) * 0.2,
            "threat_intel": (1.0 if profile.threat_actor else 0.5) * 0.2,
            "pattern_match": min(len(profile.vector_context.detected_patterns) / 3, 1.0) * 0.3
        }
        
        confidence = sum(factors.values())
        
        # Calculate false positive probability
        fp_factors = {
            "low_similarity": profile.vector_context.anomaly_score * 0.4,
            "no_patterns": (0.5 if not profile.vector_context.detected_patterns else 0) * 0.3,
            "low_severity": (0.3 if profile.alert.severity == "LOW" else 0) * 0.3
        }
        
        false_positive_prob = sum(fp_factors.values())
        
        return {
            "confidence": confidence,
            "false_positive_prob": false_positive_prob
        }
        
    def _compile_evidence(self, profile: ThreatProfile) -> List[Dict[str, Any]]:
        """Compile supporting evidence."""
        evidence = []
        
        # Graph evidence
        for i, path in enumerate(profile.graph_context.attack_paths[:3]):
            evidence.append({
                "type": "attack_path",
                "id": f"path_{i+1}",
                "description": f"Attack path with {len(path)} steps",
                "confidence": 0.8,
                "details": path
            })
            
        # Vector evidence
        for i, alert in enumerate(profile.vector_context.similar_alerts[:3]):
            evidence.append({
                "type": "similar_incident",
                "id": f"incident_{i+1}",
                "description": alert.get("title", "Similar alert"),
                "similarity": alert.get("score", 0),
                "timestamp": alert.get("timestamp")
            })
            
        # IOC evidence
        for ioc in profile.graph_context.iocs[:5]:
            evidence.append({
                "type": "ioc",
                "id": f"ioc_{ioc.get('value', 'unknown')[:8]}",
                "description": f"{ioc.get('type', 'unknown')} indicator",
                "value": ioc.get("value"),
                "confidence": ioc.get("confidence", 0.5)
            })
            
        return evidence
        
    def _extract_iocs(self, profile: ThreatProfile) -> List[Dict[str, Any]]:
        """Extract and format IOCs."""
        iocs = []
        
        # From alert
        for ip in profile.alert.source_ips:
            iocs.append({"type": "ip", "value": ip, "direction": "source"})
        for ip in profile.alert.destination_ips:
            iocs.append({"type": "ip", "value": ip, "direction": "destination"})
        for hash_val in profile.alert.file_hashes:
            iocs.append({"type": "file_hash", "value": hash_val})
            
        # From graph context
        iocs.extend(profile.graph_context.iocs)
        
        # Deduplicate
        seen = set()
        unique_iocs = []
        for ioc in iocs:
            key = f"{ioc['type']}:{ioc['value']}"
            if key not in seen:
                seen.add(key)
                unique_iocs.append(ioc)
                
        return unique_iocs
        
    def _generate_references(self, profile: ThreatProfile) -> List[str]:
        """Generate references and links."""
        references = []
        
        # MITRE ATT&CK references
        for ttp in profile.graph_context.ttps:
            references.append(f"https://attack.mitre.org/techniques/{ttp}/")
            
        # Threat actor references
        if profile.threat_actor:
            references.append(f"Internal KB: /threats/actors/{profile.threat_actor}")
            
        # Campaign references
        if profile.campaign_id:
            references.append(f"Internal KB: /threats/campaigns/{profile.campaign_id}")
            
        return references
        
    def _generate_fallback_recommendations(
        self,
        profile: ThreatProfile
    ) -> List[RecommendedAction]:
        """Generate basic recommendations when LLM fails."""
        recommendations = []
        
        # High-risk default action
        if profile.overall_risk_score > 0.7:
            recommendations.append(
                RecommendedAction(
                    action_type=ActionType.ISOLATE_HOST,
                    priority=1,
                    description="Isolate affected systems to prevent lateral movement",
                    parameters={
                        "hosts": list(profile.asset_criticality.keys())
                    },
                    risk_level="low",
                    potential_impact="System unavailability for isolated hosts",
                    requires_approval=True
                )
            )
            
        # Block malicious IPs
        malicious_ips = [
            ioc["value"] for ioc in profile.graph_context.iocs
            if ioc.get("type") == "ip" and ioc.get("confidence", 0) > 0.7
        ]
        
        if malicious_ips:
            recommendations.append(
                RecommendedAction(
                    action_type=ActionType.BLOCK_IP,
                    priority=2,
                    description="Block confirmed malicious IP addresses",
                    parameters={"ips": malicious_ips},
                    risk_level="low",
                    potential_impact="Minimal - blocking external IPs",
                    requires_approval=True
                )
            )
            
        # Always create ticket
        recommendations.append(
            RecommendedAction(
                action_type=ActionType.CREATE_TICKET,
                priority=3,
                description="Create incident ticket for tracking and investigation",
                parameters={
                    "severity": "high" if profile.overall_risk_score > 0.7 else "medium",
                    "title": f"Security Incident: {profile.threat_category}",
                    "assignee": "soc-team"
                },
                risk_level="low",
                potential_impact="None - administrative action",
                requires_approval=False
            )
        )
        
        return recommendations
        
    def _analyze_attack_vectors(self, profile: ThreatProfile) -> List[Dict[str, Any]]:
        """Analyze attack vectors from the profile."""
        vectors = []
        
        # Analyze each attack path
        for path in profile.graph_context.attack_paths[:5]:
            vector = {
                "type": "network_path",
                "steps": len(path),
                "entry_point": path[0] if path else None,
                "target": path[-1] if path else None,
                "techniques": []
            }
            
            # Extract techniques from path
            for node in path:
                if isinstance(node, dict) and "technique" in node:
                    vector["techniques"].append(node["technique"])
                    
            vectors.append(vector)
            
        return vectors
        
    def _analyze_vulnerabilities(self, profile: ThreatProfile) -> Dict[str, Any]:
        """Analyze vulnerabilities that may have been exploited."""
        vuln_analysis = {
            "exploited": [],
            "at_risk": [],
            "patches_available": []
        }
        
        # Check asset vulnerabilities
        for asset, vulns in profile.asset_vulnerabilities.items():
            for vuln in vulns:
                vuln_info = {
                    "cve": vuln,
                    "asset": asset,
                    "severity": "high"  # Would be looked up in real system
                }
                
                # Simple heuristic - if asset is in attack path, vuln might be exploited
                if any(asset in str(path) for path in profile.graph_context.attack_paths):
                    vuln_analysis["exploited"].append(vuln_info)
                else:
                    vuln_analysis["at_risk"].append(vuln_info)
                    
        return vuln_analysis
        
    def _analyze_network_activity(self, profile: ThreatProfile) -> Dict[str, Any]:
        """Analyze network activity patterns."""
        return {
            "suspicious_connections": len(profile.alert.source_ips),
            "data_exfiltration_risk": profile.impact_assessment.get("data_exposure", 0),
            "c2_indicators": any(
                "C2" in pattern or "COMMAND" in pattern
                for pattern in profile.vector_context.detected_patterns
            ),
            "lateral_movement": any(
                "LATERAL" in pattern
                for pattern in profile.vector_context.detected_patterns
            )
        }
        
    def _analyze_behavior_patterns(self, profile: ThreatProfile) -> Dict[str, Any]:
        """Analyze behavioral patterns."""
        return {
            "patterns_detected": profile.vector_context.detected_patterns,
            "anomaly_score": profile.vector_context.anomaly_score,
            "historical_occurrence": profile.vector_context.occurrence_count,
            "time_based_pattern": "PERIODIC_ACTIVITY" in profile.vector_context.detected_patterns
        }
        
    def _compile_threat_intel(self, profile: ThreatProfile) -> Dict[str, Any]:
        """Compile threat intelligence information."""
        return {
            "threat_actor": profile.threat_actor,
            "campaign": profile.campaign_id,
            "ttps": profile.graph_context.ttps,
            "related_campaigns": profile.graph_context.related_campaigns,
            "confidence": 0.8 if profile.threat_actor else 0.3
        }
        
    def _identify_forensic_artifacts(self, profile: ThreatProfile) -> List[Dict[str, Any]]:
        """Identify key forensic artifacts for investigation."""
        artifacts = []
        
        # File artifacts
        for hash_val in profile.alert.file_hashes:
            artifacts.append({
                "type": "file",
                "value": hash_val,
                "description": "Suspicious file hash",
                "collection_method": "endpoint_agent"
            })
            
        # Network artifacts
        for ip in profile.alert.source_ips:
            artifacts.append({
                "type": "network",
                "value": f"pcap_filter: host {ip}",
                "description": "Network traffic capture filter",
                "collection_method": "network_tap"
            })
            
        # Memory artifacts
        if profile.threat_category in ["MALWARE", "INTRUSION"]:
            artifacts.append({
                "type": "memory",
                "value": "full_memory_dump",
                "description": "Memory dump for malware analysis",
                "collection_method": "endpoint_agent"
            })
            
        return artifacts
        
    async def _send_threat_notification(self, report: ExecutionReport) -> bool:
        """Send initial threat notification."""
        try:
            # Format notification
            severity = "critical" if report.analysis_confidence > 0.8 else "high"
            
            message = f"""
🚨 **Security Threat Detected**

**Summary:** {report.executive_summary}

**Risk Level:** {report.analysis_confidence:.0%}
**False Positive Probability:** {report.false_positive_probability:.0%}

**Recommended Actions:** {len(report.recommended_actions)}

View full report: [Report #{report.report_id}]
            """
            
            # Send notification
            success = await self.notifier.send_alert(
                title=f"Security Alert - Task {report.task_id}",
                message=message.strip(),
                severity=severity,
                attachments=[{
                    "title": "Technical Details",
                    "text": json.dumps(report.technical_details, indent=2)[:500] + "..."
                }]
            )
            
            return success
            
        except Exception as e:
            logger.error("Failed to send threat notification", error=str(e))
            return False
            
    async def _send_approval_notification(self, approval: ApprovalRequest) -> bool:
        """Send approval request notification."""
        try:
            # Format approval request
            actions_summary = "\n".join([
                f"{i+1}. {action.description} (Priority: {action.priority})"
                for i, action in enumerate(approval.requested_actions)
            ])
            
            message = f"""
⚠️ **Action Approval Required**

**Task ID:** {approval.task_id}
**Report:** {approval.execution_report.executive_summary}

**Requested Actions:**
{actions_summary}

**Timeout:** {approval.timeout_minutes} minutes

Please review and approve/reject these actions.
            """
            
            # Create callback URL
            callback_url = f"https://api.security.company/approvals/{approval.request_id}"
            
            # Send approval request
            request_id = await self.notifier.request_approval(
                title=f"Approval Required - {approval.task_id}",
                message=message.strip(),
                actions=[{
                    "action_id": action.action_id,
                    "type": action.action_type,
                    "description": action.description,
                    "risk": action.risk_level
                } for action in approval.requested_actions],
                callback_url=callback_url
            )
            
            return bool(request_id)
            
        except Exception as e:
            logger.error("Failed to send approval notification", error=str(e))
            return False
            
    async def _execute_action_async(
        self,
        action: RecommendedAction,
        task_id: str,
        approval_id: str
    ) -> None:
        """Execute action asynchronously."""
        try:
            action_dict = action.dict()
            action_dict["task_id"] = task_id
            
            result = await self.execute_action(action_dict, approval_id)
            
            # Send completion notification
            if result.get("success"):
                await self.notifier.send_alert(
                    title=f"Action Completed - {action.action_type}",
                    message=f"Successfully executed: {action.description}",
                    severity="info"
                )
            else:
                await self.notifier.send_alert(
                    title=f"Action Failed - {action.action_type}",
                    message=f"Failed to execute: {action.description}\nError: {result.get('error')}",
                    severity="error"
                )
                
        except Exception as e:
            logger.error("Async action execution failed",
                        action_type=action.action_type,
                        error=str(e))
                        
    def _update_avg_analysis_time(self, analysis_time: float) -> None:
        """Update average analysis time metric."""
        current_avg = self.metrics["avg_analysis_time"]
        report_count = self.metrics["reports_generated"]
        
        self.metrics["avg_analysis_time"] = (
            (current_avg * (report_count - 1) + analysis_time) / report_count
        )
        
    def _update_avg_approval_time(self, approval_time: float) -> None:
        """Update average approval time metric."""
        current_avg = self.metrics["avg_approval_time"]
        approval_count = self.metrics["approvals_received"]
        
        if approval_count > 0:
            self.metrics["avg_approval_time"] = (
                (current_avg * (approval_count - 1) + approval_time) / approval_count
            )
            
    async def _approval_monitor_loop(self) -> None:
        """Monitor approval requests and handle timeouts."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                current_time = datetime.utcnow()
                
                for request_id, approval in list(self.pending_approvals.items()):
                    # Check timeout
                    elapsed = (current_time - approval.requested_at).total_seconds() / 60
                    
                    if elapsed > approval.timeout_minutes:
                        logger.warning("Approval timeout",
                                     request_id=request_id,
                                     elapsed_minutes=elapsed)
                                     
                        # Escalate
                        await self.notifier.send_alert(
                            title=f"URGENT: Approval Timeout - {approval.task_id}",
                            message=f"Approval request has timed out. Escalating to: {', '.join(approval.escalation_contacts)}",
                            severity="critical"
                        )
                        
                        # Remove from pending
                        del self.pending_approvals[request_id]
                        
            except Exception as e:
                logger.error("Approval monitoring failed", error=str(e))
                
    async def _metrics_reporting_loop(self) -> None:
        """Report metrics periodically."""
        while True:
            try:
                await asyncio.sleep(300)  # Report every 5 minutes
                
                logger.info("Executor Agent metrics",
                          metrics=dict(self.metrics),
                          active_executions=len(self.active_executions),
                          pending_approvals=len(self.pending_approvals))
                          
            except Exception as e:
                logger.error("Metrics reporting failed", error=str(e))
                
    async def _cleanup_loop(self) -> None:
        """Clean up old execution reports."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run hourly
                
                cutoff_time = datetime.utcnow() - timedelta(days=7)
                
                # Clean old reports
                old_reports = [
                    task_id for task_id, report in self.execution_reports.items()
                    if report.generated_at < cutoff_time
                ]
                
                for task_id in old_reports:
                    del self.execution_reports[task_id]
                    
                logger.debug("Cleanup completed",
                           removed_reports=len(old_reports))
                           
            except Exception as e:
                logger.error("Cleanup failed", error=str(e))
                
    async def handle_approval_response(
        self,
        request_id: str,
        approved: bool,
        approver: str,
        comments: Optional[str] = None
    ) -> None:
        """Handle approval response from human."""
        if request_id not in self.pending_approvals:
            logger.warning("Unknown approval request", request_id=request_id)
            return
            
        approval = self.pending_approvals[request_id]
        approval.approved = approved
        approval.approver = approver
        approval.approval_timestamp = datetime.utcnow()
        approval.approval_comments = comments
        
        # Update metrics
        self.metrics["approvals_received"] += 1
        approval_time = (approval.approval_timestamp - approval.requested_at).total_seconds()
        self._update_avg_approval_time(approval_time)
        
        logger.info("Approval received",
                   request_id=request_id,
                   approved=approved,
                   approver=approver,
                   response_time_seconds=approval_time)
                   
        if approved:
            # Execute approved actions
            for action in approval.requested_actions:
                asyncio.create_task(
                    self._execute_action_async(
                        action,
                        approval.task_id,
                        request_id
                    )
                )
        else:
            # Send rejection notification
            await self.notifier.send_alert(
                title=f"Actions Rejected - {approval.task_id}",
                message=f"Security actions were rejected by {approver}.\nReason: {comments or 'Not provided'}",
                severity="warning"
            )
            
        # Remove from pending
        del self.pending_approvals[request_id]
