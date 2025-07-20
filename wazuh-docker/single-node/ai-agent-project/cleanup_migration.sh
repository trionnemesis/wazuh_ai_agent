#!/bin/bash
# 清理遷移後的舊檔案
# 此腳本將在確認新架構正常運作後執行

echo "🧹 開始清理遷移後的舊檔案..."

# 確認當前目錄
if [ ! -f "app/main_new.py" ]; then
    echo "❌ 錯誤：請在 ai-agent-project 目錄下執行此腳本"
    exit 1
fi

# 檢查新架構是否就緒
if [ ! -d "app/core" ] || [ ! -d "app/services" ] || [ ! -d "app/api" ]; then
    echo "❌ 錯誤：新的模組化架構尚未完全建立"
    exit 1
fi

echo "📋 準備刪除以下檔案："
echo "   - app/main.py (舊的主程式)"
echo "   - app/migrate_to_modular.py (遷移工具)"

read -p "確定要刪除這些檔案嗎？(y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 取消操作"
    exit 0
fi

# 備份舊檔案（以防萬一）
echo "📦 創建備份..."
mkdir -p backup/$(date +%Y%m%d_%H%M%S)
cp app/main.py backup/$(date +%Y%m%d_%H%M%S)/ 2>/dev/null
cp app/migrate_to_modular.py backup/$(date +%Y%m%d_%H%M%S)/ 2>/dev/null

# 刪除舊檔案
echo "🗑️ 刪除舊檔案..."
rm -f app/main.py
rm -f app/migrate_to_modular.py

echo "✅ 清理完成！"
echo ""
echo "📝 下一步："
echo "   1. 確認所有服務都使用 main_new.py"
echo "   2. 執行完整的功能測試"
echo "   3. 更新所有相關文件"

# 檢查是否還有其他引用
echo ""
echo "🔍 檢查剩餘的 main.py 引用..."
grep -r "from main import\|import main" app/ tests/ 2>/dev/null | grep -v "__pycache__" | head -10
if [ $? -eq 0 ]; then
    echo ""
    echo "⚠️  警告：發現上述檔案仍在引用 main.py"
    echo "   請更新這些引用以使用新的模組化架構"
fi