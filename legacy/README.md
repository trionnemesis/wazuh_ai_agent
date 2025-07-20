# 舊文件歸檔目錄

本目錄包含已重構的舊版本文件，這些文件已被新的模組化文件結構取代。

## 📋 歸檔文件說明

### 已重構的文件

| 原文件位置 | 新文件位置 | 重構原因 |
|-----------|-----------|---------|
| `wazuh-docker/single-node/UNIFIED_STACK_README.md` | `docs/DEPLOYMENT.md` | 整合到統一部署指南 |
| `wazuh-docker/single-node/ai-agent-project/docs/MONITORING_SETUP.md` | `docs/MONITORING.md` | 整合到統一監控指南 |
| `MERGED_DOCUMENTATION.md` (部分內容) | `docs/ARCHITECTURE.md` | 架構內容分離 |

### 重構原則

1. **消除重複**: 移除多個文件中的重複內容
2. **功能分離**: 按功能領域重新組織文件
3. **統一入口**: 建立清晰的文檔導航結構
4. **易於維護**: 減少文件數量，提升維護效率

### 新的文件結構

```
docs/
├── ARCHITECTURE.md    # 系統架構設計
├── DEPLOYMENT.md      # 部署指南
└── MONITORING.md      # 監控系統指南

legacy/                # 舊文件歸檔 (本目錄)
└── README.md         # 歸檔說明
```

### 遷移時間表

- **2024年12月**: 完成文件重構
- **2025年1月**: 移除舊文件引用
- **2025年2月**: 清理歸檔目錄

> ⚠️ **注意**: 這些歸檔文件僅供參考，建議使用新的文件結構。 