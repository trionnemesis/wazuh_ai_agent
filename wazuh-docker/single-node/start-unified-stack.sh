#!/bin/bash

# Wazuh GraphRAG 整合監控系統 - 統一啟動腳本
# 版本: 2.0
# 描述: 啟動完整的 Wazuh、AI Agent、Neo4j、Prometheus 和 Grafana 監控堆疊

set -e

# 載入共用函數庫
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common-functions.sh"

# 健康檢查配置
HEALTH_CHECK_TIMEOUT=300  # 5分鐘總超時
HEALTH_CHECK_INTERVAL=10  # 每10秒檢查一次
MAX_RETRIES=30           # 最大重試次數

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

# 檢查 HTTP 服務健康狀態
check_http_service() {
    local service_name="$1"
    local url="$2"
    local timeout="${3:-10}"
    
    if curl -f -s --max-time $timeout "$url" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# 檢查 HTTPS 服務健康狀態（忽略憑證驗證）
check_https_service() {
    local service_name="$1"
    local url="$2"
    local timeout="${3:-10}"
    
    if curl -k -f -s --max-time $timeout "$url" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# 檢查 Docker 容器狀態
check_docker_container() {
    local container_name="$1"
    
    if docker ps --filter "name=$container_name" --filter "status=running" | grep -q "$container_name"; then
        return 0
    else
        return 1
    fi
}

# 等待單個服務就緒
wait_for_service() {
    local service_name="$1"
    local check_command="$2"
    local timeout_seconds="${3:-$HEALTH_CHECK_TIMEOUT}"
    local interval_seconds="${4:-$HEALTH_CHECK_INTERVAL}"
    
    log_info "等待 $service_name 就緒..."
    local start_time=$(date +%s)
    local attempts=0
    
    while true; do
        attempts=$((attempts + 1))
        current_time=$(date +%s)
        elapsed=$((current_time - start_time))
        
        # 檢查是否超時
        if [ $elapsed -ge $timeout_seconds ]; then
            log_error "$service_name 啟動超時 (${timeout_seconds}秒)"
            return 1
        fi
        
        # 執行健康檢查
        if eval "$check_command" > /dev/null 2>&1; then
            log_success "$service_name 已就緒 (${elapsed}秒)"
            return 0
        fi
        
        # 顯示進度
        if [ $((attempts % 3)) -eq 0 ]; then
            echo -n "."
        fi
        
        sleep $interval_seconds
    done
}

# 等待所有關鍵服務就緒
wait_for_services() {
    log_info "等待關鍵服務啟動..."
    echo
    
    local failed_services=()
    
    # 等待 Wazuh Indexer
    if ! wait_for_service "Wazuh Indexer" \
        'curl -k -s -u admin:SecretPassword "https://localhost:9200/_cluster/health"' \
        180 10; then
        failed_services+=("Wazuh Indexer")
    fi
    
    # 等待 Neo4j
    if ! wait_for_service "Neo4j" \
        'curl -s "http://localhost:7474"' \
        120 10; then
        failed_services+=("Neo4j")
    fi
    
    # 等待 AI Agent
    if ! wait_for_service "AI Agent" \
        'curl -s "http://localhost:8000/health"' \
        60 5; then
        failed_services+=("AI Agent")
    fi
    
    # 等待 Prometheus
    if ! wait_for_service "Prometheus" \
        'curl -s "http://localhost:9090/-/healthy"' \
        60 5; then
        failed_services+=("Prometheus")
    fi
    
    # 等待 Grafana
    if ! wait_for_service "Grafana" \
        'curl -s "http://localhost:3000/api/health"' \
        60 5; then
        failed_services+=("Grafana")
    fi
    
    # 檢查是否有服務失敗
    if [ ${#failed_services[@]} -gt 0 ]; then
        log_error "以下服務啟動失敗："
        for service in "${failed_services[@]}"; do
            echo "  - $service"
        done
        echo
        log_info "故障排除建議："
        echo "  1. 檢查服務日誌： docker-compose -f docker-compose.main.yml logs [service_name]"
        echo "  2. 檢查系統資源： docker stats"
        echo "  3. 重新啟動服務： docker-compose -f docker-compose.main.yml restart [service_name]"
        echo "  4. 執行健康檢查： ./health-check.sh"
        return 1
    fi
    
    log_success "所有關鍵服務已就緒！"
    return 0
}

# 主要函數
main() {
    echo "========================================================"
    echo "🚀 Wazuh GraphRAG 整合監控系統啟動器 v2.0"
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
        if wait_for_services; then
            # 顯示狀態
            show_status
            
            log_success "🎉 Wazuh GraphRAG 整合監控系統已成功啟動！"
            echo
            log_info "使用 'docker-compose -f docker-compose.main.yml logs -f [service_name]' 查看日誌"
            log_info "使用 'docker-compose -f docker-compose.main.yml down' 停止所有服務"
            log_info "使用 './health-check.sh' 檢查服務健康狀態"
            
            # 執行快速健康檢查
            echo
            log_info "執行快速健康檢查..."
            if ./health-check.sh > /dev/null 2>&1; then
                log_success "所有服務健康檢查通過！"
            else
                log_warning "部分服務可能需要更多時間初始化，請稍後執行 './health-check.sh' 進行詳細檢查"
            fi
        else
            log_error "服務啟動失敗，請檢查上述錯誤訊息"
            exit 1
        fi
        
    else
        log_error "Docker Compose 堆疊啟動失敗！"
        exit 1
    fi
}

# 如果直接執行此腳本
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi