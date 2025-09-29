"""Hunter Agent: Deep investigation and threat hunting specialist."""
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
    Hunter Agent - The Investigation Specialist
    
    Responsibilities:
    1. Deep threat investigation
    2. GraphRAG analysis for entity relationships
    3. Vector similarity search for patterns
    4. Context enrichment and correlation
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
        
        # Processing state
        self.active_hunts: Dict[str, HuntingMessage] = {}
        self.hunt_results: Dict[str, ThreatProfile] = {}
        
        # Performance tracking
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
        """Initialize the Hunter Agent."""
        await asyncio.gather(
            self.broker.connect(),
            self.graph_db.connect(),
            self.vector_db.connect()
        )
        
        # Subscribe to hunting queue
        await self.broker.subscribe(
            settings.hunting_queue,
            self._handle_hunting_request
        )
        
        logger.info("Hunter Agent initialized", agent_id=self.agent_id)
        
    async def start(self) -> None:
        """Start the Hunter Agent's main loop."""
        logger.info("Hunter Agent starting", agent_id=self.agent_id)
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self._process_hunts_loop()),
            asyncio.create_task(self._metrics_reporting_loop()),
            asyncio.create_task(self._cleanup_loop())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Hunter Agent stopping")
            for task in tasks:
                task.cancel()
                
    async def stop(self) -> None:
        """Stop the Hunter Agent."""
        await asyncio.gather(
            self.broker.disconnect(),
            self.graph_db.disconnect(),
            self.vector_db.disconnect()
        )
        logger.info("Hunter Agent stopped", agent_id=self.agent_id)
        
    async def health_check(self) -> Dict[str, Any]:
        """Return agent health status."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "status": "healthy",
            "active_hunts": len(self.active_hunts),
            "metrics": dict(self.metrics)
        }
        
    async def hunt_threat(self, message: HuntingMessage) -> ThreatProfile:
        """Perform comprehensive threat hunting."""
        start_time = datetime.utcnow()
        task = message.task
        alert = message.alert
        
        logger.info("Starting threat hunt",
                   task_id=task.task_id,
                   alert_id=alert.alert_id,
                   priority=message.priority)
                   
        self.metrics["hunts_started"] += 1
        
        try:
            # Parallel execution of investigation tasks
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
            
            # Wait for all tasks to complete
            graph_context_data, vector_context_data, enrichment_data = await asyncio.gather(
                graph_task, vector_task, enrichment_task
            )
            
            # Build comprehensive threat profile
            threat_profile = await self._build_threat_profile(
                task, alert, graph_context_data, vector_context_data, enrichment_data
            )
            
            # Store result
            self.hunt_results[task.task_id] = threat_profile
            
            # Calculate metrics
            hunt_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_avg_hunt_time(hunt_time)
            self.metrics["hunts_completed"] += 1
            
            logger.info("Threat hunt completed",
                       task_id=task.task_id,
                       risk_score=threat_profile.overall_risk_score,
                       hunt_time_seconds=hunt_time)
                       
            return threat_profile
            
        except Exception as e:
            logger.error("Threat hunt failed",
                        task_id=task.task_id,
                        error=str(e))
            raise
            
    async def query_graph(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Query GraphRAG for entity relationships and attack paths."""
        self.metrics["graph_queries"] += 1
        alert = context["alert"]
        max_depth = context.get("max_depth", 3)
        
        try:
            # Extract entities from alert
            entities = await self._extract_entities(alert)
            
            # Create or update nodes in graph
            node_ids = await self._create_graph_nodes(entities, alert)
            
            # Find attack paths and relationships
            attack_paths = []
            relationships = []
            
            for node_id in node_ids:
                # Find paths from this node
                paths = await self.graph_db.find_paths(
                    start_node=node_id,
                    max_depth=max_depth
                )
                attack_paths.extend(paths)
                
            # Query for specific patterns
            patterns = await self._query_attack_patterns(entities, alert)
            
            # Calculate graph-based risk score
            risk_score = await self._calculate_graph_risk(attack_paths, relationships)
            
            # Find related campaigns
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
            logger.error("Graph query failed", error=str(e))
            return {
                "entities": [],
                "relationships": [],
                "attack_paths": [],
                "risk_score": 0.0
            }
            
    async def search_vectors(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Search vector database for similar alerts and patterns."""
        self.metrics["vector_searches"] += 1
        alert = context["alert"]
        time_window = context.get("time_window", 24)
        top_k = context.get("top_k", 10)
        
        try:
            # Generate embedding for alert
            alert_text = f"{alert.title} {alert.description}"
            alert_embedding = await self.llm.embed(alert_text)
            
            # Search for similar alerts
            similar_alerts = await self.vector_db.search(
                vector=alert_embedding,
                top_k=top_k,
                filters={
                    "timestamp": {
                        "$gte": (datetime.utcnow() - timedelta(hours=time_window)).isoformat()
                    }
                }
            )
            
            # Analyze patterns in similar alerts
            patterns = await self._analyze_alert_patterns(similar_alerts)
            
            # Calculate anomaly score
            anomaly_score = await self._calculate_anomaly_score(
                alert_embedding, similar_alerts
            )
            
            # Get resolution history
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
            logger.error("Vector search failed", error=str(e))
            return {
                "similar_alerts": [],
                "similarity_scores": [],
                "detected_patterns": [],
                "anomaly_score": 0.0,
                "occurrence_count": 0
            }
            
    async def enrich_context(self, alert: AlertMessage) -> Dict[str, Any]:
        """Enrich alert with additional context from various sources."""
        self.metrics["enrichments"] += 1
        
        try:
            # Parallel enrichment tasks
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
                    logger.error(f"Enrichment failed: {name}", error=str(e))
                    results[name] = {}
                    
            return results
            
        except Exception as e:
            logger.error("Context enrichment failed", error=str(e))
            return {}
            
    async def _handle_hunting_request(self, message: Dict[str, Any]) -> None:
        """Handle incoming hunting request from Manager Agent."""
        try:
            hunting_message = HuntingMessage(**message)
            task_id = hunting_message.task.task_id
            
            # Store active hunt
            self.active_hunts[task_id] = hunting_message
            
            # Perform threat hunting
            threat_profile = await self.hunt_threat(hunting_message)
            
            # Create execution message
            execution_message = ExecutionMessage(
                task=hunting_message.task,
                threat_profile=threat_profile,
                auto_execute_low_risk=settings.auto_execute_low_risk,
                analysis_depth="comprehensive" if hunting_message.priority == "critical" else "standard"
            )
            
            # Publish to Executor Agent
            await self.broker.publish(
                settings.execution_queue,
                execution_message.dict()
            )
            
            # Clean up
            del self.active_hunts[task_id]
            
        except Exception as e:
            logger.error("Failed to handle hunting request", error=str(e))
            
    async def _extract_entities(self, alert: AlertMessage) -> List[Dict[str, Any]]:
        """Extract entities from alert using NLP."""
        prompt = f"""
        Extract security-relevant entities from this alert:
        
        Title: {alert.title}
        Description: {alert.description}
        
        Extract:
        1. IP addresses (with type: source/destination/c2)
        2. Hostnames/Domains
        3. User accounts
        4. File paths and hashes
        5. Process names
        6. Registry keys
        7. Network ports
        
        Return as JSON list of entities with type and value.
        """
        
        response = await self.llm.generate(prompt, temperature=0.0, max_tokens=500)
        entities = json.loads(response)
        
        # Add entities from structured data
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
        """Create or update nodes in the graph database."""
        node_ids = []
        
        for entity in entities:
            # Create node
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
            
        # Create alert node
        alert_node_id = await self.graph_db.create_node(
            node_type="alert",
            properties={
                "alert_id": alert.alert_id,
                "severity": alert.severity,
                "timestamp": alert.timestamp.isoformat(),
                "source": alert.source
            }
        )
        
        # Create relationships
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
        """Query for known attack patterns in the graph."""
        patterns = []
        
        # MITRE ATT&CK pattern matching
        cypher_queries = [
            # Lateral movement pattern
            """
            MATCH (a:ip_address)-[:CONNECTS_TO]->(b:host)-[:HAS_USER]->(u:user_account)
            WHERE a.value IN $source_ips
            RETURN 'LATERAL_MOVEMENT' as pattern
            """,
            
            # C2 communication pattern
            """
            MATCH (h:host)-[:CONNECTS_TO]->(ip:ip_address)
            WHERE ip.reputation = 'malicious' AND h.value IN $hosts
            RETURN 'C2_COMMUNICATION' as pattern
            """,
            
            # Data exfiltration pattern
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
        """Calculate risk score based on graph analysis."""
        risk_score = 0.0
        
        # Factor 1: Number of attack paths
        path_score = min(len(attack_paths) * 10, 30)
        
        # Factor 2: Path criticality (shortest paths are more dangerous)
        if attack_paths:
            avg_path_length = sum(len(p) for p in attack_paths) / len(attack_paths)
            criticality_score = max(0, 30 - (avg_path_length * 5))
        else:
            criticality_score = 0
            
        # Factor 3: Entity reputation
        reputation_score = 0
        for path in attack_paths:
            for node in path:
                if node.get("reputation") == "malicious":
                    reputation_score += 10
                elif node.get("reputation") == "suspicious":
                    reputation_score += 5
                    
        reputation_score = min(reputation_score, 40)
        
        risk_score = path_score + criticality_score + reputation_score
        return min(risk_score / 100, 1.0)  # Normalize to 0-1
        
    async def _find_related_campaigns(
        self,
        entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Find related threat campaigns."""
        campaigns = []
        
        # Query for campaigns involving these entities
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
        """Analyze patterns in similar alerts."""
        if not similar_alerts:
            return []
            
        patterns = []
        
        # Time-based patterns
        timestamps = [a["timestamp"] for a in similar_alerts]
        if self._detect_time_pattern(timestamps):
            patterns.append("PERIODIC_ACTIVITY")
            
        # Source patterns
        sources = [a.get("source_ip") for a in similar_alerts if a.get("source_ip")]
        if len(set(sources)) == 1:
            patterns.append("SINGLE_SOURCE")
        elif len(set(sources)) < len(sources) * 0.2:
            patterns.append("CONCENTRATED_SOURCE")
            
        # Target patterns
        targets = [a.get("target") for a in similar_alerts if a.get("target")]
        if len(set(targets)) == 1:
            patterns.append("TARGETED_ATTACK")
            
        # Severity escalation
        severities = [a.get("severity", 0) for a in similar_alerts]
        if severities == sorted(severities):
            patterns.append("ESCALATING_SEVERITY")
            
        return patterns
        
    def _detect_time_pattern(self, timestamps: List[datetime]) -> bool:
        """Detect if timestamps follow a pattern."""
        if len(timestamps) < 3:
            return False
            
        # Calculate time differences
        sorted_times = sorted(timestamps)
        diffs = []
        for i in range(1, len(sorted_times)):
            diff = (sorted_times[i] - sorted_times[i-1]).total_seconds()
            diffs.append(diff)
            
        # Check for regularity (standard deviation < 20% of mean)
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
        """Calculate anomaly score based on vector similarity."""
        if not similar_alerts:
            return 1.0  # Highly anomalous if no similar alerts
            
        # Average similarity of top matches
        similarities = [a.get("score", 0) for a in similar_alerts[:5]]
        avg_similarity = sum(similarities) / len(similarities)
        
        # Anomaly score is inverse of similarity
        return 1.0 - avg_similarity
        
    async def _get_resolution_history(
        self,
        similar_alerts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Get resolution history for similar alerts."""
        history = []
        
        for alert in similar_alerts[:10]:  # Limit to recent alerts
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
        """Enrich asset information from CMDB or inventory."""
        asset_info = {}
        
        for asset in assets:
            # Simulate CMDB lookup
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
        """Enrich user information from directory services."""
        user_info = {}
        
        for user in users:
            # Simulate AD lookup
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
        """Check IP reputation from threat intelligence."""
        ip_reputation = {}
        
        for ip in ips:
            # Simulate threat intel lookup
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
        """Analyze file hashes against threat intelligence."""
        file_analysis = {}
        
        for hash_val in hashes:
            # Simulate file analysis
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
        """Query external threat intelligence sources."""
        # Simulate threat intel query
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
        """Build comprehensive threat profile from all sources."""
        # Determine threat category
        threat_category = await self._determine_threat_category(
            alert, graph_context, vector_context
        )
        
        # Calculate overall risk score
        risk_components = {
            "graph_risk": graph_context.get("risk_score", 0) * 0.3,
            "anomaly_risk": vector_context.get("anomaly_score", 0) * 0.2,
            "severity_risk": {"LOW": 0.2, "MEDIUM": 0.5, "HIGH": 0.8, "CRITICAL": 1.0}[alert.severity] * 0.2,
            "asset_risk": self._calculate_asset_risk(enrichment.get("asset_info", {})) * 0.3
        }
        
        overall_risk = sum(risk_components.values())
        
        # Generate recommendations
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
        """Determine the threat category using ML/rules."""
        # Use patterns detected
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
                
        # Fallback to alert category
        return alert.suspected_category or ThreatCategory.UNKNOWN
        
    def _calculate_asset_risk(self, asset_info: Dict[str, Any]) -> float:
        """Calculate risk based on asset criticality."""
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
        """Generate actionable recommendations."""
        recommendations = []
        
        # Category-specific recommendations
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
            
        # Risk-based recommendations
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
        """Update average hunt time metric."""
        current_avg = self.metrics["avg_hunt_time"]
        hunt_count = self.metrics["hunts_completed"]
        
        # Calculate new average
        self.metrics["avg_hunt_time"] = (
            (current_avg * (hunt_count - 1) + hunt_time) / hunt_count
        )
        
    async def _process_hunts_loop(self) -> None:
        """Process active hunts and handle timeouts."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                current_time = datetime.utcnow()
                
                for task_id, hunt in list(self.active_hunts.items()):
                    # Check for timeout
                    elapsed = (current_time - hunt.task.created_at).total_seconds()
                    
                    if elapsed > hunt.timeout_seconds:
                        logger.warning("Hunt timeout",
                                     task_id=task_id,
                                     elapsed_seconds=elapsed)
                                     
                        # Create minimal threat profile
                        threat_profile = ThreatProfile(
                            task_id=task_id,
                            alert=hunt.alert,
                            graph_context=GraphContext(),
                            vector_context=VectorContext(),
                            threat_category=ThreatCategory.UNKNOWN,
                            overall_risk_score=0.5,
                            priority_score=5.0
                        )
                        
                        # Send to executor anyway
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
                logger.error("Hunt processing loop error", error=str(e))
                
    async def _metrics_reporting_loop(self) -> None:
        """Report metrics periodically."""
        while True:
            try:
                await asyncio.sleep(300)  # Report every 5 minutes
                
                logger.info("Hunter Agent metrics",
                          metrics=dict(self.metrics),
                          active_hunts=len(self.active_hunts))
                          
            except Exception as e:
                logger.error("Metrics reporting failed", error=str(e))
                
    async def _cleanup_loop(self) -> None:
        """Clean up old hunt results."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run hourly
                
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                
                # Clean old results
                old_tasks = [
                    task_id for task_id, profile in self.hunt_results.items()
                    if profile.created_at < cutoff_time
                ]
                
                for task_id in old_tasks:
                    del self.hunt_results[task_id]
                    
                logger.debug("Cleanup completed",
                           removed_results=len(old_tasks))
                           
            except Exception as e:
                logger.error("Cleanup failed", error=str(e))
