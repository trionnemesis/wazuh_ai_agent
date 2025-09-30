"""執行者代理：最終分析與回應執行的專家。"""
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
    執行者代理 - 行動專家
    
    職責：
    1. 最終威脅分析與綜合
    2. 產生人類可讀的報告
    3. 請求人類批准行動
    4. 執行已批准的安全回應
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
        
        # 執行狀態
        self.active_executions: Dict[str, ExecutionMessage] = {}
        self.pending_approvals: Dict[str, ApprovalRequest] = {}
        self.execution_reports: Dict[str, ExecutionReport] = {}
        
        # 效能追蹤
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
        """初始化執行者代理。"""
        await self.broker.connect()
        
        # 訂閱執行佇列
        await self.broker.subscribe(
            settings.execution_queue,
            self._handle_execution_request
        )
        
        logger.info("執行者代理已初始化", agent_id=self.agent_id)
        
    async def start(self) -> None:
        """啟動執行者代理的主迴圈。"""
        logger.info("執行者代理啟動中", agent_id=self.agent_id)
        
        # 啟動背景任務
        tasks = [
            asyncio.create_task(self._approval_monitor_loop()),
            asyncio.create_task(self._metrics_reporting_loop()),
            asyncio.create_task(self._cleanup_loop())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("執行者代理停止中")
            for task in tasks:
                task.cancel()
                
    async def stop(self) -> None:
        """停止執行者代理。"""
        await self.broker.disconnect()
        logger.info("執行者代理已停止", agent_id=self.agent_id)
        
    async def health_check(self) -> Dict[str, Any]:
        """返回代理健康狀態。"""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "status": "healthy",
            "active_executions": len(self.active_executions),
            "pending_approvals": len(self.pending_approvals),
            "metrics": dict(self.metrics)
        }
        
    async def analyze_threat(self, message: ExecutionMessage) -> ExecutionReport:
        """執行最終的全面威脅分析。"""
        start_time = datetime.utcnow()
        task = message.task
        profile = message.threat_profile
        
        logger.info("開始威脅分析",
                   task_id=task.task_id,
                   risk_score=profile.overall_risk_score,
                   category=profile.threat_category)
                   
        self.metrics["reports_generated"] += 1
        
        try:
            # 產生高階主管摘要
            executive_summary = await self._generate_executive_summary(profile)
            
            # 產生威脅敘述
            threat_narrative = await self._generate_threat_narrative(profile)
            
            # 產生技術分析
            technical_details = await self._generate_technical_analysis(profile)
            
            # 建立時間軸
            timeline = await self._create_incident_timeline(profile)
            
            # 產生建議
            recommendations = await self.generate_recommendations(profile)
            
            # 計算信賴度指標
            confidence_metrics = self._calculate_confidence_metrics(profile)
            
            # 編譯證據
            evidence = self._compile_evidence(profile)
            
            # 建立執行報告
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
            
            # 儲存報告
            self.execution_reports[task.task_id] = report
            
            # 更新指標
            analysis_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_avg_analysis_time(analysis_time)
            
            logger.info("威脅分析完成",
                       task_id=task.task_id,
                       num_recommendations=len(recommendations),
                       analysis_time_seconds=analysis_time)
                       
            return report
            
        except Exception as e:
            logger.error("威脅分析失敗",
                        task_id=task.task_id,
                        error=str(e))
            raise
            
    async def generate_recommendations(
        self,
        threat_profile: ThreatProfile
    ) -> List[RecommendedAction]:
        """使用進階 LLM 產生詳細的行動建議。"""
        prompt = f"""
        根據這份全面的威脅分析，產生具體的安全回應建議：
        
        威脅類別：{threat_profile.threat_category}
        風險分數：{threat_profile.overall_risk_score:.2f}
        威脅行為者：{threat_profile.threat_actor or '未知'}
        
        主要發現：
        - 攻擊路徑：識別出 {len(threat_profile.graph_context.attack_paths)} 條
        - 相似事件：找到 {len(threat_profile.vector_context.similar_alerts)} 起
        - 受影響資產：{list(threat_profile.asset_criticality.keys())}
        - 偵測到的模式：{', '.join(threat_profile.vector_context.detected_patterns)}
        
        資產重要性：
        {json.dumps(threat_profile.asset_criticality, indent=2)}
        
        產生 3-5 條具體、可行的建議，包含：
        1. 行動類型 (ISOLATE_HOST, BLOCK_IP, DISABLE_USER 等)
        2. 優先級 (1-5，1為最高)
        3. 具體參數
        4. 風險評估
        5. 預估影響
        
        考量組織的安全狀況並最小化業務中斷。
        以 JSON 列表格式返回。
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
                
            # 按優先級排序
            recommendations.sort(key=lambda x: x.priority)
            
            return recommendations
            
        except Exception as e:
            logger.error("產生建議失敗", error=str(e))
            
            # 根據威脅類別的後備建議
            return self._generate_fallback_recommendations(threat_profile)
            
    async def request_approval(self, report: ExecutionReport) -> bool:
        """請求人類批准建議的行動。"""
        task_id = report.task_id
        
        logger.info("請求批准中",
                   task_id=task_id,
                   num_actions=len(report.recommended_actions))
                   
        self.metrics["approvals_requested"] += 1
        
        # 過濾需要批准的行動
        actions_for_approval = [
            action for action in report.recommended_actions
            if action.requires_approval
        ]
        
        # 如果啟用，自動執行低風險行動
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
            return True  # 不需要批准
            
        # 建立批准請求
        approval_request = ApprovalRequest(
            task_id=task_id,
            execution_report=report,
            requested_actions=actions_for_approval,
            timeout_minutes=30,
            escalation_contacts=["security-manager@company.com"]
        )
        
        self.pending_approvals[approval_request.request_id] = approval_request
        
        # 發送通知
        approval_sent = await self._send_approval_notification(approval_request)
        
        if not approval_sent:
            logger.error("發送批准請求失敗", task_id=task_id)
            return False
            
        # 等待批准 (非同步 - 由回呼處理)
        return True
        
    async def execute_action(
        self,
        action: Dict[str, Any],
        approval_id: str
    ) -> Dict[str, Any]:
        """執行已批准的安全行動。"""
        start_time = datetime.utcnow()
        
        logger.info("執行行動中",
                   action_type=action["action_type"],
                   approval_id=approval_id)
                   
        self.metrics["actions_executed"] += 1
        
        try:
            # 驗證行動
            is_valid = await self.action_executor.validate_action(
                action["action_type"],
                action["parameters"]
            )
            
            if not is_valid:
                raise ValueError("行動驗證失敗")
                
            # 執行行動
            result = await self.action_executor.execute(
                action["action_type"],
                action["parameters"]
            )
            
            # 建立執行結果
            execution_result = ExecutionResult(
                action_id=action["action_id"],
                task_id=action.get("task_id", "unknown"),
                success=result.get("success", False),
                execution_time_seconds=(datetime.utcnow() - start_time).total_seconds(),
                output=result,
                executed_by=self.agent_id,
                approval_id=approval_id
            )
            
            logger.info("行動成功執行",
                       action_id=action["action_id"],
                       duration_seconds=execution_result.execution_time_seconds)
                       
            return execution_result.dict()
            
        except Exception as e:
            logger.error("行動執行失敗",
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
        """處理來自獵人代理的執行請求。"""
        try:
            execution_message = ExecutionMessage(**message)
            task_id = execution_message.task.task_id
            
            # 儲存活動中的執行
            self.active_executions[task_id] = execution_message
            
            # 執行威脅分析
            report = await self.analyze_threat(execution_message)
            
            # 發送初始通知
            await self._send_threat_notification(report)
            
            # 如果需要，請求批准
            if settings.enable_human_approval:
                await self.request_approval(report)
            else:
                # 自動執行所有建議 (危險!)
                logger.warning("人類批准已禁用 - 執行所有行動",
                             task_id=task_id)
                             
                for action in report.recommended_actions:
                    await self._execute_action_async(action, task_id, "auto-approved")
                    
            # 清理
            del self.active_executions[task_id]
            
        except Exception as e:
            logger.error("處理執行請求失敗", error=str(e))
            
    async def _generate_executive_summary(self, profile: ThreatProfile) -> str:
        """使用 LLM 產生高階主管摘要。"""
        prompt = f"""
        為此安全事件產生一份簡潔的高階主管摘要（3-4句話）：
        
        威脅類型：{profile.threat_category}
        風險等級：{profile.overall_risk_score:.2f} (0-1 等級)
        受影響資產：{len(profile.asset_criticality)} 個系統
        影響：{json.dumps(profile.impact_assessment)}
        
        摘要應適合 C 級主管和董事會成員閱讀。
        專注於業務影響和所需行動。
        """
        
        summary = await self.llm.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=200
        )
        
        return summary.strip()
        
    async def _generate_threat_narrative(self, profile: ThreatProfile) -> str:
        """產生詳細的威脅敘述。"""
        prompt = f"""
        建立一個詳細的威脅敘述，講述此安全事件的故事：
        
        初始警報：{profile.alert.title}
        時間：{profile.alert.timestamp}
        
        偵測到的攻擊模式：
        {json.dumps(profile.graph_context.attack_paths[:3], indent=2)}
        
        相似的歷史事件：{len(profile.vector_context.similar_alerts)}
        
        威脅行為者：{profile.threat_actor or '未知'}
        活動：{profile.campaign_id or '未與已知活動關聯'}
        
        撰寫一份敘述，解釋：
        1. 攻擊可能如何開始
        2. 攻擊者做了什麼
        3. 他們的目標可能是什麼
        4. 當前狀態和風險
        
        盡可能使用清晰、非技術性的語言。
        """
        
        narrative = await self.llm.generate(
            prompt=prompt,
            temperature=0.4,
            max_tokens=800
        )
        
        return narrative.strip()
        
    async def _generate_technical_analysis(self, profile: ThreatProfile) -> Dict[str, Any]:
        """產生詳細的技術分析。"""
        return {
            "attack_vectors": self._analyze_attack_vectors(profile),
            "vulnerability_analysis": self._analyze_vulnerabilities(profile),
            "network_analysis": self._analyze_network_activity(profile),
            "behavioral_analysis": self._analyze_behavior_patterns(profile),
            "threat_intelligence": self._compile_threat_intel(profile),
            "forensic_artifacts": self._identify_forensic_artifacts(profile)
        }
        
    async def _create_incident_timeline(self, profile: ThreatProfile) -> List[Dict[str, Any]]:
        """建立詳細的事件時間軸。"""
        timeline = []
        
        # 初始偵測
        timeline.append({
            "timestamp": profile.alert.timestamp.isoformat(),
            "event": "初始警報",
            "description": profile.alert.title,
            "severity": profile.alert.severity,
            "source": profile.alert.source
        })
        
        # 從圖形分析中新增事件
        for path in profile.graph_context.attack_paths[:5]:  # 限制為 5 條路徑
            for i, node in enumerate(path):
                if isinstance(node, dict) and "timestamp" in node:
                    timeline.append({
                        "timestamp": node["timestamp"],
                        "event": f"攻擊步驟 {i+1}",
                        "description": node.get("description", "未知行動"),
                        "entity": node.get("entity"),
                        "confidence": node.get("confidence", 0.5)
                    })
                    
        # 新增相似事件
        for alert in profile.vector_context.similar_alerts[:3]:
            timeline.append({
                "timestamp": alert.get("timestamp", profile.alert.timestamp).isoformat(),
                "event": "相似警報",
                "description": alert.get("title", "相關事件"),
                "correlation": alert.get("score", 0)
            })
            
        # 按時間戳排序
        timeline.sort(key=lambda x: x["timestamp"])
        
        return timeline
        
    def _calculate_confidence_metrics(self, profile: ThreatProfile) -> Dict[str, float]:
        """計算分析的信賴度指標。"""
        factors = {
            "graph_evidence": min(len(profile.graph_context.attack_paths) / 5, 1.0) * 0.3,
            "vector_similarity": (1 - profile.vector_context.anomaly_score) * 0.2,
            "threat_intel": (1.0 if profile.threat_actor else 0.5) * 0.2,
            "pattern_match": min(len(profile.vector_context.detected_patterns) / 3, 1.0) * 0.3
        }
        
        confidence = sum(factors.values())
        
        # 計算誤報機率
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
        """編譯支持證據。"""
        evidence = []
        
        # 圖形證據
        for i, path in enumerate(profile.graph_context.attack_paths[:3]):
            evidence.append({
                "type": "attack_path",
                "id": f"path_{i+1}",
                "description": f"包含 {len(path)} 個步驟的攻擊路徑",
                "confidence": 0.8,
                "details": path
            })
            
        # 向量證據
        for i, alert in enumerate(profile.vector_context.similar_alerts[:3]):
            evidence.append({
                "type": "similar_incident",
                "id": f"incident_{i+1}",
                "description": alert.get("title", "相似警報"),
                "similarity": alert.get("score", 0),
                "timestamp": alert.get("timestamp")
            })
            
        # IOC 證據
        for ioc in profile.graph_context.iocs[:5]:
            evidence.append({
                "type": "ioc",
                "id": f"ioc_{ioc.get('value', 'unknown')[:8]}",
                "description": f"{ioc.get('type', 'unknown')} 指標",
                "value": ioc.get("value"),
                "confidence": ioc.get("confidence", 0.5)
            })
            
        return evidence
        
    def _extract_iocs(self, profile: ThreatProfile) -> List[Dict[str, Any]]:
        """提取並格式化 IOC。"""
        iocs = []
        
        # 從警報中提取
        for ip in profile.alert.source_ips:
            iocs.append({"type": "ip", "value": ip, "direction": "source"})
        for ip in profile.alert.destination_ips:
            iocs.append({"type": "ip", "value": ip, "direction": "destination"})
        for hash_val in profile.alert.file_hashes:
            iocs.append({"type": "file_hash", "value": hash_val})
            
        # 從圖形上下文中提取
        iocs.extend(profile.graph_context.iocs)
        
        # 去重
        seen = set()
        unique_iocs = []
        for ioc in iocs:
            key = f"{ioc['type']}:{ioc['value']}"
            if key not in seen:
                seen.add(key)
                unique_iocs.append(ioc)
                
        return unique_iocs
        
    def _generate_references(self, profile: ThreatProfile) -> List[str]:
        """產生參考資料和連結。"""
        references = []
        
        # MITRE ATT&CK 參考資料
        for ttp in profile.graph_context.ttps:
            references.append(f"https://attack.mitre.org/techniques/{ttp}/")
            
        # 威脅行為者參考資料
        if profile.threat_actor:
            references.append(f"內部知識庫：/threats/actors/{profile.threat_actor}")
            
        # 活動參考資料
        if profile.campaign_id:
            references.append(f"內部知識庫：/threats/campaigns/{profile.campaign_id}")
            
        return references
        
    def _generate_fallback_recommendations(
        self,
        profile: ThreatProfile
    ) -> List[RecommendedAction]:
        """當 LLM 失敗時產生基本的後備建議。"""
        recommendations = []
        
        # 高風險預設行動
        if profile.overall_risk_score > 0.7:
            recommendations.append(
                RecommendedAction(
                    action_type=ActionType.ISOLATE_HOST,
                    priority=1,
                    description="隔離受影響的系統以防止橫向移動",
                    parameters={
                        "hosts": list(profile.asset_criticality.keys())
                    },
                    risk_level="low",
                    potential_impact="隔離主機的系統不可用",
                    requires_approval=True
                )
            )
            
        # 封鎖惡意 IP
        malicious_ips = [
            ioc["value"] for ioc in profile.graph_context.iocs
            if ioc.get("type") == "ip" and ioc.get("confidence", 0) > 0.7
        ]
        
        if malicious_ips:
            recommendations.append(
                RecommendedAction(
                    action_type=ActionType.BLOCK_IP,
                    priority=2,
                    description="封鎖已確認的惡意 IP 位址",
                    parameters={"ips": malicious_ips},
                    risk_level="low",
                    potential_impact="極小 - 封鎖外部 IP",
                    requires_approval=True
                )
            )
            
        # 總是建立工單
        recommendations.append(
            RecommendedAction(
                action_type=ActionType.CREATE_TICKET,
                priority=3,
                description="建立事件工單以供追蹤和調查",
                parameters={
                    "severity": "high" if profile.overall_risk_score > 0.7 else "medium",
                    "title": f"安全事件：{profile.threat_category}",
                    "assignee": "soc-team"
                },
                risk_level="low",
                potential_impact="無 - 管理性行動",
                requires_approval=False
            )
        )
        
        return recommendations
        
    def _analyze_attack_vectors(self, profile: ThreatProfile) -> List[Dict[str, Any]]:
        """從設定檔分析攻擊向量。"""
        vectors = []
        
        # 分析每個攻擊路徑
        for path in profile.graph_context.attack_paths[:5]:
            vector = {
                "type": "network_path",
                "steps": len(path),
                "entry_point": path[0] if path else None,
                "target": path[-1] if path else None,
                "techniques": []
            }
            
            # 從路徑中提取技術
            for node in path:
                if isinstance(node, dict) and "technique" in node:
                    vector["techniques"].append(node["technique"])
                    
            vectors.append(vector)
            
        return vectors
        
    def _analyze_vulnerabilities(self, profile: ThreatProfile) -> Dict[str, Any]:
        """分析可能被利用的漏洞。"""
        vuln_analysis = {
            "exploited": [],
            "at_risk": [],
            "patches_available": []
        }
        
        # 檢查資產漏洞
        for asset, vulns in profile.asset_vulnerabilities.items():
            for vuln in vulns:
                vuln_info = {
                    "cve": vuln,
                    "asset": asset,
                    "severity": "high"  # 在真實系統中會查詢
                }
                
                # 簡單的啟發式方法 - 如果資產在攻擊路徑中，漏洞可能被利用
                if any(asset in str(path) for path in profile.graph_context.attack_paths):
                    vuln_analysis["exploited"].append(vuln_info)
                else:
                    vuln_analysis["at_risk"].append(vuln_info)
                    
        return vuln_analysis
        
    def _analyze_network_activity(self, profile: ThreatProfile) -> Dict[str, Any]:
        """分析網路活動模式。"""
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
        """分析行為模式。"""
        return {
            "patterns_detected": profile.vector_context.detected_patterns,
            "anomaly_score": profile.vector_context.anomaly_score,
            "historical_occurrence": profile.vector_context.occurrence_count,
            "time_based_pattern": "PERIODIC_ACTIVITY" in profile.vector_context.detected_patterns
        }
        
    def _compile_threat_intel(self, profile: ThreatProfile) -> Dict[str, Any]:
        """編譯威脅情報資訊。"""
        return {
            "threat_actor": profile.threat_actor,
            "campaign": profile.campaign_id,
            "ttps": profile.graph_context.ttps,
            "related_campaigns": profile.graph_context.related_campaigns,
            "confidence": 0.8 if profile.threat_actor else 0.3
        }
        
    def _identify_forensic_artifacts(self, profile: ThreatProfile) -> List[Dict[str, Any]]:
        """識別用於調查的關鍵鑑識產物。"""
        artifacts = []
        
        # 檔案產物
        for hash_val in profile.alert.file_hashes:
            artifacts.append({
                "type": "file",
                "value": hash_val,
                "description": "可疑檔案雜湊",
                "collection_method": "endpoint_agent"
            })
            
        # 網路產物
        for ip in profile.alert.source_ips:
            artifacts.append({
                "type": "network",
                "value": f"pcap_filter: host {ip}",
                "description": "網路流量捕獲過濾器",
                "collection_method": "network_tap"
            })
            
        # 記憶體產物
        if profile.threat_category in ["MALWARE", "INTRUSION"]:
            artifacts.append({
                "type": "memory",
                "value": "full_memory_dump",
                "description": "用於惡意軟體分析的記憶體傾印",
                "collection_method": "endpoint_agent"
            })
            
        return artifacts
        
    async def _send_threat_notification(self, report: ExecutionReport) -> bool:
        """發送初始威脅通知。"""
        try:
            # 格式化通知
            severity = "critical" if report.analysis_confidence > 0.8 else "high"
            
            message = f"""
