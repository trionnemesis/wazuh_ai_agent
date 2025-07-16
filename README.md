# Wazuh AI Agent - 智慧安全警報分析助手

本專案整合大型語言模型 (LLM)，為 [Wazuh](https://wazuh.com/) SIEM 系統自動分析安全警報，產生事件摘要、風險評估與具體建議，並將分析結果寫回警報，大幅提升安全維運效率。

---

## 專案架構

本專案採用 Docker 容器化部署，將 Wazuh SIEM 與 AI Agent 服務隔離，確保穩定與可擴充性。

### 架構圖
```
---
config:
  layout: dagre
---
flowchart TD
 subgraph subGraph0["Wazuh SIEM 核心"]
        B["Wazuh Indexer OpenSearch"]
        A["Wazuh Manager"]
        C["Wazuh Dashboard"]
  end
 subgraph subGraph1["AI 智慧分析系統"]
        D["AI Agent FastAPI + LangChain"]
        E["外部大型語言模型 Google Gemini / Anthropic Claude"]
  end
 subgraph subGraph2["Docker Host"]
        subGraph0
        subGraph1
  end
    A -- 透過 Filebeat 傳送警報 --> B
    C -- 查詢與視覺化 --> B
    D -- "1. 定期查詢新警報" --> B
    B -- "2. 回傳未分析的警報" --> D
    D -- "3. 將警報內容傳送至 LLM" --> E
    E -- "4. 回傳分析結果" --> D
    D -- "5. 將 AI 分析結果寫回警報" --> B
    Analyst["安全分析師"] -- 在儀表板查看附有 AI 註解的警報 --> C
    DataSource["日誌/事件來源"] --> A


```

### 工作流程
1. **警報生成**：Wazuh Manager 監控端點，根據規則產生警報。
2. **數據索引**：警報經 Filebeat 傳送至 Wazuh Indexer (OpenSearch)。
3. **AI Agent 介入**：
   - 定期查詢未分析警報
   - 提取警報資訊，送至 LLM API（Gemini/Claude）
   - 取得結構化分析報告（摘要、風險、建議）
   - 將分析結果寫回警報（新增 ai_analysis 欄位）
4. **視覺化**：分析師於 Dashboard 查看含 AI 分析的警報。

---

## 技術內容
| 類別       | 技術                        | 說明                                               |
|------------|-----------------------------|----------------------------------------------------|
| SIEM       | Wazuh                       | 開源安全資訊與事件管理系統                         |
| 容器化     | Docker, Docker Compose      | 打包、部署及管理所有服務                           |
| AI Agent   | FastAPI                     | Python Web 框架，建構 AI Agent API                 |
|            | LangChain                   | LLM 應用開發框架，串接 Prompt 與 LLM               |
|            | Google Gemini / Claude      | 可插拔大型語言模型                                 |
|            | OpenSearch Client           | 與 Wazuh Indexer 非同步通訊                        |
|            | APScheduler                 | Python 排程函式庫，定時觸發分析任務                |
| 安全通訊   | SSL/TLS                     | 服務間通訊皆加密                                    |

---

## 快速部署指南

### 1. 前置準備
- 安裝最新版 Docker 與 Docker Compose
- 安裝 Git
- 主機記憶體建議至少 8GB

### 2. 環境設定
#### a. 複製專案
```bash
git clone <your-repository-url>
cd wazuh-docker/single-node
```
#### b. 設定 AI Agent
- 進入 ai-agent-project 目錄，建立 .env 檔：
```bash
cd ai-agent-project
touch .env
```
- 編輯 .env，填入：
```
LLM_PROVIDER="anthropic"   # 或 gemini
GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
ANTHROPIC_API_KEY="YOUR_ANTHROPIC_API_KEY"
```
> 取得 API Key 請參考 [Google Gemini](https://ai.google.dev/) 或 [Anthropic Claude](https://console.anthropic.com/)

### 3. 部署 Wazuh 環境
#### a. 調整核心參數 (Linux)
```bash
sudo sysctl -w vm.max_map_count=262144
```
#### b. 產生安全憑證
```bash
docker-compose -f generate-indexer-certs.yml run --rm generator
```
#### c. 啟動所有服務
```bash
cd ..
docker-compose up -d
```
> 第一次啟動需等待映像檔下載與初始化

### 4. 驗證與使用
- 查看容器狀態：`docker ps`
- 登入 Dashboard：https://localhost  (預設帳密：admin / SecretPassword)
- 進入 Security Events，點選警報，應可見 `ai_analysis` 欄位

---

## 常見障礙排除 (Troubleshooting)

| 問題現象                     | 可能原因/診斷方式                                                                 | 解決方法                                                         |
|------------------------------|----------------------------------------------------------------------------------|------------------------------------------------------------------|
| 容器啟動失敗                 | 記憶體不足、參數錯誤、映像檔損壞                                                 | 檢查主機資源、重啟 Docker、重建映像檔                             |
| Wazuh Indexer 啟動錯誤       | 未調整 vm.max_map_count、SSL 憑證錯誤                                            | 重新執行 sysctl 與憑證產生指令                                   |
| AI Agent 無法連接 LLM        | .env 未填 API Key、網路不通、API Key 權限不足                                    | 檢查 .env、API Key、網路，查看 ai-agent 日誌                      |
| AI 分析欄位未出現            | 警報尚未被分析、AI Agent 未正常排程、Index 欄位權限                              | 等待 1-2 分鐘、檢查 ai-agent 日誌、確認 Index 權限                |
| Dashboard 無法登入           | 連線網址錯誤、防火牆阻擋、帳密錯誤                                               | 確認網址、檢查防火牆、使用預設帳密                                |
| OpenSearch 查詢失敗          | Indexer 未啟動、帳密錯誤、SSL 憑證問題                                           | 檢查 indexer 狀態、帳密、憑證                                     |

### 進階診斷指令
- 查看所有容器狀態：`docker ps -a`
- 查看單一容器日誌：`docker logs <container_name>`
- 進入容器：`docker exec -it <container_name> /bin/bash`
- 檢查 OpenSearch 狀態：
  ```bash
  curl -k -u admin:SecretPassword https://localhost:9200/_cat/indices?v
  ```

---

## 其他建議
- 建議提供 .env.example 範例檔
- 若需擴充 LLM，請參考 ai-agent-project/app/main.py 的 get_llm 實作
- 有任何問題請先查閱本說明與 Troubleshooting 區塊

## 未來擴充方向

1. **多模型支援與自動選擇機制**
   - 除了現有的 Gemini/Claude，可擴充支援更多 LLM（如 OpenAI GPT-4、Llama 3、Azure OpenAI 等），並根據警報類型、語言或 SLA 自動選擇最適合的模型，提升彈性與準確度。

2. **自訂化警報回應與自動化處置**
   - 結合 SOAR（Security Orchestration, Automation and Response）功能，讓 AI 分析結果可自動觸發腳本、封鎖 IP、發送通知等自動化回應，實現從偵測到處置的全自動流程。

3. **進階分析與威脅情報整合**
   - 將外部威脅情報（Threat Intelligence Feed）與歷史警報資料納入 AI 分析，提升對新型攻擊的識別能力，並可產生趨勢報告、攻擊鏈分析等進階功能，協助資安團隊預防未來威脅。

---

> 本專案由資深 AI 與 Wazuh 工程師維護，歡迎 issue/PR 與討論！

