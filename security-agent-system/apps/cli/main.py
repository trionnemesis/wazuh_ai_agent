"""使用 LangGraph 的安全代理系統的主要進入點。"""
import asyncio
import signal
import sys
from typing import Optional
import structlog
import click
from pathlib import Path

from security_agent_system.workflows.langgraph import LangGraphOrchestrator
from security_agent_system.core.config import settings
from security_agent_system.core.models import AlertMessage, AlertSeverity

# 設定結構化日誌
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# 全域協調器實例
orchestrator: Optional[LangGraphOrchestrator] = None


async def shutdown(signal_received):
    """優雅關機處理常式。"""
    logger.info(f"收到訊號 {signal_received.name}，正在關機...")
    
    if orchestrator:
        await orchestrator.stop()
        
    # 取消所有執行中的任務
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
        
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("關機完成")


@click.group()
def cli():
    """使用 LangGraph 多代理協調的安全代理系統。"""
    pass


@cli.command()
@click.option('--config', type=click.Path(exists=True), help='設定檔路徑')
def start(config):
    """啟動安全代理系統。"""
    global orchestrator
    
    # 如果有提供，則載入設定
    if config:
        settings.load_from_file(config)
    
    logger.info("正在啟動使用 LangGraph 的安全代理系統",
                environment=settings.environment,
                broker_type=settings.broker_type,
                default_llm=settings.default_llm_provider)
    
    # 建立協調器
    orchestrator = LangGraphOrchestrator()
    
    # 設定訊號處理常式
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig, lambda s=sig: asyncio.create_task(shutdown(s))
        )
    
    try:
        # 執行系統
        loop.run_until_complete(run_system())
    except KeyboardInterrupt:
        logger.info("使用者中斷")
    except Exception as e:
        logger.error("系統錯誤", error=str(e), exc_info=True)
    finally:
        loop.close()


async def run_system():
    """執行主系統迴圈。"""
    try:
        # 初始化協調器
        await orchestrator.initialize()
        
        # 啟動協調器
        await orchestrator.start()
        
        logger.info("系統正在執行。按 Ctrl+C 停止。")
        
        # 持續執行直到關機
        while True:
            await asyncio.sleep(1)
            
    except asyncio.CancelledError:
        logger.info("系統迴圈已取消")
        raise
    except Exception as e:
        logger.error("系統迴圈發生嚴重錯誤", error=str(e), exc_info=True)
        raise


@cli.command()
@click.option('--severity', type=click.Choice(['critical', 'high', 'medium', 'low', 'info']), 
              default='medium', help='警報嚴重性')
@click.option('--type', default='manual_test', help='警報類型')
@click.option('--source', default='cli', help='警報來源')
@click.argument('description')
def test_alert(severity, type, source, description):
    """傳送測試警報到系統。"""
    global orchestrator
    
    logger.info("正在傳送測試警報",
                severity=severity,
                type=type,
                description=description)
    
    # 為單一警報建立協調器
    orchestrator = LangGraphOrchestrator()
    
    # 建立警報
    alert_data = {
        "severity": severity,
        "type": type,
        "source": source,
        "description": description,
        "details": {
            "test": True,
            "cli_generated": True
        },
        "context": {
            "user": "cli_test",
            "purpose": "system_test"
        }
    }
    
    # 執行非同步函式
    loop = asyncio.get_event_loop()
    
    async def process_test_alert():
        try:
            await orchestrator.initialize()
            result = await orchestrator.process_manual_alert(alert_data)
            
            logger.info("測試警報已處理",
                       status=result.get("status"),
                       workflow_steps=len(result.get("workflow_history", [])))
            
            # 列印結果
            print("\n=== 警報處理結果 ===")
            print(f"警報 ID: {result.get('alert_id')}")
            print(f"狀態: {result.get('status')}")
            
            if result.get('investigation'):
                print(f"\n調查風險分數: {result['investigation'].risk_score}")
                print(f"受影響的資產: {', '.join(result['investigation'].affected_assets)}")
                print(f"建議: {', '.join(result['investigation'].recommendations)}")
            
            if result.get('execution_results'):
                print(f"\n已執行的行動: {len(result['execution_results'])}")
                for action in result['execution_results']:
                    print(f"  - {action['action_id']}: {action['status']}")
            
            print("\n=== 工作流程歷史 ===")
            for step in result.get('workflow_history', []):
                print(f"{step['timestamp']}: {step['step']}")
                
        except Exception as e:
            logger.error("處理測試警報失敗", error=str(e), exc_info=True)
        finally:
            await orchestrator.stop()
    
    loop.run_until_complete(process_test_alert())
    loop.close()


