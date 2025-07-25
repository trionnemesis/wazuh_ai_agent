#!/bin/bash

# Wazuh GraphRAG 整合監控系統 - 簡化啟動腳本
# 版本: 2.1 (移除健康檢查依賴)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common-functions.sh"

# 檢查必要檔案
check_prerequisites() {
    log_info "檢查必要檔案和目錄..."
    
    if [ ! -f "docker-compose.main.yml" ]; then
        log_error "docker-compose.main.yml 檔案不存在！"
        exit 1
    fi
    
    if [ ! -d "ai-agent-project" ]; then
        log_error "ai-agent-project 目錄不存在！"
        exit 1
    fi
    
    log_success "必要檔案檢查完成"
}

# 顯示系統狀態
show_status() {
    log_info "=== Wazuh GraphRAG 整合監控系統狀態 ==="
    echo
    log_info "服務存取點："
    echo "  🔐 Wazuh Dashboard:    https://localhost:443"
    echo "  🧠 AI Agent Metrics:   http://localhost:8000/metrics"
    echo "  📊 Neo4j Browser:      http://localhost:7474"
    echo "  📈 Prometheus:         http://localhost:9090"
    echo "  📉 Grafana:            http://localhost:3000"
    echo "  🖥️  Node Exporter:      http://localhost:9100"
    echo
    log_info "預設認證資訊："
    echo "  Wazuh: admin / SecretPassword"
    echo "  Neo4j: neo4j / wazuh-graph-2024"
    echo "  Grafana: admin / wazuh-grafana-2024"
    echo
}

# 簡單等待函數
wait_for_containers() {
    log_info "等待容器啟動（60秒）..."
    sleep 60
    
    log_info "檢查容器狀態..."
    docker-compose -f docker-compose.main.yml ps
}

# 主要函數
main() {
    echo "========================================================"
    echo "🚀 Wazuh GraphRAG 整合監控系統啟動器 v2.1"
    echo "========================================================"
    echo
    
    # 檢查先決條件
    check_prerequisites
    
    # 啟動服務
    log_info "啟動統一 Docker Compose 堆疊..."
    
    # 停止可能存在的舊容器
    log_info "清理現有容器..."
    docker-compose -f docker-compose.main.yml down 2>/dev/null || true
    
    # 啟動服務
    log_info "啟動服務（這可能需要幾分鐘時間）..."
    docker-compose -f docker-compose.main.yml up -d
    
    if [ $? -eq 0 ]; then
        log_success "Docker Compose 堆疊啟動成功！"
        
        # 等待容器穩定
        wait_for_containers
        
        # 顯示狀態
        show_status
        
        log_success "🎉 Wazuh GraphRAG 整合監控系統已啟動！"
        echo
        log_info "注意：服務可能需要額外的時間來完全初始化"
        log_info "使用以下命令檢查服務狀態："
        echo "  docker-compose -f docker-compose.main.yml ps"
        echo "  docker-compose -f docker-compose.main.yml logs [service_name]"
        
    else
        log_error "Docker Compose 堆疊啟動失敗！"
        exit 1
    fi
}

# 執行主函數
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi