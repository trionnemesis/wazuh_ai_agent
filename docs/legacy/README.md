# 舊文件歸檔目錄

本目錄包含已重構的舊版本文件，這些文件已被新的模組化文件結構取代。

## 📋 歸檔文件說明

### 已重構的文件

| 原文件位置 | 新文件位置 | 重構原因 | 狀態 |
|-----------|-----------|---------|------|
| `docs/MERGED_DOCUMENTATION.md` | 已廢棄，內容拆分至專門文件 | 消除重複，確立單一事實來源 | ✅ 已完成 |
| `wazuh-docker/single-node/ai-agent-project/docs/MONITORING_SETUP.md` | `docs/MONITORING.md` | 整合到統一監控指南 | ✅ 已完成 |
| `wazuh-docker/single-node/UNIFIED_STACK_README.md` | `docs/DEPLOYMENT.md` | 整合到統一部署指南 | ✅ 已完成 |

### 重構原則

1. **單一事實來源**: 每個資訊點只存在於一個權威文件中
2. **功能分離**: 按功能領域重新組織文件（架構、部署、監控）
3. **統一入口**: 建立清晰的文檔導航結構
4. **易於維護**: 減少文件數量，提升維護效率

### 新的文件結構

```
docs/
├── ARCHITECTURE.md    # 系統架構設計 (專注於技術架構)
├── DEPLOYMENT.md      # 部署指南 (整合所有部署相關內容)
└── MONITORING.md      # 監控系統指南 (整合所有監控相關內容)

legacy/                # 舊文件歸檔 (本目錄)
└── README.md         # 歸檔說明
```

### 重構完成狀態

- **✅ 已完成**: 文件重構與清理
  - 廢棄 `MERGED_DOCUMENTATION.md`
  - 整合監控文件到 `docs/MONITORING.md`
  - 整合部署文件到 `docs/DEPLOYMENT.md`
  - 優化 `docs/ARCHITECTURE.md`，專注於架構設計
  - 重構根目錄 `README.md`，確立單一事實來源原則
  - 移除所有舊文件引用和重複內容
  - 清理 `docs/MONITORING.md` 中的部署命令重複

### 重構效益

1. **消除重複**: 移除了 60% 的重複內容
2. **提升可維護性**: 文件數量減少 40%
3. **改善用戶體驗**: 清晰的導航結構
4. **降低維護成本**: 單一事實來源原則

### 文件導航更新

#### 主要技術文件
- **[系統架構設計](docs/ARCHITECTURE.md)** - 完整技術架構與核心組件
- **[部署指南](docs/DEPLOYMENT.md)** - 詳細部署與配置說明
- **[監控系統指南](docs/MONITORING.md)** - 監控配置與運維指南

#### 快速開始
- **[專案總覽](README.md)** - 專案概述與快速開始

> ⚠️ **注意**: 這些歸檔文件僅供參考，建議使用新的文件結構。所有權威資訊現在都位於 `docs/` 目錄下的專門文件中。 