@cli.command()
def status():
    """檢查系統狀態。"""
    logger.info("正在檢查系統狀態")
    
    # 檢查設定
    print("\n=== 設定狀態 ===")
    print(f"環境: {settings.environment}")
    print(f"訊息代理: {settings.broker_type}")
    print(f"預設 LLM: {settings.default_llm_provider}")
    print(f"LLM 模型: {settings.default_llm_model}")
    
    # 檢查 API 金鑰
    print("\n=== API 金鑰狀態 ===")
    print(f"OpenAI: {'✓' if settings.openai_api_key else '✗'}")
    print(f"Anthropic: {'✓' if settings.anthropic_api_key else '✗'}")
    print(f"Google: {'✓' if settings.google_api_key else '✗'}")
    
    # 檢查服務
    print("\n=== 服務設定 ===")
    print(f"Neo4j URI: {settings.neo4j_uri}")
    print(f"ChromaDB 路徑: {settings.chromadb_path}")
    print(f"Slack Webhook: {'✓' if settings.slack_webhook_url else '✗'}")
    
    # 檢查代理設定
    print("\n=== 代理設定 ===")
    print(f"管理者 LLM: {settings.manager_config['llm_provider']}")
    print(f"獵人 LLM: {settings.hunter_config['llm_provider']}")
    print(f"執行者 LLM: {settings.executor_config['llm_provider']}")
    
    print("\n=== LangGraph 功能 ===")
    print("✓ 用於鏈組合的 LCEL (LangChain 表達式語言)")
    print("✓ 用於多代理協調的 LangGraph DAG")
    print("✓ 使用檢查點的狀態持久化")
    print("✓ 平行代理執行")
    print("✓ 人在環中的批准工作流程")
    print("✓ 錯誤處理和重試邏輯")


@cli.command("serve-langserve")
@click.option("--host", default="0.0.0.0", show_default=True)
@click.option("--port", default=8001, type=int, show_default=True)
def serve_langserve(host: str, port: int):
    """執行 LangServe FastAPI 部署。"""
    import uvicorn

    from apps.langserve.app import app

    logger.info("正在啟動 LangServe API", host=host, port=port)
    uvicorn.run(app, host=host, port=port, log_level="info")


@cli.command("serve-mcp")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8765, type=int, show_default=True)
def serve_mcp(host: str, port: int):
    """啟動用於 IDE 整合的 MCP 伺服器。"""
    from apps.mcp.server import run_server

    logger.info("正在啟動 MCP 伺服器", host=host, port=port)
    asyncio.run(run_server(host=host, port=port))


@cli.command()
@click.option('--output', type=click.Path(), default='langgraph_visualization.png',
              help='圖形視覺化的輸出路徑')
def visualize(output):
    """視覺化 LangGraph DAG 結構。"""
    logger.info("正在產生 LangGraph 視覺化")
    
    try:
        from security_agent_system.workflows.langgraph import (
            SecurityAgentGraph,
            ManagerNode,
            HunterNode,
            ExecutorNode,
        )
        
        # 建立用於視覺化的虛擬節點
        manager = ManagerNode(llm_provider=None)
        hunter = HunterNode(llm_provider=None)
        executor = ExecutorNode(llm_provider=None)
        
        # 建立圖
        graph = SecurityAgentGraph(
            manager_node=manager,
            hunter_node=hunter,
            executor_node=executor
        )
        
        # 獲取 mermaid 表示法
        mermaid_graph = graph.app.get_graph().draw_mermaid()
        
        print("\n=== LangGraph 結構 (Mermaid) ===")
        print(mermaid_graph)
        
        # 如果 graphviz 可用，嘗試產生 PNG
        try:
            from langgraph.graph import END
            graph_viz = graph.app.get_graph()
            graph_viz.draw_png(output)
            print(f"\n圖形視覺化已儲存至：{output}")
        except Exception as e:
            print(f"\n無法產生 PNG (請安裝 graphviz)：{e}")
            print("您可以在任何 Mermaid 檢視器中使用上面的 Mermaid 圖表")
            
    except Exception as e:
        logger.error("產生視覺化失敗", error=str(e))
        print(f"錯誤：{e}")


if __name__ == "__main__":
    cli()