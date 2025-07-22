"""Tests for agent implementations."""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from src.agents import ManagerAgent, HunterAgent, ExecutorAgent
from src.core.models import (
    AlertMessage, AlertSeverity, Task, TaskStatus,
    HuntingMessage, ExecutionMessage, ThreatProfile
)


@pytest.fixture
async def mock_broker():
    """Mock message broker."""
    broker = AsyncMock()
    broker.connect = AsyncMock()
    broker.disconnect = AsyncMock()
    broker.publish = AsyncMock()
    broker.subscribe = AsyncMock()
    return broker


@pytest.fixture
async def mock_llm():
    """Mock LLM provider."""
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value='{"category": "MALWARE", "requires_hunting": true}')
    llm.embed = AsyncMock(return_value=[0.1] * 1536)
    return llm


@pytest.fixture
async def mock_graph_db():
    """Mock graph database."""
    db = AsyncMock()
    db.connect = AsyncMock()
    db.disconnect = AsyncMock()
    db.create_node = AsyncMock(return_value="node_123")
    db.create_relationship = AsyncMock(return_value="rel_123")
    db.find_paths = AsyncMock(return_value=[])
    db.query = AsyncMock(return_value=[])
    return db


@pytest.fixture
async def mock_vector_db():
    """Mock vector database."""
    db = AsyncMock()
    db.connect = AsyncMock()
    db.disconnect = AsyncMock()
    db.insert = AsyncMock(return_value="vec_123")
    db.search = AsyncMock(return_value=[])
    return db


class TestManagerAgent:
    """Test Manager Agent functionality."""
    
    @pytest.mark.asyncio
    async def test_agent_initialization(self, mock_broker, mock_llm):
        """Test agent initialization."""
        agent = ManagerAgent(mock_broker, mock_llm)
        
        assert agent.agent_type == "manager"
        assert agent.agent_id.startswith("manager-")
        
        await agent.initialize()
        mock_broker.connect.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_alert_processing(self, mock_broker, mock_llm):
        """Test alert processing."""
        agent = ManagerAgent(mock_broker, mock_llm)
        
        alert = AlertMessage(
            alert_id="test_123",
            source="test",
            timestamp="2024-01-20T10:00:00Z",
            severity=AlertSeverity.HIGH,
            title="Test Alert",
            description="Test description",
            raw_data={},
            affected_assets=["host1"],
            source_ips=["1.2.3.4"]
        )
        
        task = await agent.process_alert(alert)
        
        assert task.alert_id == alert.alert_id
        assert task.severity == alert.severity
        assert task.status == TaskStatus.HUNTING
        
        # Verify message was published
        mock_broker.publish.assert_called()
        
    @pytest.mark.asyncio
    async def test_alert_deduplication(self, mock_broker, mock_llm):
        """Test alert deduplication."""
        agent = ManagerAgent(mock_broker, mock_llm)
        
        alert1 = AlertMessage(
            alert_id="test_123",
            source="test",
            timestamp="2024-01-20T10:00:00Z",
            severity=AlertSeverity.HIGH,
            title="Test Alert",
            description="Test description",
            raw_data={},
            affected_assets=["host1"],
            source_ips=["1.2.3.4"]
        )
        
        # Process first alert
        task1 = await agent.process_alert(alert1)
        
        # Process duplicate alert
        alert2 = alert1.copy(update={"alert_id": "test_124"})
        task2 = await agent.process_alert(alert2)
        
        # Should return same task
        assert task1.task_id == task2.task_id


class TestHunterAgent:
    """Test Hunter Agent functionality."""
    
    @pytest.mark.asyncio
    async def test_threat_hunting(self, mock_broker, mock_graph_db, mock_vector_db, mock_llm):
        """Test threat hunting process."""
        agent = HunterAgent(mock_broker, mock_graph_db, mock_vector_db, mock_llm)
        
        task = Task(
            alert_id="test_123",
            alert_source="test",
            alert_timestamp="2024-01-20T10:00:00Z",
            severity=AlertSeverity.HIGH
        )
        
        alert = AlertMessage(
            alert_id="test_123",
            source="test",
            timestamp="2024-01-20T10:00:00Z",
            severity=AlertSeverity.HIGH,
            title="Test Alert",
            description="Test description",
            raw_data={},
            affected_assets=["host1"],
            source_ips=["1.2.3.4"]
        )
        
        message = HuntingMessage(task=task, alert=alert)
        
        profile = await agent.hunt_threat(message)
        
        assert isinstance(profile, ThreatProfile)
        assert profile.task_id == task.task_id
        assert profile.overall_risk_score >= 0
        assert profile.overall_risk_score <= 1
        
    @pytest.mark.asyncio
    async def test_graph_querying(self, mock_broker, mock_graph_db, mock_vector_db, mock_llm):
        """Test graph database querying."""
        agent = HunterAgent(mock_broker, mock_graph_db, mock_vector_db, mock_llm)
        
        context = {
            "alert": AlertMessage(
                alert_id="test_123",
                source="test",
                timestamp="2024-01-20T10:00:00Z",
                severity=AlertSeverity.HIGH,
                title="Test",
                description="Test",
                raw_data={},
                source_ips=["1.2.3.4"]
            ),
            "max_depth": 3
        }
        
        result = await agent.query_graph(context)
        
        assert "entities" in result
        assert "relationships" in result
        assert "attack_paths" in result
        assert "risk_score" in result


class TestExecutorAgent:
    """Test Executor Agent functionality."""
    
    @pytest.mark.asyncio
    async def test_threat_analysis(self, mock_broker, mock_llm):
        """Test threat analysis."""
        mock_notifier = AsyncMock()
        mock_executor = AsyncMock()
        
        agent = ExecutorAgent(mock_broker, mock_llm, mock_notifier, mock_executor)
        
        task = Task(
            alert_id="test_123",
            alert_source="test",
            alert_timestamp="2024-01-20T10:00:00Z",
            severity=AlertSeverity.HIGH
        )
        
        alert = AlertMessage(
            alert_id="test_123",
            source="test",
            timestamp="2024-01-20T10:00:00Z",
            severity=AlertSeverity.HIGH,
            title="Test Alert",
            description="Test description",
            raw_data={},
            affected_assets=["host1"],
            source_ips=["1.2.3.4"]
        )
        
        profile = ThreatProfile(
            task_id=task.task_id,
            alert=alert,
            graph_context={},
            vector_context={},
            threat_category="MALWARE",
            overall_risk_score=0.8,
            priority_score=8.0
        )
        
        message = ExecutionMessage(task=task, threat_profile=profile)
        
        report = await agent.analyze_threat(message)
        
        assert report.task_id == task.task_id
        assert len(report.executive_summary) > 0
        assert len(report.recommended_actions) > 0
        
    @pytest.mark.asyncio  
    async def test_action_execution(self, mock_broker, mock_llm):
        """Test action execution."""
        mock_notifier = AsyncMock()
        mock_executor = AsyncMock()
        mock_executor.validate_action = AsyncMock(return_value=True)
        mock_executor.execute = AsyncMock(return_value={"success": True})
        
        agent = ExecutorAgent(mock_broker, mock_llm, mock_notifier, mock_executor)
        
        action = {
            "action_id": "act_123",
            "action_type": "ISOLATE_HOST",
            "parameters": {"hosts": ["host1"]}
        }
        
        result = await agent.execute_action(action, "approval_123")
        
        assert result["success"] is True
        mock_executor.validate_action.assert_called_once()
        mock_executor.execute.assert_called_once()
