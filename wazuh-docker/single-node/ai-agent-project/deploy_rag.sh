#!/bin/bash

# RAG增強AI Agent部署腳本
# 自動部署和驗證 agenticRAG 核心功能

set -e

echo "🚀 開始部署 agenticRAG 核心檢索與關聯分析系統..."
echo "=============================================================="

# 檢查必要的環境變數
echo "📋 檢查環境變數..."

# OpenSearch 配置
export OPENSEARCH_URL=${OPENSEARCH_URL:-"https://wazuh.indexer:9200"}
export OPENSEARCH_USER=${OPENSEARCH_USER:-"admin"}
export OPENSEARCH_PASSWORD=${OPENSEARCH_PASSWORD:-"SecretPassword"}

# LLM 配置
export LLM_PROVIDER=${LLM_PROVIDER:-"anthropic"}

if [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$GEMINI_API_KEY" ]; then
    echo "❌ 錯誤: 請設定 ANTHROPIC_API_KEY 或 GEMINI_API_KEY"
    echo "   範例: export ANTHROPIC_API_KEY='your-api-key-here'"
    exit 1
fi

echo "✅ 環境變數檢查完成"
echo "   OpenSearch URL: $OPENSEARCH_URL"
echo "   LLM Provider: $LLM_PROVIDER"

# 進入專案目錄
cd "$(dirname "$0")"

# 確保 Docker 網路存在
echo "🔗 確保 Docker 網路設定..."
docker network create wazuh 2>/dev/null || echo "   wazuh 網路已存在"

# 啟動系統
echo "🐳 啟動 Docker 容器..."
docker-compose up -d

# 等待服務啟動
echo "⏳ 等待服務啟動完成..."
sleep 30

# 檢查服務健康狀態
echo "🔍 檢查服務健康狀態..."

# 檢查 AI Agent 健康狀態
echo "   檢查 AI Agent..."
for i in {1..10}; do
    if curl -s http://localhost:8000/health | grep -q "healthy"; then
        echo "   ✅ AI Agent 健康狀態良好"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "   ❌ AI Agent 健康檢查失敗"
        docker-compose logs ai-agent
        exit 1
    fi
    echo "   等待 AI Agent 啟動... ($i/10)"
    sleep 5
done

# 檢查 OpenSearch 連接
echo "   檢查 OpenSearch 連接..."
if curl -s -k -u "$OPENSEARCH_USER:$OPENSEARCH_PASSWORD" "$OPENSEARCH_URL" | grep -q "opensearch"; then
    echo "   ✅ OpenSearch 連接正常"
else
    echo "   ❌ OpenSearch 連接失敗"
    exit 1
fi

# 執行檢索模組測試
echo "🔬 執行檢索模組測試..."
docker-compose exec ai-agent python test_retrieval_module.py

# 顯示系統狀態
echo "📊 系統狀態總覽..."
echo "=============================================================="

# 顯示運行中的容器
echo "🐳 運行中的容器:"
docker-compose ps

echo ""
echo "🌐 服務端點:"
echo "   AI Agent API: http://localhost:8000"
echo "   AI Agent Health: http://localhost:8000/health"
echo "   Wazuh Dashboard: https://localhost:443"

echo ""
echo "📋 系統功能:"
echo "   ✅ 向量化警報處理"
echo "   ✅ k-NN 相似警報檢索"
echo "   ✅ 歷史上下文整合"
echo "   ✅ 增強型 AI 分析"
echo "   ✅ RAG 驅動的洞察生成"

echo ""
echo "🔍 監控命令:"
echo "   查看 AI Agent 日誌: docker-compose logs -f ai-agent"
echo "   查看所有服務日誌: docker-compose logs -f"
echo "   重啟 AI Agent: docker-compose restart ai-agent"

echo ""
echo "🎯 驗收檢查清單:"
echo "   □ 日誌中確認 k-NN 查詢執行"
echo "   □ 日誌中確認歷史上下文注入"
echo "   □ 比較分析報告品質提升"
echo "   □ 檢查檢索模組效能指標"

echo ""
echo "=============================================================="
echo "🎉 agenticRAG 核心檢索與關聯分析系統部署完成!"
echo "=============================================================="

# 顯示首次使用說明
echo ""
echo "📖 首次使用說明:"
echo "1. 系統會自動開始處理新的 Wazuh 警報"
echo "2. 每個警報都會執行向量檢索和歷史關聯分析"
echo "3. 查看日誌確認 RAG 功能正常運作"
echo "4. 對比分析報告品質是否明顯提升"
echo ""
echo "🔧 進階配置:"
echo "   調整檢索數量: 修改 main.py 中的 k 參數"
echo "   優化向量維度: 修改 embedding 服務配置"
echo "   自定義 Prompt: 編輯 prompt_template"
echo ""

# 顯示實時日誌 (可選)
read -p "是否要查看實時日誌? (y/N): " view_logs
if [[ $view_logs =~ ^[Yy]$ ]]; then
    echo "🔍 顯示實時日誌 (Ctrl+C 退出)..."
    docker-compose logs -f ai-agent
fi