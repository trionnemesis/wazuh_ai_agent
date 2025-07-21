# 📚 Wazuh GraphRAG 專案文件目錄

**最後更新**: 2024年12月  
**文件版本**: 1.0.0  

---

## 📋 文件分類體系

### 🏛️ 核心架構文件

#### [系統架構設計](ARCHITECTURE.md)
- **類別**: 技術架構
- **對象**: 架構師、技術主管、資深工程師
- **內容**: 
  - 系統整體架構設計
  - 核心組件說明
  - 技術選型決策
  - 六階段演進路線圖
  - GraphRAG 實施細節

#### [部署指南](DEPLOYMENT.md)
- **類別**: 部署運維
- **對象**: DevOps 工程師、系統管理員
- **內容**:
  - 環境需求說明
  - 詳細部署步驟
  - 配置參數說明
  - 故障排除指南
  - 效能調優建議

#### [監控系統指南](MONITORING.md)
- **類別**: 運維監控
- **對象**: 運維工程師、SRE
- **內容**:
  - Prometheus 監控配置
  - Grafana 儀表板設置
  - 警報規則定義
  - 效能指標說明
  - 日誌分析指南

---

### 🔄 重構與優化報告

#### [模組化重構總結](REFACTORING_SUMMARY.md)
- **類別**: 架構重構
- **對象**: 技術團隊、專案經理
- **內容**:
  - 重構前後架構對比
  - 模組化設計原則
  - 服務層實施細節
  - 重構成果評估

#### [清理完成報告](CLEANUP_COMPLETION_REPORT.md)
- **類別**: 程式碼優化
- **對象**: 開發團隊
- **內容**:
  - 程式碼清理範圍
  - 優化項目清單
  - 程式碼品質提升
  - 技術債務清理

#### [智能快取實作報告](INTELLIGENT_CACHING_IMPLEMENTATION.md)
- **類別**: 效能優化
- **對象**: 開發工程師、架構師
- **內容**:
  - 快取架構設計
  - 實作細節說明
  - 效能測試結果
  - 最佳實踐建議

---

### 🧪 測試與品質文件

#### [測試策略文件](TESTING_STRATEGY.md)
- **類別**: 測試規劃
- **對象**: 測試工程師、QA 團隊
- **內容**:
  - 測試層級設計
  - 測試案例規劃
  - 測試環境配置
  - 測試最佳實踐

#### [測試優化報告](TESTING_OPTIMIZATION_REPORT.md)
- **類別**: 測試改進
- **對象**: 測試團隊、開發團隊
- **內容**:
  - 測試流程優化
  - 測試效率提升
  - 自動化測試實施
  - 測試覆蓋率分析

---

### 🤖 自動化與持續整合

#### [自動化優化報告](AUTOMATION_OPTIMIZATION_REPORT.md)
- **類別**: CI/CD 優化
- **對象**: DevOps 團隊
- **內容**:
  - CI/CD 流程設計
  - 自動化腳本實施
  - 構建優化策略
  - 部署自動化改進

---

### 📊 專案報告索引

#### [專案報告總覽](PROJECT_REPORTS.md)
- **類別**: 報告索引
- **對象**: 所有團隊成員
- **內容**:
  - 所有報告快速索引
  - 專案里程碑總結
  - 報告使用指南

---

## 🗂️ 文件使用指引

### 按角色查找

**架構師/技術主管**
1. 首先閱讀 [系統架構設計](ARCHITECTURE.md)
2. 查看 [模組化重構總結](REFACTORING_SUMMARY.md)
3. 了解 [專案報告總覽](PROJECT_REPORTS.md)

**開發工程師**
1. 查看 [系統架構設計](ARCHITECTURE.md) 的技術實施章節
2. 閱讀 [測試策略文件](TESTING_STRATEGY.md)
3. 參考 [清理完成報告](CLEANUP_COMPLETION_REPORT.md)

**DevOps/運維工程師**
1. 詳讀 [部署指南](DEPLOYMENT.md)
2. 配置 [監控系統指南](MONITORING.md)
3. 查看 [自動化優化報告](AUTOMATION_OPTIMIZATION_REPORT.md)

**測試工程師**
1. 深入 [測試策略文件](TESTING_STRATEGY.md)
2. 參考 [測試優化報告](TESTING_OPTIMIZATION_REPORT.md)

**專案經理**
1. 查看 [專案報告總覽](PROJECT_REPORTS.md)
2. 了解各階段完成報告

---

## 📝 文件維護說明

### 更新頻率
- **架構文件**: 重大變更時更新
- **部署指南**: 每個版本發布前檢查更新
- **監控指南**: 新增監控項目時更新
- **報告文件**: 階段性任務完成時生成

### 版本控制
- 所有文件納入 Git 版本控制
- 重大更新需記錄在文件頭部的更新日誌
- 使用語意化版本號管理文件版本

### 文件標準
- 使用 Markdown 格式
- 保持結構清晰、層次分明
- 包含目錄導航
- 提供實用範例

---

## 🔗 外部參考資源

- [Wazuh 官方文檔](https://documentation.wazuh.com/)
- [Neo4j 圖資料庫文檔](https://neo4j.com/docs/)
- [OpenSearch 向量搜索指南](https://opensearch.org/docs/latest/search-plugins/knn/)
- [GraphRAG 概念說明](https://github.com/microsoft/graphrag)

---

## 📮 文件反饋

如發現文件錯誤或有改進建議，請：
1. 在 GitHub 開啟 Issue
2. 標記為 `documentation`
3. 詳細說明問題或建議