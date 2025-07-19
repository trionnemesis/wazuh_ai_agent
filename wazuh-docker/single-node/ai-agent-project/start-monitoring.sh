#!/bin/bash

# Wazuh AI Agent 監控系統啟動腳本
# 此腳本會啟動 Prometheus 和 Grafana 監控服務

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印帶顏色的消息
print_message() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 檢查 Docker 是否安裝
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安裝。請先安裝 Docker。"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose 未安裝。請先安裝 Docker Compose。"
        exit 1
    fi
}

# 檢查必要的文件是否存在
check_files() {
    local files=(
        "docker-compose.monitoring.yml"
        "prometheus.yml"
        "grafana/provisioning/datasources/prometheus.yml"
        "grafana/provisioning/dashboards/dashboard.yml"
        "grafana/dashboards/ai-agent-monitoring.json"
    )

    for file in "${files[@]}"; do
        if [[ ! -f "$file" ]]; then
            print_error "必要文件不存在: $file"
            exit 1
        fi
    done
    
    print_success "所有必要文件檢查通過"
}

# 檢查網路是否存在
check_network() {
    if ! docker network ls | grep -q "wazuh"; then
        print_warning "Wazuh 網路不存在，正在創建..."
        docker network create wazuh || {
            print_error "創建 Wazuh 網路失敗"
            exit 1
        }
        print_success "Wazuh 網路創建成功"
    else
        print_success "Wazuh 網路已存在"
    fi
}

# 啟動監控服務
start_monitoring() {
    print_message "正在啟動監控服務..."
    
    # 停止現有的監控服務（如果存在）
    docker-compose -f docker-compose.monitoring.yml down 2>/dev/null || true
    
    # 啟動服務
    docker-compose -f docker-compose.monitoring.yml up -d
    
    if [[ $? -eq 0 ]]; then
        print_success "監控服務啟動成功"
    else
        print_error "監控服務啟動失敗"
        exit 1
    fi
}

# 等待服務就緒
wait_for_services() {
    print_message "等待服務就緒..."
    
    # 等待 Prometheus
    print_message "檢查 Prometheus 服務..."
    for i in {1..30}; do
        if curl -s http://localhost:9090/-/ready > /dev/null 2>&1; then
            print_success "Prometheus 服務已就緒"
            break
        fi
        
        if [[ $i -eq 30 ]]; then
            print_warning "Prometheus 服務可能尚未完全就緒"
        fi
        
        sleep 2
    done
    
    # 等待 Grafana
    print_message "檢查 Grafana 服務..."
    for i in {1..30}; do
        if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
            print_success "Grafana 服務已就緒"
            break
        fi
        
        if [[ $i -eq 30 ]]; then
            print_warning "Grafana 服務可能尚未完全就緒"
        fi
        
        sleep 2
    done
}

# 顯示服務狀態
show_status() {
    print_message "檢查服務狀態..."
    echo ""
    docker-compose -f docker-compose.monitoring.yml ps
    echo ""
}

# 顯示訪問信息
show_access_info() {
    echo ""
    print_success "監控系統部署完成！"
    echo ""
    echo "===== 服務訪問信息 ====="
    echo "🔗 AI Agent 指標端點: http://localhost:8000/metrics"
    echo "📊 Prometheus UI:      http://localhost:9090"
    echo "📈 Grafana Dashboard:  http://localhost:3000"
    echo ""
    echo "===== Grafana 登入資訊 ====="
    echo "👤 使用者名稱: admin"
    echo "🔐 密碼:       wazuh-grafana-2024"
    echo ""
    echo "===== 有用的指令 ====="
    echo "📋 檢查服務狀態:"
    echo "   docker-compose -f docker-compose.monitoring.yml ps"
    echo ""
    echo "📝 查看日誌:"
    echo "   docker-compose -f docker-compose.monitoring.yml logs -f"
    echo ""
    echo "⏹️  停止監控服務:"
    echo "   docker-compose -f docker-compose.monitoring.yml down"
    echo ""
    echo "🔄 重啟監控服務:"
    echo "   docker-compose -f docker-compose.monitoring.yml restart"
    echo ""
}

# 主函數
main() {
    echo ""
    print_message "🚀 Wazuh AI Agent 監控系統啟動腳本"
    echo ""
    
    print_message "正在檢查系統要求..."
    check_docker
    check_files
    check_network
    
    start_monitoring
    wait_for_services
    show_status
    show_access_info
    
    print_success "監控系統部署完成！請查看上述訪問信息。"
}

# 執行主函數
main "$@"