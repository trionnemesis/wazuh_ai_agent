import os
import re
import logging
import traceback
import asyncio
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import aiohttp
import numpy as np
from sentence_transformers import SentenceTransformer

# <--- 新增: 匯入新的 LLM 類別 ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection

# --- 基礎設定 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 從環境變數讀取配置 ---
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "https://wazuh.indexer:9200")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "SecretPassword")

# <--- 修改: 讀取 LLM 供應商和對應的 Keys ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower() # 預設為 anthropic
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# <--- 新增: RAG / agent 決策迴圈 / 高風險通知 相關設定 ---
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
CONTEXT_LOOKBACK_HOURS = int(os.getenv("CONTEXT_LOOKBACK_HOURS", "1"))
CONTEXT_TOP_K = int(os.getenv("CONTEXT_TOP_K", "3"))
BROADENED_LOOKBACK_HOURS = int(os.getenv("BROADENED_LOOKBACK_HOURS", "24"))
WEBHOOK_URL = os.getenv("AI_AGENT_WEBHOOK_URL")
HIGH_RISK_LEVELS = {"critical", "high"}


# --- OpenSearch 客戶端 ---
client = AsyncOpenSearch(
    hosts=[OPENSEARCH_URL],
    http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
    use_ssl=True,
    verify_certs=False,
    ssl_show_warn=False,
    connection_class=AsyncHttpConnection
)

# <--- 新增: 本地嵌入模型 (用於 RAG 上下文排序，無需額外的向量資料庫服務) ---
logging.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)


# <--- 新增: 根據環境變數選擇 LLM 的函式 ---
def get_llm():
    """根據環境變數 LLM_PROVIDER 選擇並初始化 LLM"""
    logging.info(f"Selected LLM Provider: {LLM_PROVIDER}")

    if LLM_PROVIDER == 'gemini':
        if not GEMINI_API_KEY:
            raise ValueError("LLM_PROVIDER is 'gemini' but GEMINI_API_KEY is not set.")
        # Gemini 1.5 Flash 是速度和成本效益的絕佳選擇
        return ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GEMINI_API_KEY)

    elif LLM_PROVIDER == 'anthropic':
        if not ANTHROPIC_API_KEY:
            raise ValueError("LLM_PROVIDER is 'anthropic' but ANTHROPIC_API_KEY is not set.")
        # Claude 3 Haiku 是最快、最經濟的 Claude 模型，非常適合入門
        return ChatAnthropic(model="claude-3-haiku-20240307", anthropic_api_key=ANTHROPIC_API_KEY)
        # 備選模型:
        # return ChatAnthropic(model="claude-3-sonnet-20240229", anthropic_api_key=ANTHROPIC_API_KEY)

    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}. Please choose 'gemini' or 'anthropic'.")

# --- LangChain 元件 ---
# 1. LLM 模型 (透過新函式動態選擇)
llm = get_llm()

# 2. 提示模板：決策步驟 (讓 agent 判斷現有上下文是否足夠，或需要擴大查詢)
decision_prompt_template = ChatPromptTemplate.from_template(
    """You are a senior security analyst deciding how to triage a Wazuh alert.

    **Wazuh Alert:**
    {alert_summary}

    **Context gathered from the same host so far:**
    {context}

    **Decision Task:**
    Decide whether the context above is sufficient to triage this alert, or whether it would help
    to broaden the search for related events across other hosts (e.g. the same source IP or the
    same rule triggering elsewhere).

    Respond with EXACTLY one line, no extra text:
    DECISION: SUFFICIENT
    or
    DECISION: NEED_MORE_CONTEXT
    """
)

# 3. 提示模板：最終分析 (維持既有內容，額外要求輸出可解析的風險等級)
prompt_template = ChatPromptTemplate.from_template(
    """You are a senior security analyst. Your task is to triage a Wazuh alert based on the alert data and relevant log context.

    **Wazuh Alert:**
    {alert_summary}

    **Relevant Log Context from the same host (and related hosts, if broadened):**
    {context}

    **Your Analysis Task:**
    1. Briefly summarize the event.
    2. Assess the potential risk level (Critical, High, Medium, Low, Informational).
    3. Provide a clear recommendation for the next step (e.g., "Investigate user activity", "Block IP address", "No action needed").

    End your report with exactly one extra line in this exact format so it can be parsed automatically:
    RISK_LEVEL: <Critical|High|Medium|Low|Informational>

    **Your Triage Report:**
    """
)