🚨 **偵測到安全威脅**

**摘要：** {report.executive_summary}

**風險等級：** {report.analysis_confidence:.0%}
**誤報機率：** {report.false_positive_probability:.0%}

**建議行動：** {len(report.recommended_actions)}

查看完整報告：[報告 #{report.report_id}]
            """
            
            # 發送通知
            success = await self.notifier.send_alert(
                title=f"安全警報 - 任務 {report.task_id}",
                message=message.strip(),
                severity=severity,
                attachments=[{
                    "title": "技術細節",
                    "text": json.dumps(report.technical_details, indent=2)[:500] + "..."
                }]
            )
            
            return success
            
        except Exception as e:
            logger.error("發送威脅通知失敗", error=str(e))
            return False
            
    async def _send_approval_notification(self, approval: ApprovalRequest) -> bool:
        """發送批准請求通知。"""
        try:
            # 格式化批准請求
            actions_summary = "\n".join([
                f"{i+1}. {action.description} (優先級：{action.priority})"
                for i, action in enumerate(approval.requested_actions)
            ])
            
            message = f"""
⚠️ **需要行動批准**

**任務 ID：** {approval.task_id}
**報告：** {approval.execution_report.executive_summary}

**請求的行動：**
{actions_summary}

**逾時：** {approval.timeout_minutes} 分鐘

請審查並批准/拒絕這些行動。
            """
            
            # 建立回呼 URL
            callback_url = f"https://api.security.company/approvals/{approval.request_id}"
            
            # 發送批准請求
            request_id = await self.notifier.request_approval(
                title=f"需要批准 - {approval.task_id}",
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
            logger.error("發送批准通知失敗", error=str(e))
            return False
            
    async def _execute_action_async(
        self,
        action: RecommendedAction,
        task_id: str,
        approval_id: str
    ) -> None:
        """非同步執行行動。"""
        try:
            action_dict = action.dict()
            action_dict["task_id"] = task_id
            
            result = await self.execute_action(action_dict, approval_id)
            
            # 發送完成通知
            if result.get("success"):
                await self.notifier.send_alert(
                    title=f"行動完成 - {action.action_type}",
                    message=f"成功執行：{action.description}",
                    severity="info"
                )
            else:
                await self.notifier.send_alert(
                    title=f"行動失敗 - {action.action_type}",
                    message=f"執行失敗：{action.description}\n錯誤：{result.get('error')}",
                    severity="error"
                )
                
        except Exception as e:
            logger.error("非同步行動執行失敗",
                        action_type=action.action_type,
                        error=str(e))
                        
    def _update_avg_analysis_time(self, analysis_time: float) -> None:
        """更新平均分析時間指標。"""
        current_avg = self.metrics["avg_analysis_time"]
        report_count = self.metrics["reports_generated"]
        
        self.metrics["avg_analysis_time"] = (
            (current_avg * (report_count - 1) + analysis_time) / report_count
        )
        
    def _update_avg_approval_time(self, approval_time: float) -> None:
        """更新平均批准時間指標。"""
        current_avg = self.metrics["avg_approval_time"]
        approval_count = self.metrics["approvals_received"]
        
        if approval_count > 0:
            self.metrics["avg_approval_time"] = (
                (current_avg * (approval_count - 1) + approval_time) / approval_count
            )
            
    async def _approval_monitor_loop(self) -> None:
        """監控批准請求並處理逾時。"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分鐘檢查一次
                
                current_time = datetime.utcnow()
                
                for request_id, approval in list(self.pending_approvals.items()):
                    # 檢查逾時
                    elapsed = (current_time - approval.requested_at).total_seconds() / 60
                    
                    if elapsed > approval.timeout_minutes:
                        logger.warning("批准逾時",
                                     request_id=request_id,
                                     elapsed_minutes=elapsed)
                                     
                        # 上報
                        await self.notifier.send_alert(
                            title=f"緊急：批准逾時 - {approval.task_id}",
                            message=f"批准請求已逾時。上報至：{', '.join(approval.escalation_contacts)}",
                            severity="critical"
                        )
                        
                        # 從待處理中移除
                        del self.pending_approvals[request_id]
                        
            except Exception as e:
                logger.error("批准監控失敗", error=str(e))
                
    async def _metrics_reporting_loop(self) -> None:
        """定期回報指標。"""
        while True:
            try:
                await asyncio.sleep(300)  # 每 5 分鐘回報一次
                
                logger.info("執行者代理指標",
                          metrics=dict(self.metrics),
                          active_executions=len(self.active_executions),
                          pending_approvals=len(self.pending_approvals))
                          
            except Exception as e:
                logger.error("指標回報失敗", error=str(e))
                
    async def _cleanup_loop(self) -> None:
        """清理舊的執行報告。"""
        while True:
            try:
                await asyncio.sleep(3600)  # 每小時執行一次
                
                cutoff_time = datetime.utcnow() - timedelta(days=7)
                
                # 清理舊報告
                old_reports = [
                    task_id for task_id, report in self.execution_reports.items()
                    if report.generated_at < cutoff_time
                ]
                
                for task_id in old_reports:
                    del self.execution_reports[task_id]
                    
                logger.debug("清理完成",
                           removed_reports=len(old_reports))
                           
            except Exception as e:
                logger.error("清理失敗", error=str(e))
                
    async def handle_approval_response(
        self,
        request_id: str,
        approved: bool,
        approver: str,
        comments: Optional[str] = None
    ) -> None:
        """處理來自人類的批准回應。"""
        if request_id not in self.pending_approvals:
            logger.warning("未知的批准請求", request_id=request_id)
            return
            
        approval = self.pending_approvals[request_id]
        approval.approved = approved
        approval.approver = approver
        approval.approval_timestamp = datetime.utcnow()
        approval.approval_comments = comments
        
        # 更新指標
        self.metrics["approvals_received"] += 1
        approval_time = (approval.approval_timestamp - approval.requested_at).total_seconds()
        self._update_avg_approval_time(approval_time)
        
        logger.info("收到批准",
                   request_id=request_id,
                   approved=approved,
                   approver=approver,
                   response_time_seconds=approval_time)
                   
        if approved:
            # 執行已批准的行動
            for action in approval.requested_actions:
                asyncio.create_task(
                    self._execute_action_async(
                        action,
                        approval.task_id,
                        request_id
                    )
                )
        else:
            # 發送拒絕通知
            await self.notifier.send_alert(
                title=f"行動已拒絕 - {approval.task_id}",
                message=f"安全行動被 {approver} 拒絕。\n原因：{comments or '未提供'}",
                severity="warning"
            )
            
        # 從待處理中移除
        del self.pending_approvals[request_id]