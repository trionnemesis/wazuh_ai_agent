#!/bin/bash
# 修復並重建 AI Agent Docker 容器

echo "🔧 修復 embedding_service.py 的導入問題..."
echo "✅ 修復已完成（已添加 get_cache_service 到導入語句）"

echo ""
echo "📦 重建 Docker 映像..."
cd /workspace/wazuh-docker/single-node

# 停止現有容器
echo "🛑 停止現有容器..."
docker compose -f docker-compose.main.yml -f docker-compose.override.yml stop ai-agent

# 重建映像
echo "🏗️ 重建 AI Agent 映像..."
docker compose -f docker-compose.main.yml -f docker-compose.override.yml build ai-agent

# 啟動容器
echo "🚀 啟動 AI Agent 容器..."
docker compose -f docker-compose.main.yml -f docker-compose.override.yml up -d ai-agent

# 等待服務啟動
echo "⏳ 等待服務啟動..."
sleep 10

# 檢查服務狀態
echo "📊 檢查服務狀態..."
docker compose -f docker-compose.main.yml -f docker-compose.override.yml ps ai-agent

# 查看日誌
echo ""
echo "📝 最近的日誌："
docker compose -f docker-compose.main.yml -f docker-compose.override.yml logs --tail=50 ai-agent

echo ""
echo "✅ 完成！"