# 4. 輸出解析器
output_parser = StrOutputParser()

# 5. 組成 LangChain 鏈
decision_chain = decision_prompt_template | llm | output_parser
chain = prompt_template | llm | output_parser


# --- RAG 上下文檢索 (使用 OpenSearch 撈候選日誌 + 本地 embedding 做相似度排序) ---
def _alert_text(source: dict) -> str:
    rule = source.get('rule', {})
    agent = source.get('agent', {})
    return f"Rule: {rule.get('description', 'N/A')} (Level: {rule.get('level', 'N/A')}) on Host: {agent.get('name', 'N/A')}. Log: {source.get('full_log', '')}"


async def _rank_by_similarity(query_text: str, candidates: list[str], top_k: int) -> list[str]:
    if not candidates:
        return []
    texts = [query_text] + candidates
    embeddings = await asyncio.to_thread(embedding_model.encode, texts)
    query_vec, candidate_vecs = embeddings[0], embeddings[1:]
    norms = np.linalg.norm(candidate_vecs, axis=1) * np.linalg.norm(query_vec)
    norms[norms == 0] = 1e-8
    scores = candidate_vecs @ query_vec / norms
    ranked_indices = np.argsort(scores)[::-1][:top_k]
    return [candidates[i] for i in ranked_indices]


async def fetch_recent_host_context(agent_name: str, exclude_id: str, alert_summary: str) -> str:
    """撈同一台主機最近的警報，用 embedding 相似度排序後取 top-k 當作 RAG 上下文。"""
    try:
        response = await client.search(
            index="wazuh-alerts-*",
            body={
                "query": {
                    "bool": {
                        "must": [
                            {"match": {"agent.name": agent_name}},
                            {"range": {"timestamp": {"gte": f"now-{CONTEXT_LOOKBACK_HOURS}h"}}},
                        ],
                        "must_not": [{"ids": {"values": [exclude_id]}}],
                    }
                },
                "sort": [{"timestamp": {"order": "desc"}}],
                "size": 20,
            },
        )
    except Exception as e:
        logging.warning(f"Failed to fetch recent host context: {e}")
        return "No additional context retrieved (host lookup failed)."

    hits = response.get('hits', {}).get('hits', [])
    if not hits:
        return "No related events found on this host in the recent window."

    candidates = [_alert_text(hit['_source']) for hit in hits]
    top_matches = await _rank_by_similarity(alert_summary, candidates, CONTEXT_TOP_K)
    return "\n".join(f"- {text}" for text in top_matches)


async def fetch_broadened_context(alert_source: dict, exclude_id: str) -> str:
    """Agent 決策後才會呼叫的擴大查詢：跨主機找相同來源 IP 或相同規則的事件。"""
    srcip = alert_source.get('data', {}).get('srcip')
    rule_id = alert_source.get('rule', {}).get('id')

    should_clauses = []
    if srcip:
        should_clauses.append({"match": {"data.srcip": srcip}})
    if rule_id:
        should_clauses.append({"match": {"rule.id": rule_id}})

    if not should_clauses:
        return "No source IP or rule ID available to broaden the search."

    try:
        response = await client.search(
            index="wazuh-alerts-*",
            body={
                "query": {
                    "bool": {
                        "should": should_clauses,
                        "minimum_should_match": 1,
                        "must": [{"range": {"timestamp": {"gte": f"now-{BROADENED_LOOKBACK_HOURS}h"}}}],
                        "must_not": [{"ids": {"values": [exclude_id]}}],
                    }
                },
                "sort": [{"timestamp": {"order": "desc"}}],
                "size": 10,
            },
        )
    except Exception as e:
        logging.warning(f"Failed to fetch broadened context: {e}")
        return "No additional context retrieved (broadened lookup failed)."

    hits = response.get('hits', {}).get('hits', [])
    if not hits:
        return "No related events found across other hosts (same source IP / rule)."

    return "\n".join(f"- {_alert_text(hit['_source'])}" for hit in hits)


def parse_decision(decision_text: str) -> bool:
    """回傳是否需要擴大查詢；解析失敗時預設為 False（避免無限迴圈/多餘呼叫）。"""
    match = re.search(r"DECISION:\s*(SUFFICIENT|NEED_MORE_CONTEXT)", decision_text, re.IGNORECASE)
    if not match:
        return False
    return match.group(1).upper() == "NEED_MORE_CONTEXT"


