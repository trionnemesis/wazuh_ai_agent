#!/bin/bash
# 重建 AI Agent 容器（異步版本）

echo "🧹 開始清理和重建 AI Agent 容器..."

# 切換到正確的目錄
cd "$(dirname "$0")/.." || exit 1

# 停止現有容器
echo "⏹️ 停止現有容器..."
docker-compose -f docker-compose.main.yml stop ai-agent

# 刪除舊容器
echo "🗑️ 刪除舊容器..."
docker-compose -f docker-compose.main.yml rm -f ai-agent

# 清理 Docker 映像緩存
echo "🧹 清理 Docker 映像緩存..."
docker images | grep "single-node.*ai-agent" | awk '{print $3}' | xargs -r docker rmi -f

# 清理構建緩存
echo "🧹 清理構建緩存..."
docker builder prune -f

# 重新構建映像（無緩存）
echo "🔨 重新構建映像（無緩存）..."
docker-compose -f docker-compose.main.yml build --no-cache ai-agent

# 啟動新容器
echo "🚀 啟動新容器..."
docker-compose -f docker-compose.main.yml up -d ai-agent

# 等待容器啟動
echo "⏳ 等待容器啟動..."
sleep 10

# 檢查容器狀態
echo "🔍 檢查容器狀態..."
docker-compose -f docker-compose.main.yml ps ai-agent

# 顯示最新日誌
echo "📋 顯示最新日誌..."
docker-compose -f docker-compose.main.yml logs --tail=50 ai-agent

echo "✅ 重建完成！"
echo ""
echo "使用以下命令查看實時日誌："
echo "  docker-compose -f docker-compose.main.yml logs -f ai-agent"
echo ""
echo "檢查健康狀態："
echo "  curl http://localhost:8000/health"