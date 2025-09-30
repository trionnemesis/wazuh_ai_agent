"""獵人代理：深度調查與威脅狩獵專家。"""
import asyncio
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime, timedelta
import json
import structlog
from collections import defaultdict
import networkx as nx

from ..core.interfaces import (
    IHunterAgent, IMessageBroker, IGraphDatabase,
    IVectorDatabase, ILLMProvider
)
from ..core.models import (
    Task, TaskStatus, AlertMessage, HuntingMessage,
    ExecutionMessage, ThreatProfile, GraphContext,
    VectorContext, ThreatCategory
)
from ..core.config import settings

logger = structlog.get_logger()


class HunterAgent(IHunterAgent):
    """
    獵人代理 - 調查專家
    
    職責：
    1. 深度威脅調查
    2. 實體關係的 GraphRAG 分析
    3. 模式的向量相似性搜索
    4. 上下文豐富與關聯
    """
    
    def __init__(
        self,
        message_broker: IMessageBroker,
        graph_db: IGraphDatabase,
        vector_db: IVectorDatabase,
        llm_provider: ILLMProvider
    ):
        self._agent_id = f"hunter-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        self._agent_type = "hunter"
        self.broker = message_broker
        self.graph_db = graph_db
        self.vector_db = vector_db
        self.llm = llm_provider
        
        # 處理狀態
        self.active_hunts: Dict[str, HuntingMessage] = {}
        self.hunt_results: Dict[str, ThreatProfile] = {}
        
        # 效能追蹤
        self.metrics = {
            "hunts_started": 0,
            "hunts_completed": 0,
            "graph_queries": 0,
            "vector_searches": 0,
            "enrichments": 0,
            "avg_hunt_time": 0.0
        }
        
    @property
    def agent_id(self) -> str:
        return self._agent_id
        
    @property
    def agent_type(self) -> str:
        return self._agent_type
        
    async def initialize(self) -> None:
        """初始化獵人代理。"""
        await asyncio.gather(
            self.broker.connect(),
            self.graph_db.connect(),
            self.vector_db.connect()
        )
        
        # 訂閱狩獵佇列
        await self.broker.subscribe(
            settings.hunting_queue,
            self._handle_hunting_request
        )
        
        logger.info("獵人代理已初始化", agent_id=self.agent_id)
        
    async def start(self) -> None:
        """啟動獵人代理的主迴圈。"""
        logger.info("獵人代理啟動中", agent_id=self.agent_id)
        
        # 啟動背景任務
        tasks = [
            asyncio.create_task(self._process_hunts_loop()),
            asyncio.create_task(self._metrics_reporting_loop()),
            asyncio.create_task(self._cleanup_loop())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("獵人代理停止中")
            for task in tasks:
                task.cancel()
                
    async def stop(self) -> None:
        """停止獵人代理。"""
        await asyncio.gather(
            self.broker.disconnect(),
            self.graph_db.disconnect(),
            self.vector_db.disconnect()
        )
        logger.info("獵人代理已停止", agent_id=self.agent_id)
        
    async def health_check(self) -> Dict[str, Any]:
        """返回代理健康狀態。"""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "status": "healthy",
            "active_hunts": len(self.active_hunts),
            "metrics": dict(self.metrics)
        }
        
    async def hunt_threat(self, message: HuntingMessage) -> ThreatProfile:
        """執行全面的威脅狩獵。"""
        start_time = datetime.utcnow()
        task = message.task
        alert = message.alert
        
        logger.info("開始威脅狩獵",
                   task_id=task.task_id,
                   alert_id=alert.alert_id,
                   priority=message.priority)
                   
        self.metrics["hunts_started"] += 1
        
        try:
            # 並行執行調查任務
            graph_task = asyncio.create_task(
                self.query_graph({
                    "alert": alert,
                    "max_depth": message.max_depth,
                    "time_window": message.time_window_hours
                })
            )
            
            vector_task = asyncio.create_task(
                self.search_vectors({
                    "alert": alert,
                    "time_window": message.time_window_hours,
                    "top_k": 20
                })
            )
            
            enrichment_task = asyncio.create_task(
                self.enrich_context(alert)
            )
            
            # 等待所有任務完成
            graph_context_data, vector_context_data, enrichment_data = await asyncio.gather(
                graph_task, vector_task, enrichment_task
            )
            
            # 建立全面的威脅設定檔
            threat_profile = await self._build_threat_profile(
                task, alert, graph_context_data, vector_context_data, enrichment_data
            )
            
            # 儲存結果
            self.hunt_results[task.task_id] = threat_profile
            
            # 計算指標
            hunt_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_avg_hunt_time(hunt_time)
            self.metrics["hunts_completed"] += 1
            
            logger.info("威脅狩獵完成",
                       task_id=task.task_id,
                       risk_score=threat_profile.overall_risk_score,
                       hunt_time_seconds=hunt_time)
                       
            return threat_profile
            
        except Exception as e:
            logger.error("威脅狩獵失敗",
                        task_id=task.task_id,
                        error=str(e))
            raise
            
    async def query_graph(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """查詢 GraphRAG 以獲取實體關係和攻擊路徑。"""
        self.metrics["graph_queries"] += 1
        alert = context["alert"]
        max_depth = context.get("max_depth", 3)
        
        try:
            # 從警報中提取實體
            entities = await self._extract_entities(alert)
            
            # 在圖形中建立或更新節點
            node_ids = await self._create_graph_nodes(entities, alert)
            
            # 尋找攻擊路徑和關係
            attack_paths = []
            relationships = []
            
            for node_id in node_ids:
                # 從此節點尋找路徑
                paths = await self.graph_db.find_paths(
                    start_node=node_id,
                    max_depth=max_depth
                )
                attack_paths.extend(paths)
                
            # 查詢特定模式
            patterns = await self._query_attack_patterns(entities, alert)
            
            # 計算基於圖形的風險分數
            risk_score = await self._calculate_graph_risk(attack_paths, relationships)
            
            # 尋找相關活動
            campaigns = await self._find_related_campaigns(entities)
            
            return {
                "entities": entities,
                "relationships": relationships,
                "attack_paths": attack_paths,
                "risk_score": risk_score,
                "patterns": patterns,
                "campaigns": campaigns
            }
            
        except Exception as e:
            logger.error("圖形查詢失敗", error=str(e))
            return {
                "entities": [],
                "relationships": [],
                "attack_paths": [],
                "risk_score": 0.0
            }
            
    async def search_vectors(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """在向量資料庫中搜索相似的警報和模式。"""
        self.metrics["vector_searches"] += 1
        alert = context["alert"]
        time_window = context.get("time_window", 24)
        top_k = context.get("top_k", 10)
        
        try:
            # 為警報產生嵌入
            alert_text = f"{alert.title} {alert.description}"
            alert_embedding = await self.llm.embed(alert_text)
            
            # 搜索相似的警報
            similar_alerts = await self.vector_db.search(
                vector=alert_embedding,
                top_k=top_k,
                filters={
                    "timestamp": {
                        "$gte": (datetime.utcnow() - timedelta(hours=time_window)).isoformat()
                    }
                }
            )
            
            # 分析相似警報中的模式
            patterns = await self._analyze_alert_patterns(similar_alerts)
            
            # 計算異常分數
            anomaly_score = await self._calculate_anomaly_score(
                alert_embedding, similar_alerts
            )
            
            # 獲取解決歷史記錄
            resolution_history = await self._get_resolution_history(similar_alerts)
            
            return {
                "similar_alerts": similar_alerts,
                "similarity_scores": [a.get("score", 0) for a in similar_alerts],
                "detected_patterns": patterns,
                "anomaly_score": anomaly_score,
                "occurrence_count": len(similar_alerts),
                "last_seen": max([a.get("timestamp") for a in similar_alerts]) if similar_alerts else None,
                "resolution_history": resolution_history
            }
            
        except Exception as e:
            logger.error("向量搜索失敗", error=str(e))
            return {
                "similar_alerts": [],
                "similarity_scores": [],
                "detected_patterns": [],
                "anomaly_score": 0.0,
                "occurrence_count": 0
            }
            
    async def enrich_context(self, alert: AlertMessage) -> Dict[str, Any]:
        """從各種來源豐富警報的上下文。"""
        self.metrics["enrichments"] += 1
        
        try:
            # 並行豐富任務
            tasks = {
                "asset_info": self._enrich_asset_information(alert.affected_assets),
                "user_info": self._enrich_user_information(alert.user_accounts),
                "ip_reputation": self._check_ip_reputation(alert.source_ips),
                "file_analysis": self._analyze_file_hashes(alert.file_hashes),
                "threat_intel": self._query_threat_intelligence(alert)
            }
            
            results = {}
            for name, task in tasks.items():
                try:
                    results[name] = await task
                except Exception as e:
                    logger.error(f"豐富失敗：{name}", error=str(e))
                    results[name] = {}
                    
            return results
            
        except Exception as e:
            logger.error("上下文豐富失敗", error=str(e))
            return {}
            
    async def _handle_hunting_request(self, message: Dict[str, Any]) -> None:
        """處理來自管理代理的狩獵請求。"""
        try:
            hunting_message = HuntingMessage(**message)
            task_id = hunting_message.task.task_id
            
            # 儲存活動中的狩獵
            self.active_hunts[task_id] = hunting_message
            
            # 執行威脅狩獵
            threat_profile = await self.hunt_threat(hunting_message)
            
            # 建立執行訊息
            execution_message = ExecutionMessage(
                task=hunting_message.task,
                threat_profile=threat_profile,
                auto_execute_low_risk=settings.auto_execute_low_risk,
                analysis_depth="comprehensive" if hunting_message.priority == "critical" else "standard"
            )
            
            # 發布到執行者代理
            await self.broker.publish(
                settings.execution_queue,
                execution_message.dict()
            )
            
            # 清理
            del self.active_hunts[task_id]
            
        except Exception as e:
            logger.error("處理狩獵請求失敗", error=str(e))
            
    async def _extract_entities(self, alert: AlertMessage) -> List[Dict[str, Any]]:
        """使用 NLP 從警報中提取實體。"""
        prompt = f"""
        從此警報中提取與安全相關的實體：
        
        標題：{alert.title}
        描述：{alert.description}
        
        提取：
        1. IP 位址 (附帶類型：來源/目的地/C2)
        2. 主機名/域名
        3. 使用者帳戶
        4. 檔案路徑與雜湊值
        5. 行程名稱
        6. 登錄機碼
        7. 網路連接埠
        
        以包含類型和值的 JSON 實體列表格式返回。
        """
        
        response = await self.llm.generate(prompt, temperature=0.0, max_tokens=500)
        entities = json.loads(response)
        
        # 從結構化資料中新增實體
        for ip in alert.source_ips:
            entities.append({"type": "ip_address", "value": ip, "role": "source"})
        for ip in alert.destination_ips:
            entities.append({"type": "ip_address", "value": ip, "role": "destination"})
        for user in alert.user_accounts:
            entities.append({"type": "user_account", "value": user})
        for hash_val in alert.file_hashes:
            entities.append({"type": "file_hash", "value": hash_val})
            
        return entities
        
    async def _create_graph_nodes(
        self,
        entities: List[Dict[str, Any]],
        alert: AlertMessage
    ) -> List[str]:
        """在圖形資料庫中建立或更新節點。"""
        node_ids = []
        
        for entity in entities:
            # 建立節點
            node_id = await self.graph_db.create_node(
                node_type=entity["type"],
                properties={
                    "value": entity["value"],
                    "first_seen": alert.timestamp.isoformat(),
                    "last_seen": alert.timestamp.isoformat(),
                    "alert_count": 1,
                    **entity.get("metadata", {})
                }
            )
            node_ids.append(node_id)
            
        # 建立警報節點
        alert_node_id = await self.graph_db.create_node(
            node_type="alert",
            properties={
                "alert_id": alert.alert_id,
                "severity": alert.severity,
                "timestamp": alert.timestamp.isoformat(),
                "source": alert.source
            }
        )
        
        # 建立關係
        for node_id in node_ids:
            await self.graph_db.create_relationship(
                source_id=alert_node_id,
                target_id=node_id,
                relationship_type="INVOLVES"
            )
            
        return node_ids
        
    async def _query_attack_patterns(
        self,
        entities: List[Dict[str, Any]],
        alert: AlertMessage
    ) -> List[str]:
        """在圖形中查詢已知的攻擊模式。"""
        patterns = []
        
        # MITRE ATT&CK 模式匹配
        cypher_queries = [
            # 橫向移動模式
            """
            MATCH (a:ip_address)-[:CONNECTS_TO]->(b:host)-[:HAS_USER]->(u:user_account)
            WHERE a.value IN $source_ips
            RETURN 'LATERAL_MOVEMENT' as pattern
            """,
            
            # C2 通訊模式
            """
            MATCH (h:host)-[:CONNECTS_TO]->(ip:ip_address)
            WHERE ip.reputation = 'malicious' AND h.value IN $hosts
            RETURN 'C2_COMMUNICATION' as pattern
            """,
            
            # 資料外洩模式
            """
            MATCH (u:user_account)-[:ACCESSED]->(f:file)-[:SENT_TO]->(ip:ip_address)
            WHERE u.value IN $users AND ip.external = true
            RETURN 'DATA_EXFILTRATION' as pattern
            """
        ]
        
        for query in cypher_queries:
            results = await self.graph_db.query(
                query,
                parameters={
                    "source_ips": alert.source_ips,
                    "hosts": alert.affected_assets,
                    "users": alert.user_accounts
                }
            )
            patterns.extend([r["pattern"] for r in results])
            
        return list(set(patterns))
        
    async def _calculate_graph_risk(
        self,
        attack_paths: List[List[Dict[str, Any]]],
        relationships: List[Dict[str, Any]]
    ) -> float:
        """根據圖形分析計算風險分數。"""
        risk_score = 0.0
        
        # 因素 1：攻擊路徑數量
        path_score = min(len(attack_paths) * 10, 30)
        
        # 因素 2：路徑重要性（最短路徑更危險）
        if attack_paths:
            avg_path_length = sum(len(p) for p in attack_paths) / len(attack_paths)
            criticality_score = max(0, 30 - (avg_path_length * 5))
        else:
            criticality_score = 0
            
        # 因素 3：實體信譽
        reputation_score = 0
        for path in attack_paths:
            for node in path:
                if node.get("reputation") == "malicious":
                    reputation_score += 10
                elif node.get("reputation") == "suspicious":
                    reputation_score += 5
                    
        reputation_score = min(reputation_score, 40)
        
        risk_score = path_score + criticality_score + reputation_score
        return min(risk_score / 100, 1.0)  # 正規化至 0-1
        
    async def _find_related_campaigns(
        self,
        entities: List[Dict[str, Any]]
    ) -> List[str]:
        """尋找相關的威脅活動。"""
        campaigns = []
        
        # 查詢涉及這些實體的活動
        for entity in entities:
            query = """
            MATCH (e:{type})-[:PART_OF]->(c:campaign)
            WHERE e.value = $value
            RETURN DISTINCT c.campaign_id as campaign_id, c.name as name
            """.format(type=entity["type"])
            
            results = await self.graph_db.query(
                query,
                parameters={"value": entity["value"]}
            )
            
            campaigns.extend([r["campaign_id"] for r in results])
            
        return list(set(campaigns))
        
    async def _analyze_alert_patterns(
        self,
        similar_alerts: List[Dict[str, Any]]
    ) -> List[str]:
        """分析相似警報中的模式。"""
        if not similar_alerts:
            return []
            
        patterns = []
        
        # 基於時間的模式
        timestamps = [a["timestamp"] for a in similar_alerts]
        if self._detect_time_pattern(timestamps):
            patterns.append("PERIODIC_ACTIVITY")
            
        # 來源模式
        sources = [a.get("source_ip") for a in similar_alerts if a.get("source_ip")]
        if len(set(sources)) == 1:
            patterns.append("SINGLE_SOURCE")
        elif len(set(sources)) < len(sources) * 0.2:
            patterns.append("CONCENTRATED_SOURCE")
            
        # 目標模式
        targets = [a.get("target") for a in similar_alerts if a.get("target")]
        if len(set(targets)) == 1:
            patterns.append("TARGETED_ATTACK")
            
        # 嚴重性升級
        severities = [a.get("severity", 0) for a in similar_alerts]
        if severities == sorted(severities):
            patterns.append("ESCALATING_SEVERITY")
            
        return patterns
        
    def _detect_time_pattern(self, timestamps: List[datetime]) -> bool:
        """偵測時間戳是否遵循模式。"""
        if len(timestamps) < 3:
            return False
            
        # 計算時間差
        sorted_times = sorted(timestamps)
        diffs = []
        for i in range(1, len(sorted_times)):
            diff = (sorted_times[i] - sorted_times[i-1]).total_seconds()
            diffs.append(diff)
            
        # 檢查規律性（標準差 < 平均值的 20%）
        if diffs:
            mean_diff = sum(diffs) / len(diffs)
            if mean_diff > 0:
                variance = sum((d - mean_diff) ** 2 for d in diffs) / len(diffs)
                std_dev = variance ** 0.5
                return std_dev / mean_diff < 0.2
                
        return False
        
    async def _calculate_anomaly_score(
        self,
        alert_embedding: List[float],
        similar_alerts: List[Dict[str, Any]]
    ) -> float:
        """根據向量相似性計算異常分數。"""
        if not similar_alerts:
            return 1.0  # 如果沒有相似警報，則為高度異常
            
        # 前幾個匹配項的平均相似性
        similarities = [a.get("score", 0) for a in similar_alerts[:5]]
        avg_similarity = sum(similarities) / len(similarities)
        
        # 異常分數是相似性的倒數
        return 1.0 - avg_similarity
        
    async def _get_resolution_history(
        self,
        similar_alerts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """獲取相似警報的解決歷史記錄。"""
        history = []
        
        for alert in similar_alerts[:10]:  # 限制為最近的警報
            if alert.get("resolution"):
                history.append({
                    "alert_id": alert.get("alert_id"),
                    "timestamp": alert.get("timestamp"),
                    "resolution": alert.get("resolution"),
                    "resolution_time": alert.get("resolution_time"),
                    "actions_taken": alert.get("actions_taken", [])
                })
                
        return history
        
    async def _enrich_asset_information(
        self,
        assets: List[str]
    ) -> Dict[str, Any]:
        """從 CMDB 或資產清單中豐富資產資訊。"""
        asset_info = {}
        
        for asset in assets:
            # 模擬 CMDB 查詢
            asset_info[asset] = {
                "criticality": "high" if "server" in asset.lower() else "medium",
                "owner": "IT Operations",
                "location": "Datacenter-1",
                "os": "Windows Server 2019",
                "last_patch": "2024-01-15",
                "vulnerabilities": ["CVE-2024-1234", "CVE-2024-5678"]
            }
            
        return asset_info
        
    async def _enrich_user_information(
        self,
        users: List[str]
    ) -> Dict[str, Any]:
        """從目錄服務中豐富使用者資訊。"""
        user_info = {}
        
        for user in users:
            # 模擬 AD 查詢
            user_info[user] = {
                "department": "Finance",
                "role": "Administrator",
                "privileged": True,
                "last_login": "2024-01-20T10:30:00Z",
                "risk_score": 0.7
            }
            
        return user_info
        
    async def _check_ip_reputation(
        self,
        ips: List[str]
    ) -> Dict[str, Any]:
        """從威脅情報中檢查 IP 信譽。"""
        ip_reputation = {}
        
        for ip in ips:
            # 模擬威脅情報查詢
            ip_reputation[ip] = {
                "reputation": "suspicious",
                "country": "CN",
                "asn": "AS12345",
                "threat_categories": ["botnet", "scanner"],
                "last_seen": "2024-01-20T15:00:00Z"
            }
            
        return ip_reputation
        
    async def _analyze_file_hashes(
        self,
        hashes: List[str]
    ) -> Dict[str, Any]:
        """根據威脅情報分析檔案雜湊值。"""
        file_analysis = {}
        
        for hash_val in hashes:
            # 模擬檔案分析
            file_analysis[hash_val] = {
                "malware_family": "Emotet",
                "file_type": "PE32 executable",
                "first_seen": "2024-01-15T08:00:00Z",
                "prevalence": "low",
                "verdict": "malicious"
            }
            
        return file_analysis
        
    async def _query_threat_intelligence(
        self,
        alert: AlertMessage
    ) -> Dict[str, Any]:
        """查詢外部威脅情報來源。"""
        # 模擬威脅情報查詢
        return {
            "iocs": [
                {"type": "ip", "value": ip, "confidence": 0.8}
                for ip in alert.source_ips
            ],
            "ttps": ["T1055", "T1057", "T1082"],  # MITRE ATT&CK
            "threat_actors": ["APT28"],
            "related_campaigns": ["Operation-X"]
        }
        
    async def _build_threat_profile(
        self,
        task: Task,
        alert: AlertMessage,
        graph_context: Dict[str, Any],
        vector_context: Dict[str, Any],
        enrichment: Dict[str, Any]
    ) -> ThreatProfile:
        """從所有來源建立全面的威脅設定檔。"""
        # 確定威脅類別
        threat_category = await self._determine_threat_category(
            alert, graph_context, vector_context
        )
        
        # 計算總體風險分數
        risk_components = {
            "graph_risk": graph_context.get("risk_score", 0) * 0.3,
            "anomaly_risk": vector_context.get("anomaly_score", 0) * 0.2,
            "severity_risk": {"LOW": 0.2, "MEDIUM": 0.5, "HIGH": 0.8, "CRITICAL": 1.0}[alert.severity] * 0.2,
            "asset_risk": self._calculate_asset_risk(enrichment.get("asset_info", {})) * 0.3
        }
        
        overall_risk = sum(risk_components.values())
        
        # 產生建議
        recommendations = await self._generate_recommendations(
            threat_category, overall_risk, enrichment
        )
        
        return ThreatProfile(
            task_id=task.task_id,
            alert=alert,
            graph_context=GraphContext(**graph_context),
            vector_context=VectorContext(**vector_context),
            asset_criticality={
                asset: info.get("criticality", "medium")
                for asset, info in enrichment.get("asset_info", {}).items()
            },
            asset_vulnerabilities={
                asset: info.get("vulnerabilities", [])
                for asset, info in enrichment.get("asset_info", {}).items()
            },
            threat_category=threat_category,
            threat_actor=enrichment.get("threat_intel", {}).get("threat_actors", [None])[0],
            campaign_id=graph_context.get("campaigns", [None])[0],
            overall_risk_score=overall_risk,
            impact_assessment={
                "data_exposure": overall_risk * 0.7,
                "system_availability": overall_risk * 0.5,
                "reputation": overall_risk * 0.3
            },
            likelihood_assessment=overall_risk * 0.8,
            recommended_actions=recommendations,
            priority_score=overall_risk * 10
        )
        
    async def _determine_threat_category(
        self,
        alert: AlertMessage,
        graph_context: Dict[str, Any],
        vector_context: Dict[str, Any]
    ) -> ThreatCategory:
        """使用機器學習/規則確定威脅類別。"""
        # 使用偵測到的模式
        patterns = graph_context.get("patterns", []) + vector_context.get("detected_patterns", [])
        
        category_mapping = {
            "LATERAL_MOVEMENT": ThreatCategory.LATERAL_MOVEMENT,
            "C2_COMMUNICATION": ThreatCategory.COMMAND_AND_CONTROL,
            "DATA_EXFILTRATION": ThreatCategory.DATA_EXFILTRATION,
            "PRIVILEGE_ESCALATION": ThreatCategory.PRIVILEGE_ESCALATION
        }
        
        for pattern in patterns:
            if pattern in category_mapping:
                return category_mapping[pattern]
                
        # 後備為警報類別
        return alert.suspected_category or ThreatCategory.UNKNOWN
        
    def _calculate_asset_risk(self, asset_info: Dict[str, Any]) -> float:
        """根據資產重要性計算風險。"""
        if not asset_info:
            return 0.5
            
        criticality_scores = {
            "low": 0.2,
            "medium": 0.5,
            "high": 0.8,
            "critical": 1.0
        }
        
        scores = [
            criticality_scores.get(info.get("criticality", "medium"), 0.5)
            for info in asset_info.values()
        ]
        
        return sum(scores) / len(scores) if scores else 0.5
        
    async def _generate_recommendations(
        self,
        threat_category: ThreatCategory,
        risk_score: float,
        enrichment: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """產生可行的建議。"""
        recommendations = []
        
        # 特定類別的建議
        if threat_category == ThreatCategory.LATERAL_MOVEMENT:
            recommendations.extend([
                {
                    "action": "ISOLATE_HOST",
                    "priority": 1,
                    "targets": list(enrichment.get("asset_info", {}).keys())
                },
                {
                    "action": "DISABLE_USER",
                    "priority": 2,
                    "targets": list(enrichment.get("user_info", {}).keys())
                }
            ])
            
        elif threat_category == ThreatCategory.DATA_EXFILTRATION:
            recommendations.extend([
                {
                    "action": "BLOCK_IP",
                    "priority": 1,
                    "targets": list(enrichment.get("ip_reputation", {}).keys())
                },
                {
                    "action": "QUARANTINE_FILE",
                    "priority": 2,
                    "targets": list(enrichment.get("file_analysis", {}).keys())
                }
            ])
            
        # 基於風險的建議
        if risk_score > 0.8:
            recommendations.append({
                "action": "CREATE_TICKET",
                "priority": 1,
                "parameters": {
                    "severity": "critical",
                    "assignee": "incident-response-team"
                }
            })
            
        return recommendations
        
    def _update_avg_hunt_time(self, hunt_time: float) -> None:
        """更新平均狩獵時間指標。"""
        current_avg = self.metrics["avg_hunt_time"]
        hunt_count = self.metrics["hunts_completed"]
        
        # 計算新平均值
        self.metrics["avg_hunt_time"] = (
            (current_avg * (hunt_count - 1) + hunt_time) / hunt_count
        )
        
    async def _process_hunts_loop(self) -> None:
        """處理活動中的狩獵並處理逾時。"""
        while True:
            try:
                await asyncio.sleep(30)  # 每 30 秒檢查一次
                
                current_time = datetime.utcnow()
                
                for task_id, hunt in list(self.active_hunts.items()):
                    # 檢查逾時
                    elapsed = (current_time - hunt.task.created_at).total_seconds()
                    
                    if elapsed > hunt.timeout_seconds:
                        logger.warning("狩獵逾時",
                                     task_id=task_id,
                                     elapsed_seconds=elapsed)
                                     
                        # 建立最小威脅設定檔
                        threat_profile = ThreatProfile(
                            task_id=task_id,
                            alert=hunt.alert,
                            graph_context=GraphContext(),
                            vector_context=VectorContext(),
                            threat_category=ThreatCategory.UNKNOWN,
                            overall_risk_score=0.5,
                            priority_score=5.0
                        )
                        
                        # 無論如何都發送到執行者
                        execution_message = ExecutionMessage(
                            task=hunt.task,
                            threat_profile=threat_profile,
                            analysis_depth="quick"
                        )
                        
                        await self.broker.publish(
                            settings.execution_queue,
                            execution_message.dict()
                        )
                        
                        del self.active_hunts[task_id]
                        
            except Exception as e:
                logger.error("狩獵處理迴圈錯誤", error=str(e))
                
    async def _metrics_reporting_loop(self) -> None:
        """定期回報指標。"""
        while True:
            try:
                await asyncio.sleep(300)  # 每 5 分鐘回報一次
                
                logger.info("獵人代理指標",
                          metrics=dict(self.metrics),
                          active_hunts=len(self.active_hunts))
                          
            except Exception as e:
                logger.error("指標回報失敗", error=str(e))
                
    async def _cleanup_loop(self) -> None:
        """清理舊的狩獵結果。"""
        while True:
            try:
                await asyncio.sleep(3600)  # 每小時執行一次
                
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                
                # 清理舊結果
                old_tasks = [
                    task_id for task_id, profile in self.hunt_results.items()
                    if profile.created_at < cutoff_time
                ]
                
                for task_id in old_tasks:
                    del self.hunt_results[task_id]
                    
                logger.debug("清理完成",
                           removed_results=len(old_tasks))
                           
            except Exception as e:
                logger.error("清理失敗", error=str(e))