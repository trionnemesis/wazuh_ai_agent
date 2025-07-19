#!/bin/bash

# Wazuh GraphRAG 整合監控系統 - 健康檢查腳本
# 版本: 1.0
# 描述: 檢查所有服務的健康狀態

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 健康狀態計數器
total_services=0
healthy_services=0
unhealthy_services=0

# 日誌函數
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
    ((healthy_services++))
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
    ((unhealthy_services++))
}

# 檢查 HTTP 服務
check_http_service() {
    local service_name="$1"
    local url="$2"
    local timeout="${3:-10}"
    
    ((total_services++))
    
    if curl -f -s --max-time $timeout "$url" > /dev/null 2>&1; then
        log_success "$service_name 服務正常 ($url)"
        return 0
    else
        log_error "$service_name 服務異常 ($url)"
        return 1
    fi
}

# 檢查 HTTPS 服務（忽略憑證驗證）
check_https_service() {
    local service_name="$1"
    local url="$2"
    local timeout="${3:-10}"
    
    ((total_services++))
    
    if curl -k -f -s --max-time $timeout "$url" > /dev/null 2>&1; then
        log_success "$service_name 服務正常 ($url)"
        return 0
    else
        log_error "$service_name 服務異常 ($url)"
        return 1
    fi
}

# 檢查 Docker 容器狀態
check_docker_container() {
    local container_name="$1"
    
    ((total_services++))
    
    if docker ps --filter "name=$container_name" --filter "status=running" | grep -q "$container_name"; then
        log_success "Docker 容器 $container_name 正在運行"
        return 0
    else
        log_error "Docker 容器 $container_name 未運行或不存在"
        return 1
    fi
}

# 檢查網路連通性
check_network_connectivity() {
    local service_name="$1"
    local host="$2"
    local port="$3"
    
    ((total_services++))
    
    if timeout 5 bash -c "</dev/tcp/$host/$port"; then
        log_success "$service_name 網路連通性正常 ($host:$port)"
        return 0
    else
        log_error "$service_name 網路連通性異常 ($host:$port)"
        return 1
    fi
}

# 檢查 Neo4j 特定健康狀態
check_neo4j_health() {
    ((total_services++))
    
    # 檢查 Neo4j 是否可以接受 Cypher 查詢
    if docker exec wazuh-neo4j-graphrag cypher-shell -u neo4j -p wazuh-graph-2024 "CALL db.ping()" > /dev/null 2>&1; then
        log_success "Neo4j 資料庫連接正常"
        return 0
    else
        log_error "Neo4j 資料庫連接異常"
        return 1
    fi
}

# 檢查 Prometheus 目標狀態
check_prometheus_targets() {
    ((total_services++))
    
    local healthy_targets=$(curl -s "http://localhost:9090/api/v1/targets" 2>/dev/null | jq '.data.activeTargets[] | select(.health=="up") | .health' 2>/dev/null | wc -l)
    local total_targets=$(curl -s "http://localhost:9090/api/v1/targets" 2>/dev/null | jq '.data.activeTargets | length' 2>/dev/null)
    
    if [ "$healthy_targets" -gt 0 ] && [ "$total_targets" -gt 0 ]; then
        log_success "Prometheus 目標狀態：$healthy_targets/$total_targets 個目標正常"
        return 0
    else
        log_error "Prometheus 目標狀態異常"
        return 1
    fi
}

# 顯示詳細的服務狀態
show_detailed_status() {
    log_info "=== 詳細服務狀態 ==="
    echo
    
    # Docker Compose 服務狀態
    if [ -f "docker-compose.main.yml" ]; then
        log_info "Docker Compose 服務狀態："
        docker-compose -f docker-compose.main.yml ps
        echo
    fi
    
    # 資源使用情況
    log_info "系統資源使用情況："
    echo "記憶體使用："
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" 2>/dev/null || echo "無法取得 Docker 統計資訊"
    echo
}

# 主要健康檢查函數
main_health_check() {
    echo "========================================================"
    echo "🔍 Wazuh GraphRAG 整合監控系統健康檢查"
    echo "========================================================"
    echo
    
    log_info "開始執行健康檢查..."
    echo
    
    # 檢查 Docker 容器狀態
    log_info "=== 檢查 Docker 容器狀態 ==="
    check_docker_container "wazuh.manager"
    check_docker_container "wazuh.indexer"
    check_docker_container "wazuh.dashboard"
    check_docker_container "ai-agent"
    check_docker_container "wazuh-neo4j-graphrag"
    check_docker_container "wazuh-prometheus"
    check_docker_container "wazuh-grafana"
    check_docker_container "wazuh-node-exporter"
    echo
    
    # 檢查 HTTP/HTTPS 服務
    log_info "=== 檢查 Web 服務存取 ==="
    check_https_service "Wazuh Dashboard" "https://localhost:443"
    check_http_service "AI Agent Metrics" "http://localhost:8000/metrics"
    check_http_service "Neo4j Browser" "http://localhost:7474"
    check_http_service "Prometheus" "http://localhost:9090"
    check_http_service "Grafana" "http://localhost:3000"
    check_http_service "Node Exporter" "http://localhost:9100"
    echo
    
    # 檢查服務間網路連通性
    log_info "=== 檢查服務間網路連通性 ==="
    check_network_connectivity "Wazuh Indexer" "localhost" "9200"
    check_network_connectivity "Neo4j Bolt" "localhost" "7687"
    check_network_connectivity "Wazuh Manager API" "localhost" "55000"
    echo
    
    # 檢查特定服務健康狀態
    log_info "=== 檢查特定服務健康狀態 ==="
    check_neo4j_health
    check_prometheus_targets
    echo
    
    # 顯示總結
    echo "========================================================"
    log_info "健康檢查總結："
    echo "  總服務數：$total_services"
    echo "  健康服務：$healthy_services"
    echo "  異常服務：$unhealthy_services"
    
    if [ $unhealthy_services -eq 0 ]; then
        log_success "🎉 所有服務都正常運行！"
        echo
        log_info "服務存取點："
        echo "  🔐 Wazuh Dashboard:    https://localhost:443"
        echo "  🧠 AI Agent Metrics:   http://localhost:8000/metrics"
        echo "  📊 Neo4j Browser:      http://localhost:7474"
        echo "  📈 Prometheus:         http://localhost:9090"
        echo "  📉 Grafana:            http://localhost:3000"
        echo "  🖥️  Node Exporter:      http://localhost:9100"
        return 0
    else
        log_error "⚠️  發現 $unhealthy_services 個服務異常"
        echo
        log_info "故障排除建議："
        echo "  1. 檢查服務日誌： docker-compose -f docker-compose.main.yml logs [service_name]"
        echo "  2. 重啟異常服務： docker-compose -f docker-compose.main.yml restart [service_name]"
        echo "  3. 檢查系統資源： docker stats"
        echo "  4. 查看詳細狀態： ./health-check.sh -v"
        return 1
    fi
}

# 檢查命令列參數
case "${1:-}" in
    -v|--verbose)
        main_health_check
        echo
        show_detailed_status
        ;;
    -h|--help)
        echo "使用方法: $0 [選項]"
        echo "選項："
        echo "  -v, --verbose    顯示詳細狀態資訊"
        echo "  -h, --help       顯示此幫助訊息"
        ;;
    *)
        main_health_check
        ;;
esac

# 結束時返回適當的退出碼
if [ $unhealthy_services -eq 0 ]; then
    exit 0
else
    exit 1
fi