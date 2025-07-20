#!/bin/bash

# Wazuh GraphRAG 重複檔案清理腳本
# 版本: 1.0
# 描述: 安全地刪除重複檔案並重新組織目錄結構
# 作者: AgenticRAG & GraphRAG 架構工程師
# 更新日期: 2024-12

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 備份目錄
BACKUP_DIR="backup/$(date +%Y%m%d_%H%M%S)"

# 顯示幫助信息
show_help() {
    echo -e "${BLUE}Wazuh GraphRAG 重複檔案清理腳本${NC}"
    echo ""
    echo "用法: $0 [選項]"
    echo ""
    echo "選項:"
    echo "  --dry-run    僅顯示將要執行的操作，不實際執行"
    echo "  --backup     創建備份後再刪除 (預設)"
    echo "  --force      直接刪除，不創建備份"
    echo "  --help       顯示此幫助信息"
    echo ""
    echo "範例:"
    echo "  $0 --dry-run    # 預覽清理操作"
    echo "  $0 --backup     # 備份後清理"
    echo "  $0 --force      # 直接清理"
    echo ""
}

# 解析命令行參數
DRY_RUN=false
FORCE=false
BACKUP=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            BACKUP=false
            shift
            ;;
        --backup)
            BACKUP=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}錯誤: 未知參數 $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# 要刪除的檔案列表
FILES_TO_DELETE=(
    "wazuh-docker/single-node/docker-compose.yml"
    "wazuh-docker/single-node/ai-agent-project/config/docker-compose.monitoring.yml"
    "wazuh-docker/single-node/ai-agent-project/config/docker-compose.neo4j.yml"
    "wazuh-docker/single-node/UNIFIED_STACK_README.md"
)

# 要移動的檔案列表
FILES_TO_MOVE=(
    "wazuh-docker/single-node/ai-agent-project/config/prometheus.yml:wazuh-docker/single-node/config/monitoring/"
    "wazuh-docker/single-node/ai-agent-project/grafana/:wazuh-docker/single-node/config/monitoring/"
)

# 創建備份目錄
create_backup() {
    if [ "$BACKUP" = true ]; then
        echo -e "${BLUE}創建備份目錄: ${BACKUP_DIR}${NC}"
        
        if [ "$DRY_RUN" = false ]; then
            mkdir -p "$BACKUP_DIR"
        fi
        
        # 備份要刪除的檔案
        for file in "${FILES_TO_DELETE[@]}"; do
            if [ -f "$file" ] || [ -d "$file" ]; then
                echo -e "${YELLOW}備份: $file${NC}"
                if [ "$DRY_RUN" = false ]; then
                    mkdir -p "$(dirname "$BACKUP_DIR/$file")"
                    cp -r "$file" "$BACKUP_DIR/$file" 2>/dev/null || true
                fi
            fi
        done
        
        # 備份要移動的檔案
        for move_item in "${FILES_TO_MOVE[@]}"; do
            IFS=':' read -r source dest <<< "$move_item"
            if [ -f "$source" ] || [ -d "$source" ]; then
                echo -e "${YELLOW}備份: $source${NC}"
                if [ "$DRY_RUN" = false ]; then
                    mkdir -p "$(dirname "$BACKUP_DIR/$source")"
                    cp -r "$source" "$BACKUP_DIR/$source" 2>/dev/null || true
                fi
            fi
        done
        
        echo -e "${GREEN}✓ 備份完成${NC}"
    fi
}

# 刪除重複檔案
delete_duplicates() {
    echo -e "${BLUE}刪除重複檔案...${NC}"
    
    for file in "${FILES_TO_DELETE[@]}"; do
        if [ -f "$file" ] || [ -d "$file" ]; then
            if [ "$DRY_RUN" = true ]; then
                echo -e "${YELLOW}[DRY-RUN] 將刪除: $file${NC}"
            else
                echo -e "${YELLOW}刪除: $file${NC}"
                rm -rf "$file"
            fi
        else
            echo -e "${YELLOW}檔案不存在，跳過: $file${NC}"
        fi
    done
    
    echo -e "${GREEN}✓ 重複檔案刪除完成${NC}"
}

