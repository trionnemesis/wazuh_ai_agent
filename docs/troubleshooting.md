[← 回到 README](../README.md)

# 常見問題排除

### 服務啟動問題
| 問題症狀 | 可能原因 | 解決方案 |
|----------|----------|----------|
| `ai-agent` 容器無法啟動 | API 金鑰未設定 | 檢查 `.env` 檔案中的 API 金鑰 |
| `wazuh.indexer` 啟動失敗 | `vm.max_map_count` 過低 | 執行 `sudo sysctl -w vm.max_map_count=262144` |
| SSL 憑證錯誤 | 憑證檔案損壞 | 重新執行憑證產生命令 |
| 記憶體不足錯誤 | 系統資源不夠 | 增加 RAM 或調整 Docker 記憶體限制 |

### AI 分析問題
| 問題症狀 | 診斷方法 | 解決方案 |
|----------|----------|----------|
| 警報未被分析 | `docker logs ai-agent` | 檢查 API 金鑰、網路連線 |
| LLM API 呼叫失敗 | 查看 API 使用額度 | 確認 API 金鑰有效且有足夠額度 |
| 分析結果格式異常 | 檢查提示模板 | 調整提示模板或切換 LLM 模型 |

### 診斷指令
```bash
# 即時監控所有容器日誌
docker-compose logs -f

# 檢查特定服務狀態
docker-compose ps
docker inspect ai-agent

# 測試 OpenSearch 連線
curl -k -u admin:SecretPassword https://localhost:9200/_cat/health

# 查看未分析的警報數量
curl -k -u admin:SecretPassword \
  'https://localhost:9200/wazuh-alerts-*/_count?q=NOT%20_exists_:ai_analysis'
```