def parse_risk_level(report_text: str) -> str:
    match = re.search(r"RISK_LEVEL:\s*(Critical|High|Medium|Low|Informational)", report_text, re.IGNORECASE)
    return match.group(1) if match else "Unknown"


async def send_risk_notification(alert_id: str, alert_summary: str, risk_level: str, report: str):
    if not WEBHOOK_URL:
        return
    payload = {"text": f"🚨 [{risk_level}] {alert_summary}\n\n{report}\n\nAlert ID: {alert_id}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(WEBHOOK_URL, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status >= 300:
                    logging.warning(f"Webhook notification returned status {resp.status}")
    except Exception as e:
        logging.warning(f"Failed to send webhook notification: {e}")


# --- 核心工作函式 ---
async def triage_new_alerts():
    print("--- TRIAGE JOB EXECUTING NOW ---")
    logging.info(f"Analyzing alerts with {LLM_PROVIDER} model...")
    try:
        response = await client.search(index="wazuh-alerts-*", body={"query":{"bool":{"must_not":[{"exists":{"field":"ai_analysis"}}]}}}, size=10)
        alerts = response['hits']['hits']
        if not alerts:
            print("--- No new alerts found. ---")
            logging.info("No new alerts found.")
            return
        for alert in alerts:
            alert_id = alert['_id']
            alert_index = alert['_index']
            alert_source = alert['_source']
            rule = alert_source.get('rule', {})
            agent = alert_source.get('agent', {})

            alert_summary = f"Rule: {rule.get('description', 'N/A')} (Level: {rule.get('level', 'N/A')}) on Host: {agent.get('name', 'N/A')}"
            print(f"--- Found alert to process: {alert_id} ---")
            logging.info(f"Found new alert to process: {alert_id} - {alert_summary}")

            # 1. RAG: 撈同主機近期警報，用 embedding 相似度排序當作上下文
            context = await fetch_recent_host_context(agent.get('name', ''), alert_id, alert_summary)

            # 2. Agent 決策迴圈：先問 LLM 現有上下文夠不夠，不夠才觸發擴大查詢
            decision_text = await decision_chain.ainvoke({"alert_summary": alert_summary, "context": context})
            needs_more_context = parse_decision(decision_text)
            if needs_more_context:
                logging.info(f"Agent requested broadened context for alert {alert_id}")
                broadened = await fetch_broadened_context(alert_source, alert_id)
                context = f"{context}\n\nBroadened cross-host context (requested by agent):\n{broadened}"

            # 3. 最終分析
            analysis_result = await chain.ainvoke({"alert_summary": alert_summary, "context": context})
            risk_level = parse_risk_level(analysis_result)
            print(f"--- AI Analysis received: {analysis_result[:100]}... ---")
            logging.info(f"AI Analysis for {alert_id} (risk={risk_level}): {analysis_result}")

            update_body = {"doc": {"ai_analysis": {
                "triage_report": analysis_result,
                "risk_level": risk_level,
                "provider": LLM_PROVIDER,
                "used_broadened_context": needs_more_context,
                "timestamp": alert_source.get('timestamp'),
            }}}
            await client.update(index=alert_index, id=alert_id, body=update_body)
            print(f"--- Successfully updated alert {alert_id} ---")
            logging.info(f"Successfully updated alert {alert_id} with AI analysis.")

            # 4. 高風險自動通知
            if risk_level.lower() in HIGH_RISK_LEVELS:
                await send_risk_notification(alert_id, alert_summary, risk_level, analysis_result)

    except Exception as e:
        print(f"!!!!!! A CRITICAL ERROR OCCURRED IN TRIAGE JOB !!!!!!")
        logging.error(f"An error occurred during triage: {e}", exc_info=True)
        traceback.print_exc()

# --- FastAPI 應用與排程 (維持不變) ---
app = FastAPI(title="Wazuh AI Triage Agent")
scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    logging.info("AI Agent starting up...")
    scheduler.add_job(triage_new_alerts, 'interval', seconds=60, id='triage_job', misfire_grace_time=30)
    scheduler.start()
    logging.info("Scheduler started. Triage job scheduled.")

@app.get("/")
def read_root():
    return {"status": "AI Triage Agent is running", "scheduler_status": str(scheduler.get_jobs())}

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()
    logging.info("Scheduler shut down.")