# 移動檔案到統一位置
move_files() {
    echo -e "${BLUE}移動檔案到統一位置...${NC}"
    
    # 創建目標目錄
    if [ "$DRY_RUN" = false ]; then
        mkdir -p "wazuh-docker/single-node/config/monitoring"
    fi
    
    for move_item in "${FILES_TO_MOVE[@]}"; do
        IFS=':' read -r source dest <<< "$move_item"
        
        if [ -f "$source" ] || [ -d "$source" ]; then
            if [ "$DRY_RUN" = true ]; then
                echo -e "${YELLOW}[DRY-RUN] 將移動: $source -> $dest${NC}"
            else
                echo -e "${YELLOW}移動: $source -> $dest${NC}"
                mv "$source" "$dest"
            fi
        else
            echo -e "${YELLOW}檔案不存在，跳過: $source${NC}"
        fi
    done
    
    echo -e "${GREEN}✓ 檔案移動完成${NC}"
}

# 更新 Docker Compose 引用
update_references() {
    echo -e "${BLUE}更新 Docker Compose 引用...${NC}"
    
    local compose_file="wazuh-docker/single-node/docker-compose.main.yml"
    
    if [ -f "$compose_file" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${YELLOW}[DRY-RUN] 將更新: $compose_file${NC}"
            echo -e "${YELLOW}[DRY-RUN] 更新 prometheus.yml 路徑引用${NC}"
        else
            echo -e "${YELLOW}更新: $compose_file${NC}"
            # 更新 prometheus.yml 路徑
            sed -i.bak 's|./ai-agent-project/prometheus.yml|./config/monitoring/prometheus.yml|g' "$compose_file"
            rm -f "${compose_file}.bak"
        fi
    fi
    
    echo -e "${GREEN}✓ 引用更新完成${NC}"
}

# 驗證清理結果
verify_cleanup() {
    echo -e "${BLUE}驗證清理結果...${NC}"
    
    local errors=0
    
    # 檢查是否還有重複檔案
    for file in "${FILES_TO_DELETE[@]}"; do
        if [ -f "$file" ] || [ -d "$file" ]; then
            echo -e "${RED}錯誤: 檔案仍然存在: $file${NC}"
            ((errors++))
        fi
    done
    
    # 檢查移動的檔案是否在新位置
    for move_item in "${FILES_TO_MOVE[@]}"; do
        IFS=':' read -r source dest <<< "$move_item"
        local filename=$(basename "$source")
        local new_path="$dest$filename"
        
        if [ ! -f "$new_path" ] && [ ! -d "$new_path" ]; then
            echo -e "${RED}錯誤: 檔案未正確移動: $new_path${NC}"
            ((errors++))
        fi
    done
    
    if [ $errors -eq 0 ]; then
        echo -e "${GREEN}✓ 清理驗證通過${NC}"
    else
        echo -e "${RED}✗ 清理驗證失敗，發現 $errors 個錯誤${NC}"
        return 1
    fi
}

# 顯示清理摘要
show_summary() {
    echo ""
    echo -e "${BLUE}=== 清理摘要 ===${NC}"
    echo -e "執行模式: ${YELLOW}$([ "$DRY_RUN" = true ] && echo "DRY-RUN" || echo "實際執行")${NC}"
    echo -e "備份模式: ${YELLOW}$([ "$BACKUP" = true ] && echo "已備份" || echo "無備份")${NC}"
    
    if [ "$BACKUP" = true ] && [ "$DRY_RUN" = false ]; then
        echo -e "備份位置: ${YELLOW}${BACKUP_DIR}${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}清理操作完成！${NC}"
    
    if [ "$DRY_RUN" = false ]; then
        echo ""
        echo -e "${BLUE}下一步建議:${NC}"
        echo "1. 執行測試部署: ./deploy.sh production up"
        echo "2. 驗證所有服務正常運行"
        echo "3. 檢查監控功能是否正常"
    fi
}

# 主函數
main() {
    echo -e "${BLUE}=== Wazuh GraphRAG 重複檔案清理 ===${NC}"
    echo ""
    
    # 創建備份
    create_backup
    
    # 刪除重複檔案
    delete_duplicates
    
    # 移動檔案
    move_files
    
    # 更新引用
    update_references
    
    # 驗證清理結果
    if [ "$DRY_RUN" = false ]; then
        verify_cleanup
    fi
    
    # 顯示摘要
    show_summary
}

# 執行主函數
main "$@" 