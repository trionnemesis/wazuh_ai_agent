# Wazuh Docker 單節點部署

本目錄包含 Wazuh GraphRAG 整合監控系統的單節點部署配置。

## 🚀 快速開始

### 基本 Wazuh 部署

如果您只需要基本的 Wazuh 安全平台：

1) 增加主機的 max_map_count (Linux)，需要 root 權限：
```bash
$ sysctl -w vm.max_map_count=262144
```

2) 執行憑證創建腳本：
```bash
$ docker-compose -f generate-indexer-certs.yml run --rm generator
```

3) 啟動環境：
```bash
# 前景執行
$ docker-compose up

# 背景執行
$ docker-compose up -d
```

### 完整 GraphRAG 整合堆疊

如果您需要完整的 Wazuh + AI Agent + GraphRAG + 監控解決方案，請參考：

- **詳細部署指南**: `UNIFIED_STACK_README.md`
- **統一啟動**: `./start-unified-stack.sh`
- **健康檢查**: `./health-check.sh`

## 📁 架構組件

- **Wazuh Security Platform** - SIEM 安全監控
- **AI Agent** - AgenticRAG 智慧警報分析
- **Neo4j** - GraphRAG 圖形資料庫
- **Prometheus + Grafana** - 監控與視覺化

## ⚠️ 注意事項

首次啟動約需 1 分鐘（取決於 Docker 主機效能），因為 Wazuh Indexer 需要初始化並生成索引和索引模式。

---

💡 **提示**: 對於生產環境部署，強烈建議使用 `UNIFIED_STACK_README.md` 中的完整配置。
