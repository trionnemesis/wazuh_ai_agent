"""Hunter Agent Node for LangGraph implementation."""
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda, RunnableParallel
from langchain_core.tools import Tool
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from ..state import AgentState, Investigation, SecurityAlert

logger = structlog.get_logger()


class ThreatIntelligence(BaseModel):
    """Threat intelligence findings."""
    indicators: List[str] = Field(description="Threat indicators found")
    ttps: List[str] = Field(description="Tactics, Techniques, and Procedures identified")
    related_campaigns: List[str] = Field(description="Related threat campaigns")
    confidence_score: float = Field(description="Confidence score 0-1")


class InvestigationResult(BaseModel):
    """Hunter investigation result."""
    risk_score: float = Field(description="Risk score 0-100")
    affected_assets: List[str] = Field(description="List of affected assets")
    attack_indicators: List[str] = Field(description="Attack indicators found")
    findings: List[Dict[str, Any]] = Field(description="Detailed findings")
    recommendations: List[str] = Field(description="Recommended actions")
    evidence: Dict[str, Any] = Field(default_factory=dict)
    threat_intel: Optional[ThreatIntelligence] = None


class HunterNode:
    """Hunter agent node that performs threat investigation."""
    
    def __init__(self, llm_provider, graph_db=None, vector_db=None):
        """Initialize Hunter node with LLM provider and databases."""
        self.llm = llm_provider
        self.graph_db = graph_db
        self.vector_db = vector_db
        self.parser = JsonOutputParser(pydantic_object=InvestigationResult)
        
        # Create investigation prompt
        self.investigation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the Hunter Agent in a security orchestration system.
            Your responsibilities include:
            1. Deep investigation of security alerts
            2. Threat hunting and correlation
            3. Identifying attack patterns and indicators
            4. Risk assessment and scoring
            5. Gathering evidence and context
            6. Providing actionable recommendations
            
            Investigation approach:
            - Analyze the alert details thoroughly
            - Look for patterns and anomalies
            - Correlate with historical data
            - Identify potential attack vectors
            - Assess business impact
            - Gather forensic evidence
            
            Output your findings in the specified JSON format."""),
            MessagesPlaceholder(variable_name="messages", optional=True),
            ("human", """Investigate this security alert:
            
            Alert Details:
            ID: {alert_id}
            Type: {alert_type}
            Severity: {severity}
            Source: {source}
            Description: {description}
            Timestamp: {timestamp}
            
            Alert Context:
            {alert_context}
            
            Historical Context:
            {historical_context}
            
            External Intelligence:
            {threat_intel}
            
            Perform a thorough investigation and provide findings.
            
            {format_instructions}""")
        ])
        
        # Create tool-based investigation chains
        self._setup_investigation_tools()
        self._build_chains()
    
    def _setup_investigation_tools(self):
        """Setup investigation tools for the Hunter agent."""
        self.tools = []
        
        # Graph database query tool
        if self.graph_db:
            graph_tool = Tool(
                name="query_graph_db",
                description="Query the graph database for entity relationships and patterns",
                func=self._query_graph_db
            )
            self.tools.append(graph_tool)
        
        # Vector database search tool
        if self.vector_db:
            vector_tool = Tool(
                name="search_vector_db",
                description="Search vector database for similar alerts and patterns",
                func=self._search_vector_db
            )
            self.tools.append(vector_tool)
        
        # Threat intelligence lookup tool
        threat_intel_tool = Tool(
            name="lookup_threat_intel",
            description="Look up threat intelligence for indicators",
            func=self._lookup_threat_intel
        )
        self.tools.append(threat_intel_tool)
        
        # Create tool node if tools are available
        if self.tools:
            self.tool_node = ToolNode(self.tools)
    
    def _build_chains(self):
        """Build LCEL chains for investigation."""
        # Main investigation chain
        self.investigation_chain = (
            RunnablePassthrough.assign(
                format_instructions=lambda x: self.parser.get_format_instructions()
            )
            | self.investigation_prompt
            | self.llm
            | self.parser
        )
        
        # Parallel investigation chain for gathering context
        self.context_gathering_chain = RunnableParallel(
            historical_context=RunnableLambda(self._get_historical_context),
            threat_intel=RunnableLambda(self._get_threat_intelligence),
            graph_analysis=RunnableLambda(self._analyze_graph_relationships)
        )
    
    async def _query_graph_db(self, query: str) -> str:
        """Query the graph database."""
        if not self.graph_db:
            return "Graph database not available"
        
        try:
            # Implement actual graph query logic
            result = await self.graph_db.query(query)
            return str(result)
        except Exception as e:
            logger.error("Graph DB query error", error=str(e))
            return f"Error querying graph DB: {str(e)}"
    
    async def _search_vector_db(self, query: str) -> str:
        """Search the vector database."""
        if not self.vector_db:
            return "Vector database not available"
        
        try:
            # Implement actual vector search logic
            results = await self.vector_db.search(query, limit=5)
            return str(results)
        except Exception as e:
            logger.error("Vector DB search error", error=str(e))
            return f"Error searching vector DB: {str(e)}"
    
    async def _lookup_threat_intel(self, indicators: str) -> str:
        """Look up threat intelligence for given indicators."""
        # This would integrate with actual threat intel feeds
        # For now, return mock data
        return f"Threat intel lookup for: {indicators} - No known campaigns identified"
    
    async def _get_historical_context(self, alert_data: Dict[str, Any]) -> str:
        """Get historical context for the alert."""
        # Query historical data
        if self.vector_db:
            similar_alerts = await self._search_vector_db(
                f"similar alerts to {alert_data.get('type', 'unknown')}"
            )
            return f"Historical context: {similar_alerts}"
        return "No historical data available"
    
    async def _get_threat_intelligence(self, alert_data: Dict[str, Any]) -> str:
        """Get threat intelligence for the alert."""
        # Extract indicators from alert
        indicators = []
        if "details" in alert_data:
            # Extract IPs, domains, hashes, etc.
            details = alert_data["details"]
            if isinstance(details, dict):
                indicators.extend(details.get("indicators", []))
        
        if indicators:
            return await self._lookup_threat_intel(", ".join(indicators))
        return "No indicators to lookup"
    
    async def _analyze_graph_relationships(self, alert_data: Dict[str, Any]) -> str:
        """Analyze entity relationships in graph database."""
        if self.graph_db:
            # Extract entities from alert
            entities = alert_data.get("details", {}).get("entities", [])
            if entities:
                query = f"MATCH path = (n)-[*..3]-(m) WHERE n.name IN {entities} RETURN path"
                return await self._query_graph_db(query)
        return "No graph analysis performed"
    
    async def __call__(self, state: AgentState) -> AgentState:
        """Process the current state and perform investigation."""
        logger.info("Hunter node processing", 
                   workflow_step=state.get("workflow_step"),
                   current_alert=state.get("current_alert"))
        
        try:
            # Check if we should investigate
            if state.get("workflow_step") != "investigation":
                logger.info("Not in investigation phase, skipping")
                return state
            
            # Get current alert
            current_alert = state.get("current_alert")
            if not current_alert:
                logger.warning("No current alert to investigate")
                return state
            
            # Convert to dict if needed
            if isinstance(current_alert, SecurityAlert):
                alert_dict = current_alert.model_dump()
            else:
                alert_dict = current_alert
            
            # Gather context in parallel
            context_data = await self.context_gathering_chain.ainvoke(alert_dict)
            
            # Prepare investigation context
            investigation_context = {
                "alert_id": alert_dict.get("id", "unknown"),
                "alert_type": alert_dict.get("type", "unknown"),
                "severity": alert_dict.get("severity", "unknown"),
                "source": alert_dict.get("source", "unknown"),
                "description": alert_dict.get("description", ""),
                "timestamp": alert_dict.get("timestamp", ""),
                "alert_context": str(alert_dict.get("context", {})),
                "historical_context": context_data.get("historical_context", ""),
                "threat_intel": context_data.get("threat_intel", ""),
                "messages": state.get("messages", [])
            }
            
            # Perform investigation
            investigation_result = await self.investigation_chain.ainvoke(investigation_context)
            
            # Log investigation results
            logger.info("Investigation completed",
                       alert_id=investigation_context["alert_id"],
                       risk_score=investigation_result.risk_score,
                       affected_assets=len(investigation_result.affected_assets))
            
            # Create Investigation object
            investigation = Investigation(
                alert_id=investigation_context["alert_id"],
                findings=investigation_result.findings,
                risk_score=investigation_result.risk_score,
                affected_assets=investigation_result.affected_assets,
                attack_indicators=investigation_result.attack_indicators,
                recommendations=investigation_result.recommendations,
                evidence=investigation_result.evidence
            )
            
            # Update state
            state["investigations"] = state.get("investigations", {})
            state["investigations"][investigation_context["alert_id"]] = investigation
            
            # Update alert status
            if isinstance(current_alert, dict):
                current_alert["investigation_status"] = "completed"
            
            # Update workflow
            state["workflow_step"] = "decision"
            state["agent_status"]["hunter"] = "completed"
            state["agent_status"]["manager"] = "pending"  # Manager needs to review
            
            # Add to workflow history
            state["workflow_history"] = state.get("workflow_history", [])
            state["workflow_history"].append({
                "step": "hunter_investigation",
                "timestamp": datetime.now().isoformat(),
                "result": {
                    "risk_score": investigation.risk_score,
                    "indicators_found": len(investigation.attack_indicators),
                    "affected_assets": len(investigation.affected_assets)
                }
            })
            
            # Update metrics
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["investigations_completed"] = \
                state["metrics"].get("investigations_completed", 0) + 1
            
        except Exception as e:
            logger.error("Hunter node error", error=str(e), exc_info=True)
            state["errors"] = state.get("errors", [])
            state["errors"].append({
                "agent": "hunter",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            state["agent_status"]["hunter"] = "error"
            # Fall back to manager for decision
            state["workflow_step"] = "decision"
            state["agent_status"]["manager"] = "pending"
        
        return state