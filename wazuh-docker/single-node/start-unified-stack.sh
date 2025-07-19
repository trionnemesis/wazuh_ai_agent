#!/bin/bash

# Wazuh GraphRAG 整合監控系統 - 統一啟動腳本
# 版本: 1.0
# 描述: 啟動完整的 Wazuh、AI Agent、Neo4j、Prometheus 和 Grafana 監控堆疊

set -e

# 載入共用函數庫
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common-functions.sh"

# 檢查必要檔案
check_prerequisites() {
    log_info "檢查必要檔案和目錄..."
    
    # 檢查 Docker Compose 檔案
    if [ ! -f "docker-compose.main.yml" ]; then
        log_error "docker-compose.main.yml 檔案不存在！"
        exit 1
    fi
    
    # 檢查 AI Agent 專案目錄
    if [ ! -d "ai-agent-project" ]; then
        log_error "ai-agent-project 目錄不存在！"
        exit 1
    fi
    
    # 檢查環境變數檔案
    if [ ! -f "ai-agent-project/.env" ]; then
        log_warning "ai-agent-project/.env 檔案不存在，請確認已設定正確的環境變數"
    fi
    
    # 檢查 SSL 憑證目錄
    if [ ! -d "config/wazuh_indexer_ssl_certs" ]; then
        log_warning "SSL 憑證目錄不存在，可能需要先生成憑證"
        log_info "執行憑證生成： docker-compose -f generate-indexer-certs.yml run --rm generator"
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

# 等待服務就緒
wait_for_services() {
    log_info "等待關鍵服務啟動..."
    
    local max_attempts=60
    local attempt=1
    
    # 等待 Wazuh Indexer
    log_info "等待 Wazuh Indexer (OpenSearch) 就緒..."
    while [ $attempt -le $max_attempts ]; do
        if curl -k -s -u admin:SecretPassword "https://localhost:9200/_cluster/health" > /dev/null 2>&1; then
            log_success "Wazuh Indexer 已就緒"
            break
        fi
        echo -n "."
        sleep 5
        ((attempt++))
    done
    
    if [ $attempt -gt $max_attempts ]; then
        log_error "Wazuh Indexer 啟動超時"
        return 1
    fi
    
    # 等待 Neo4j
    log_info "等待 Neo4j 就緒..."
    attempt=1
    while [ $attempt -le $max_attempts ]; do
        if curl -s "http://localhost:7474" > /dev/null 2>&1; then
            log_success "Neo4j 已就緒"
            break
        fi
        echo -n "."
        sleep 5
        ((attempt++))
    done
    
    # 等待 Prometheus
    log_info "等待 Prometheus 就緒..."
    attempt=1
    while [ $attempt -le $max_attempts ]; do
        if curl -s "http://localhost:9090/-/healthy" > /dev/null 2>&1; then
            log_success "Prometheus 已就緒"
            break
        fi
        echo -n "."
        sleep 5
        ((attempt++))
    done
    
    # 等待 Grafana
    log_info "等待 Grafana 就緒..."
    attempt=1
    while [ $attempt -le $max_attempts ]; do
        if curl -s "http://localhost:3000/api/health" > /dev/null 2>&1; then
            log_success "Grafana 已就緒"
            break
        fi
        echo -n "."
        sleep 5
        ((attempt++))
    done
    
    log_success "所有關鍵服務已就緒！"
}

# 主要函數
main() {
    echo "========================================================"
    echo "🚀 Wazuh GraphRAG 整合監控系統啟動器"
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
        
        # 等待服務就緒
        wait_for_services
        
        # 顯示狀態
        show_status
        
        log_success "🎉 Wazuh GraphRAG 整合監控系統已成功啟動！"
        echo
        log_info "使用 'docker-compose -f docker-compose.main.yml logs -f [service_name]' 查看日誌"
        log_info "使用 'docker-compose -f docker-compose.main.yml down' 停止所有服務"
        
    else
        log_error "Docker Compose 堆疊啟動失敗！"
        exit 1
    fi
}

# 如果直接執行此腳本
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi