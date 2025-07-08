# Wazuh AI Agent - 智慧安全警報分析助手

本專案旨在透過整合大型語言模型 (LLM)，為 [Wazuh](https://wazuh.com/) SIEM 系統賦予智慧化的自動警報分析能力。當 Wazuh 產生新的安全警報時，AI Agent 將自動對其進行分析，產出簡潔的事件摘要、風險評估和具體應對建議，並將這些資訊寫回警報中，大幅提升安全維運團隊的分析效率與反應速度。

## 專案架構

本專案採用容器化技術 (Docker) 進行部署，將 Wazuh 核心元件與 AI Agent 服務完全隔離，確保系統的穩定性與可擴充性。整體架構分為兩大部分：**Wazuh SIEM** 和 **AI Triage System**。

### 架構圖

```mermaid
graph TD
    subgraph "Docker Host"
        subgraph "Wazuh SIEM 核心"
            A[Wazuh Manager] -->|透過 Filebeat 傳送警報| B[Wazuh Indexer <br>(OpenSearch)];
            C[Wazuh Dashboard] -->|查詢與視覺化| B;
        end
        subgraph "AI 智慧分析系統"
            D[AI Agent <br>(FastAPI + LangChain)] -- "1. 定期查詢新警報" --> B;
            B -- "2. 回傳未分析的警報" --> D;
            D -- "3. 將警報內容傳送至 LLM" --> E[外部大型語言模型 <br>(Google Gemini / Anthropic Claude)];
            E -- "4. 回傳分析結果" --> D;
            D -- "5. 將 AI 分析結果寫回警報" --> B;
        end
    end
    Analyst[安全分析師] -->|在儀表板查看<br>附有 AI 註解的警報| C;
    DataSource[日誌/事件來源] --> A;
好的，這裏是您可以直接複製使用的完整 README.md 檔案內容：

Markdown

# Wazuh AI Agent - 智慧安全警報分析助手

本專案旨在透過整合大型語言模型 (LLM)，為 [Wazuh](https://wazuh.com/) SIEM 系統賦予智慧化的自動警報分析能力。當 Wazuh 產生新的安全警報時，AI Agent 將自動對其進行分析，產出簡潔的事件摘要、風險評估和具體應對建議，並將這些資訊寫回警報中，大幅提升安全維運團隊的分析效率與反應速度。

## 專案架構

本專案採用容器化技術 (Docker) 進行部署，將 Wazuh 核心元件與 AI Agent 服務完全隔離，確保系統的穩定性與可擴充性。整體架構分為兩大部分：**Wazuh SIEM** 和 **AI Triage System**。

### 架構圖

```mermaid
graph TD
    subgraph "Docker Host"
        subgraph "Wazuh SIEM 核心"
            A[Wazuh Manager] -->|透過 Filebeat 傳送警報| B[Wazuh Indexer <br>(OpenSearch)];
            C[Wazuh Dashboard] -->|查詢與視覺化| B;
        end
        subgraph "AI 智慧分析系統"
            D[AI Agent <br>(FastAPI + LangChain)] -- "1. 定期查詢新警報" --> B;
            B -- "2. 回傳未分析的警報" --> D;
            D -- "3. 將警報內容傳送至 LLM" --> E[外部大型語言模型 <br>(Google Gemini / Anthropic Claude)];
            E -- "4. 回傳分析結果" --> D;
            D -- "5. 將 AI 分析結果寫回警報" --> B;
        end
    end
    Analyst[安全分析師] -->|在儀表板查看<br>附有 AI 註解的警報| C;
    DataSource[日誌/事件來源] --> A;

工作流程說明
警報生成: Wazuh Manager 監控端點，分析日誌並根據規則生成安全警報。

數據索引: 警報透過 Filebeat 傳送到 Wazuh Indexer (基於 OpenSearch) 進行儲存和索引。

AI Agent 介入:

AI Agent 服務會定期 (預設每 60 秒) 向 Wazuh Indexer 查詢是否有尚未被 AI 分析過的新警報。

一旦發現新警報，AI Agent 會提取其核心資訊（如規則描述、主機名稱等）。

使用 LangChain 框架，將警報資訊套用至預設的 Prompt Template，並呼叫外部的 LLM API (支援 Google Gemini 和 Anthropic Claude)。

LLM 會根據提示詞，回傳一份結構化的分析報告，包含：事件摘要、風險等級和下一步建議。

警報豐富化: AI Agent 將收到的分析報告寫回 Wazuh Indexer 中對應的警報文件內，新增一個名為 ai_analysis 的欄位。

視覺化呈現: 安全分析師可以透過 Wazuh Dashboard 查看警報，此時警報中已包含由 AI 提供的寶貴分析見解，無需再手動進行初步研判。

類別	技術	說明				
SIEM	Wazuh	一套開源的安全資訊與事件管理系統，包含 Manager、Indexer 和 Dashboard。				
容器化	Docker, Docker Compose	用於打包、部署及管理本專案所有服務。				
AI Agent	FastAPI	高效能的 Python Web 框架，用於建立 AI Agent 的 API 服務。				
	LangChain	領先的 LLM 應用開發框架，用於串接 Prompt、LLM 和輸出解析。				
	Google Gemini / Anthropic Claude	可插拔的大型語言模型，提供核心的自然語言分析能力。				
	OpenSearch Client	用於與 Wazuh Indexer 進行非同步的資料庫通訊。				
	APScheduler	一個 Python 排程函式庫，用於定時觸發警報分析任務。				
安全通訊	SSL/TLS	所有內部服務間的通訊 (如 Dashboard 到 Indexer) 均使用自簽署憑證進行加密。				

好的，這裏是您可以直接複製使用的完整 README.md 檔案內容：

Markdown

# Wazuh AI Agent - 智慧安全警報分析助手

本專案旨在透過整合大型語言模型 (LLM)，為 [Wazuh](https://wazuh.com/) SIEM 系統賦予智慧化的自動警報分析能力。當 Wazuh 產生新的安全警報時，AI Agent 將自動對其進行分析，產出簡潔的事件摘要、風險評估和具體應對建議，並將這些資訊寫回警報中，大幅提升安全維運團隊的分析效率與反應速度。

## 專案架構

本專案採用容器化技術 (Docker) 進行部署，將 Wazuh 核心元件與 AI Agent 服務完全隔離，確保系統的穩定性與可擴充性。整體架構分為兩大部分：**Wazuh SIEM** 和 **AI Triage System**。

### 架構圖

```mermaid
graph TD
    subgraph "Docker Host"
        subgraph "Wazuh SIEM 核心"
            A[Wazuh Manager] -->|透過 Filebeat 傳送警報| B[Wazuh Indexer <br>(OpenSearch)];
            C[Wazuh Dashboard] -->|查詢與視覺化| B;
        end
        subgraph "AI 智慧分析系統"
            D[AI Agent <br>(FastAPI + LangChain)] -- "1. 定期查詢新警報" --> B;
            B -- "2. 回傳未分析的警報" --> D;
            D -- "3. 將警報內容傳送至 LLM" --> E[外部大型語言模型 <br>(Google Gemini / Anthropic Claude)];
            E -- "4. 回傳分析結果" --> D;
            D -- "5. 將 AI 分析結果寫回警報" --> B;
        end
    end
    Analyst[安全分析師] -->|在儀表板查看<br>附有 AI 註解的警報| C;
    DataSource[日誌/事件來源] --> A;

工作流程說明
警報生成: Wazuh Manager 監控端點，分析日誌並根據規則生成安全警報。

數據索引: 警報透過 Filebeat 傳送到 Wazuh Indexer (基於 OpenSearch) 進行儲存和索引。

AI Agent 介入:

AI Agent 服務會定期 (預設每 60 秒) 向 Wazuh Indexer 查詢是否有尚未被 AI 分析過的新警報。

一旦發現新警報，AI Agent 會提取其核心資訊（如規則描述、主機名稱等）。

使用 LangChain 框架，將警報資訊套用至預設的 Prompt Template，並呼叫外部的 LLM API (支援 Google Gemini 和 Anthropic Claude)。

LLM 會根據提示詞，回傳一份結構化的分析報告，包含：事件摘要、風險等級和下一步建議。

警報豐富化: AI Agent 將收到的分析報告寫回 Wazuh Indexer 中對應的警報文件內，新增一個名為 ai_analysis 的欄位。

視覺化呈現: 安全分析師可以透過 Wazuh Dashboard 查看警報，此時警報中已包含由 AI 提供的寶貴分析見解，無需再手動進行初步研判。

技術棧
類別

技術

說明

SIEM

Wazuh

一套開源的安全資訊與事件管理系統，包含 Manager、Indexer 和 Dashboard。

容器化

Docker, Docker Compose

用於打包、部署及管理本專案所有服務。

AI Agent

FastAPI

高效能的 Python Web 框架，用於建立 AI Agent 的 API 服務。

LangChain

領先的 LLM 應用開發框架，用於串接 Prompt、LLM 和輸出解析。

Google Gemini / Anthropic Claude

可插拔的大型語言模型，提供核心的自然語言分析能力。

OpenSearch Client

用於與 Wazuh Indexer 進行非同步的資料庫通訊。

APScheduler

一個 Python 排程函式庫，用於定時觸發警報分析任務。

安全通訊

SSL/TLS

所有內部服務間的通訊 (如 Dashboard 到 Indexer) 均使用自簽署憑證進行加密。


匯出到試算表
使用方式
請依照以下步驟來部署並啟動完整的 Wazuh AI Agent 環境。

1. 前置準備
確認您的主機已安裝最新版的 Docker 與 Docker Compose。

安裝 Git 用於複製本專案。

確保主機有足夠的記憶體 (建議至少 8GB)。

2. 環境設定
a. 複製專案
git clone <your-repository-url>
cd wazuh-docker/single-node


b. 設定 AI Agent

您需要設定要使用的 LLM 供應商及對應的 API 金鑰。

首先，進入 ai-agent-project 目錄，並建立一個 .env 檔案：
cd ai-agent-project
touch .env

# .env

# 指定要使用的 LLM 供應商，可選 'gemini' 或 'anthropic'
LLM_PROVIDER="anthropic"

# 如果使用 Google Gemini，請填寫您的 API Key
GEMINI_API_KEY="YOUR_GEMINI_API_KEY"

# 如果使用 Anthropic Claude，請填寫您的 API Key
ANTHROPIC_API_KEY="YOUR_ANTHROPIC_API_KEY"

3. 部署 Wazuh 環境
a. 調整核心參數 (Linux)

為了讓 Wazuh Indexer (OpenSearch) 正常運作，需要調整作業系統的虛擬記憶體對應數量。此指令需要 root 權限。

sudo sysctl -w vm.max_map_count=262144
b. 產生安全憑證

執行以下指令來產生服務間通訊所需的 SSL 憑證。
docker-compose -f generate-indexer-certs.yml run --rm generator
cd ..
docker-compose up -d
好的，這裏是您可以直接複製使用的完整 README.md 檔案內容：

Markdown

# Wazuh AI Agent - 智慧安全警報分析助手

本專案旨在透過整合大型語言模型 (LLM)，為 [Wazuh](https://wazuh.com/) SIEM 系統賦予智慧化的自動警報分析能力。當 Wazuh 產生新的安全警報時，AI Agent 將自動對其進行分析，產出簡潔的事件摘要、風險評估和具體應對建議，並將這些資訊寫回警報中，大幅提升安全維運團隊的分析效率與反應速度。

## 專案架構

本專案採用容器化技術 (Docker) 進行部署，將 Wazuh 核心元件與 AI Agent 服務完全隔離，確保系統的穩定性與可擴充性。整體架構分為兩大部分：**Wazuh SIEM** 和 **AI Triage System**。

### 架構圖

```mermaid
graph TD
    subgraph "Docker Host"
        subgraph "Wazuh SIEM 核心"
            A[Wazuh Manager] -->|透過 Filebeat 傳送警報| B[Wazuh Indexer <br>(OpenSearch)];
            C[Wazuh Dashboard] -->|查詢與視覺化| B;
        end
        subgraph "AI 智慧分析系統"
            D[AI Agent <br>(FastAPI + LangChain)] -- "1. 定期查詢新警報" --> B;
            B -- "2. 回傳未分析的警報" --> D;
            D -- "3. 將警報內容傳送至 LLM" --> E[外部大型語言模型 <br>(Google Gemini / Anthropic Claude)];
            E -- "4. 回傳分析結果" --> D;
            D -- "5. 將 AI 分析結果寫回警報" --> B;
        end
    end
    Analyst[安全分析師] -->|在儀表板查看<br>附有 AI 註解的警報| C;
    DataSource[日誌/事件來源] --> A;

工作流程說明
警報生成: Wazuh Manager 監控端點，分析日誌並根據規則生成安全警報。

數據索引: 警報透過 Filebeat 傳送到 Wazuh Indexer (基於 OpenSearch) 進行儲存和索引。

AI Agent 介入:

AI Agent 服務會定期 (預設每 60 秒) 向 Wazuh Indexer 查詢是否有尚未被 AI 分析過的新警報。

一旦發現新警報，AI Agent 會提取其核心資訊（如規則描述、主機名稱等）。

使用 LangChain 框架，將警報資訊套用至預設的 Prompt Template，並呼叫外部的 LLM API (支援 Google Gemini 和 Anthropic Claude)。

LLM 會根據提示詞，回傳一份結構化的分析報告，包含：事件摘要、風險等級和下一步建議。

警報豐富化: AI Agent 將收到的分析報告寫回 Wazuh Indexer 中對應的警報文件內，新增一個名為 ai_analysis 的欄位。

視覺化呈現: 安全分析師可以透過 Wazuh Dashboard 查看警報，此時警報中已包含由 AI 提供的寶貴分析見解，無需再手動進行初步研判。

技術棧
類別

技術

說明

SIEM

Wazuh

一套開源的安全資訊與事件管理系統，包含 Manager、Indexer 和 Dashboard。

容器化

Docker, Docker Compose

用於打包、部署及管理本專案所有服務。

AI Agent

FastAPI

高效能的 Python Web 框架，用於建立 AI Agent 的 API 服務。

LangChain

領先的 LLM 應用開發框架，用於串接 Prompt、LLM 和輸出解析。

Google Gemini / Anthropic Claude

可插拔的大型語言模型，提供核心的自然語言分析能力。

OpenSearch Client

用於與 Wazuh Indexer 進行非同步的資料庫通訊。

APScheduler

一個 Python 排程函式庫，用於定時觸發警報分析任務。

安全通訊

SSL/TLS

所有內部服務間的通訊 (如 Dashboard 到 Indexer) 均使用自簽署憑證進行加密。


匯出到試算表
使用方式
請依照以下步驟來部署並啟動完整的 Wazuh AI Agent 環境。

1. 前置準備
確認您的主機已安裝最新版的 Docker 與 Docker Compose。

安裝 Git 用於複製本專案。

確保主機有足夠的記憶體 (建議至少 8GB)。

2. 環境設定
a. 複製專案

Bash

git clone <your-repository-url>
cd wazuh-docker/single-node
b. 設定 AI Agent

您需要設定要使用的 LLM 供應商及對應的 API 金鑰。

首先，進入 ai-agent-project 目錄，並建立一個 .env 檔案：

Bash

cd ai-agent-project
touch .env
接著，編輯 .env 檔案，並填入以下內容。請務必根據您選擇的 LLM 供應商填寫對應的 API 金鑰。

程式碼片段

# .env

# 指定要使用的 LLM 供應商，可選 'gemini' 或 'anthropic'
LLM_PROVIDER="anthropic"

# 如果使用 Google Gemini，請填寫您的 API Key
GEMINI_API_KEY="YOUR_GEMINI_API_KEY"

# 如果使用 Anthropic Claude，請填寫您的 API Key
ANTHROPIC_API_KEY="YOUR_ANTHROPIC_API_KEY"
3. 部署 Wazuh 環境
a. 調整核心參數 (Linux)

為了讓 Wazuh Indexer (OpenSearch) 正常運作，需要調整作業系統的虛擬記憶體對應數量。此指令需要 root 權限。

Bash

sudo sysctl -w vm.max_map_count=262144
b. 產生安全憑證

執行以下指令來產生服務間通訊所需的 SSL 憑證。

Bash

docker-compose -f generate-indexer-certs.yml run --rm generator
c. 啟動所有服務

回到 single-node 目錄，使用 docker-compose 啟動所有服務 (包含 Wazuh 和 AI Agent)。-d 參數會讓服務在背景執行。

Bash

cd ..
docker-compose up -d
第一次啟動會需要一些時間下載映像檔並進行初始化。

4. 驗證與使用
a. 確認服務狀態

執行 docker ps 來查看所有容器是否都正常運行，您應該會看到 wazuh.manager, wazuh.indexer, wazuh.dashboard, 和 ai-agent 等容器。

b. 登入 Wazuh Dashboard

開啟瀏覽器，前往 https://localhost。

預設登入帳號：admin

預設登入密碼：SecretPassword

c. 查看 AI 分析結果

等待幾分鐘，讓系統生成一些警報並讓 AI Agent 有時間處理。

在 Wazuh Dashboard 中，點擊左側選單進入 Security Events。

隨機點開一則警報，查看其詳細資訊 (JSON 格式)。

如果 AI Agent 已成功處理該警報，您會看到一個名為 ai_analysis 的新欄位，其中包含了 triage_report。

AI 分析欄位範例：
"ai_analysis": {
  "triage_report": "Your Triage Report:\n1. **Event Summary:** An attempt was made to log in to the host 'wazuh.manager' as user 'root' from the IP address '172.19.0.1', but it failed due to an incorrect password.\n2. **Potential Risk Level:** Medium\n3. **Recommendation:** Investigate the source IP '172.19.0.1' to determine if it is a known malicious actor. Consider blocking the IP at the firewall if the activity is deemed hostile.",
  "provider": "anthropic",
  "timestamp": "2024-05-23T08:15:30.123Z"
}

c. 啟動所有服務

回到 single-node 目錄，使用 docker-compose 啟動所有服務 (包含 Wazuh 和 AI Agent)。-d 參數會讓服務在背景執行。

