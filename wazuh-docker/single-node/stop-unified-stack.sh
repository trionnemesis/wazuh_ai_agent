#!/bin/bash

# Wazuh GraphRAG 整合監控系統 - 統一停止腳本
# 版本: 1.0
# 描述: 安全地停止完整的 Wazuh、AI Agent、Neo4j、Prometheus 和 Grafana 監控堆疊

set -e

# 載入共用函數庫
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common-functions.sh"

# 顯示選項菜單
show_menu() {
    echo "========================================================"
    echo "🛑 Wazuh GraphRAG 整合監控系統停止器"
    echo "========================================================"
    echo
    echo "請選擇停止模式："
    echo "1) 正常停止 (保留資料)"
    echo "2) 完全清理 (刪除所有資料卷)"
    echo "3) 僅停止監控服務 (保留 Wazuh + AI Agent)"
    echo "4) 取消"
    echo
    read -p "請輸入選項 (1-4): " choice
}

# 正常停止服務
normal_stop() {
    log_info "正常停止所有服務..."
    
    if docker-compose -f docker-compose.main.yml down; then
        log_success "✅ 所有服務已成功停止"
        log_info "資料卷已保留，下次啟動時資料將會保留"
    else
        log_error "❌ 停止服務時發生錯誤"
        return 1
    fi
}

# 完全清理
full_cleanup() {
    log_warning "⚠️  警告：此操作將刪除所有資料！"
    read -p "是否確定要繼續？這將刪除所有持久化資料 (y/N): " confirm
    
    if [[ $confirm =~ ^[Yy]$ ]]; then
        log_info "執行完全清理..."
        
        # 停止並刪除容器、網路、資料卷
        if docker-compose -f docker-compose.main.yml down -v --remove-orphans; then
            log_success "✅ 完全清理完成"
            log_warning "所有資料已被刪除"
        else
            log_error "❌ 清理過程中發生錯誤"
            return 1
        fi
        
        # 清理未使用的 Docker 資源
        log_info "清理未使用的 Docker 資源..."
        docker system prune -f
        
    else
        log_info "取消完全清理操作"
    fi
}

# 僅停止監控服務
stop_monitoring_only() {
    log_info "僅停止監控服務 (Prometheus, Grafana, Node Exporter)..."
    
    # 停止監控相關容器
    docker-compose -f docker-compose.main.yml stop grafana prometheus node-exporter
    
    if [ $? -eq 0 ]; then
        log_success "✅ 監控服務已停止"
        log_info "Wazuh、AI Agent 和 Neo4j 仍在運行"
        log_info "重新啟動監控： docker-compose -f docker-compose.main.yml start grafana prometheus node-exporter"
    else
        log_error "❌ 停止監控服務時發生錯誤"
        return 1
    fi
}

# 顯示當前狀態
show_current_status() {
    log_info "=== 當前容器狀態 ==="
    echo
    docker-compose -f docker-compose.main.yml ps 2>/dev/null || echo "無法取得容器狀態"
    echo
}

# 主函數
main() {
    # 檢查 docker-compose.main.yml 是否存在
    if [ ! -f "docker-compose.main.yml" ]; then
        log_error "docker-compose.main.yml 檔案不存在！"
        log_info "請確認您在正確的目錄中執行此腳本"
        exit 1
    fi
    
    # 顯示當前狀態
    show_current_status
    
    # 顯示選項菜單
    show_menu
    
    # 根據選擇執行相應操作
    case $choice in
        1)
            normal_stop
            ;;
        2)
            full_cleanup
            ;;
        3)
            stop_monitoring_only
            ;;
        4)
            log_info "操作已取消"
            exit 0
            ;;
        *)
            log_error "無效的選項，請選擇 1-4"
            exit 1
            ;;
    esac
    
    echo
    log_info "=== 操作完成 ==="
    log_info "如需重新啟動，請執行： ./start-unified-stack.sh"
}

# 如果直接執行此腳本
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi