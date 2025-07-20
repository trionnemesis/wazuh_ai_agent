#!/bin/bash

# Wazuh GraphRAG 快速部署腳本
# 版本: 1.0
# 描述: 快速部署 Wazuh GraphRAG 系統
# 作者: AgenticRAG & GraphRAG 架構工程師
# 更新日期: 2024-12

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 預設值
ENVIRONMENT=${1:-production}
ACTION=${2:-up}

# 顯示幫助信息
show_help() {
    echo -e "${BLUE}Wazuh GraphRAG 快速部署腳本${NC}"
    echo ""
    echo "用法: $0 [環境] [動作]"
    echo ""
    echo "環境:"
    echo "  production   生產環境 (預設)"
    echo "  development  開發環境"
    echo ""
    echo "動作:"
    echo "  up           啟動服務 (預設)"
    echo "  down         停止服務"
    echo "  restart      重啟服務"
    echo "  logs         查看日誌"
    echo "  status       查看狀態"
    echo ""
    echo "範例:"
    echo "  $0 production up"
    echo "  $0 development restart"
    echo ""
}

# 檢查 Docker Compose 是否可用
check_docker_compose() {
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}錯誤: Docker Compose 未安裝或不在 PATH 中${NC}"
        exit 1
    fi
}

# 檢查必要文件
check_files() {
    local compose_file="wazuh-docker/single-node/docker-compose.main.yml"
    
    if [ ! -f "$compose_file" ]; then
        echo -e "${RED}錯誤: 找不到 Docker Compose 文件: $compose_file${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ 檢查必要文件完成${NC}"
}

# 顯示部署信息
show_deploy_info() {
    echo -e "${BLUE}=== Wazuh GraphRAG 部署信息 ===${NC}"
    echo -e "部署環境: ${YELLOW}${ENVIRONMENT}${NC}"
    echo -e "執行動作: ${YELLOW}${ACTION}${NC}"
    echo -e "Docker Compose 文件: ${YELLOW}wazuh-docker/single-node/docker-compose.main.yml${NC}"
    echo ""
}

# 啟動服務
start_services() {
    echo -e "${BLUE}啟動 Wazuh GraphRAG 服務...${NC}"
    
    cd wazuh-docker/single-node
    
    # 使用 docker-compose 啟動服務
    docker-compose -f docker-compose.main.yml up -d
    
    echo -e "${GREEN}✓ 服務啟動完成${NC}"
}

# 停止服務
stop_services() {
    echo -e "${BLUE}停止 Wazuh GraphRAG 服務...${NC}"
    
    cd wazuh-docker/single-node
    
    docker-compose -f docker-compose.main.yml down
    
    echo -e "${GREEN}✓ 服務停止完成${NC}"
}

# 重啟服務
restart_services() {
    echo -e "${BLUE}重啟 Wazuh GraphRAG 服務...${NC}"
    
    cd wazuh-docker/single-node
    
    docker-compose -f docker-compose.main.yml restart
    
    echo -e "${GREEN}✓ 服務重啟完成${NC}"
}

# 查看日誌
show_logs() {
    echo -e "${BLUE}顯示 Wazuh GraphRAG 服務日誌...${NC}"
    
    cd wazuh-docker/single-node
    
    docker-compose -f docker-compose.main.yml logs -f
}

# 查看狀態
show_status() {
    echo -e "${BLUE}Wazuh GraphRAG 服務狀態${NC}"
    echo ""
    
    cd wazuh-docker/single-node
    
    docker-compose -f docker-compose.main.yml ps
    
    echo ""
    echo -e "${BLUE}服務健康檢查${NC}"
    echo ""
    
    # 檢查各服務健康狀態
    services=("wazuh.manager" "wazuh.indexer" "wazuh.dashboard" "neo4j" "ai-agent" "prometheus" "grafana")
    
    for service in "${services[@]}"; do
        if docker-compose -f docker-compose.main.yml ps | grep -q "$service.*Up"; then
            echo -e "${GREEN}✓ $service: 運行中${NC}"
        else
            echo -e "${RED}✗ $service: 未運行${NC}"
        fi
    done
}

# 顯示訪問信息
show_access_info() {
    echo ""
    echo -e "${BLUE}=== 服務訪問信息 ===${NC}"
    echo -e "Wazuh Dashboard: ${YELLOW}https://localhost:443${NC}"
    echo -e "AI Agent API: ${YELLOW}http://localhost:8000${NC}"
    echo -e "Neo4j Browser: ${YELLOW}http://localhost:7474${NC}"
    echo -e "Prometheus: ${YELLOW}http://localhost:9090${NC}"
    echo -e "Grafana: ${YELLOW}http://localhost:3000${NC}"
    echo ""
    echo -e "${GREEN}部署完成！${NC}"
}

# 主函數
main() {
    # 檢查參數
    if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        show_help
        exit 0
    fi
    
    # 檢查環境
    if [ "$ENVIRONMENT" != "production" ] && [ "$ENVIRONMENT" != "development" ]; then
        echo -e "${RED}錯誤: 無效的環境參數: $ENVIRONMENT${NC}"
        echo "請使用 'production' 或 'development'"
        exit 1
    fi
    
    # 檢查動作
    case $ACTION in
        up|down|restart|logs|status)
            ;;
        *)
            echo -e "${RED}錯誤: 無效的動作參數: $ACTION${NC}"
            echo "請使用 'up', 'down', 'restart', 'logs' 或 'status'"
            exit 1
            ;;
    esac
    
    # 檢查依賴
    check_docker_compose
    check_files
    
    # 顯示部署信息
    show_deploy_info
    
    # 執行動作
    case $ACTION in
        up)
            start_services
            show_access_info
            ;;
        down)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        logs)
            show_logs
            ;;
        status)
            show_status
            ;;
    esac
}

# 執行主函數
main "$@" 