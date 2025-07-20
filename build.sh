#!/bin/bash

# Wazuh GraphRAG 統一構建腳本
# 版本: 1.0
# 描述: 統一構建 Wazuh GraphRAG 系統的所有 Docker 映像檔
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
BUILD_ENV=${1:-production}
VERSION=${2:-latest}
REGISTRY=${3:-""}
PUSH_IMAGES=${4:-false}

# 映像檔名稱
AI_AGENT_IMAGE="wazuh-ai-agent"
WAZUH_MANAGER_IMAGE="wazuh-manager"
WAZUH_INDEXER_IMAGE="wazuh-indexer"
WAZUH_DASHBOARD_IMAGE="wazuh-dashboard"

# 顯示幫助信息
show_help() {
    echo -e "${BLUE}Wazuh GraphRAG 統一構建腳本${NC}"
    echo ""
    echo "用法: $0 [環境] [版本] [註冊表] [推送]"
    echo ""
    echo "參數:"
    echo "  環境     構建環境 (development|production) [預設: production]"
    echo "  版本     映像檔版本標籤 [預設: latest]"
    echo "  註冊表   Docker 註冊表 URL (可選)"
    echo "  推送     是否推送映像檔到註冊表 (true|false) [預設: false]"
    echo ""
    echo "範例:"
    echo "  $0 production v1.0.0"
    echo "  $0 development latest myregistry.com true"
    echo ""
}

# 檢查 Docker 是否可用
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}錯誤: Docker 未安裝或不在 PATH 中${NC}"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        echo -e "${RED}錯誤: Docker 守護程序未運行${NC}"
        exit 1
    fi
}

# 顯示構建信息
show_build_info() {
    echo -e "${BLUE}=== Wazuh GraphRAG 構建信息 ===${NC}"
    echo -e "構建環境: ${YELLOW}${BUILD_ENV}${NC}"
    echo -e "版本標籤: ${YELLOW}${VERSION}${NC}"
    echo -e "Docker 註冊表: ${YELLOW}${REGISTRY:-"本地"}${NC}"
    echo -e "推送映像檔: ${YELLOW}${PUSH_IMAGES}${NC}"
    echo ""
}

# 構建 AI Agent 映像檔
build_ai_agent() {
    echo -e "${BLUE}構建 AI Agent 映像檔...${NC}"
    
    local image_name="${REGISTRY:+${REGISTRY}/}${AI_AGENT_IMAGE}:${VERSION}"
    local context="wazuh-docker/single-node/ai-agent-project"
    
    docker build \
        --build-arg BUILD_ENV=${BUILD_ENV} \
        --target ${BUILD_ENV} \
        -t ${image_name} \
        -f ${context}/Dockerfile \
        ${context}
    
    echo -e "${GREEN}✓ AI Agent 映像檔構建完成: ${image_name}${NC}"
}

# 構建 Wazuh 核心服務映像檔 (僅開發環境)
build_wazuh_services() {
    if [ "$BUILD_ENV" = "development" ]; then
        echo -e "${BLUE}構建 Wazuh 核心服務映像檔...${NC}"
        
        # 構建 Wazuh Manager
        local manager_image="${REGISTRY:+${REGISTRY}/}${WAZUH_MANAGER_IMAGE}:${VERSION}"
        docker build \
            -t ${manager_image} \
            wazuh-docker/build-docker-images/wazuh-manager
        echo -e "${GREEN}✓ Wazuh Manager 映像檔構建完成: ${manager_image}${NC}"
        
        # 構建 Wazuh Indexer
        local indexer_image="${REGISTRY:+${REGISTRY}/}${WAZUH_INDEXER_IMAGE}:${VERSION}"
        docker build \
            -t ${indexer_image} \
            wazuh-docker/build-docker-images/wazuh-indexer
        echo -e "${GREEN}✓ Wazuh Indexer 映像檔構建完成: ${indexer_image}${NC}"
        
        # 構建 Wazuh Dashboard
        local dashboard_image="${REGISTRY:+${REGISTRY}/}${WAZUH_DASHBOARD_IMAGE}:${VERSION}"
        docker build \
            -t ${dashboard_image} \
            wazuh-docker/build-docker-images/wazuh-dashboard
        echo -e "${GREEN}✓ Wazuh Dashboard 映像檔構建完成: ${dashboard_image}${NC}"
    else
        echo -e "${YELLOW}跳過 Wazuh 核心服務構建 (生產環境使用官方映像檔)${NC}"
    fi
}

# 推送映像檔到註冊表
push_images() {
    if [ "$PUSH_IMAGES" = "true" ] && [ -n "$REGISTRY" ]; then
        echo -e "${BLUE}推送映像檔到註冊表...${NC}"
        
        # 推送 AI Agent
        local ai_agent_image="${REGISTRY}/${AI_AGENT_IMAGE}:${VERSION}"
        docker push ${ai_agent_image}
        echo -e "${GREEN}✓ AI Agent 映像檔推送完成${NC}"
        
        # 推送 Wazuh 服務 (僅開發環境)
        if [ "$BUILD_ENV" = "development" ]; then
            docker push "${REGISTRY}/${WAZUH_MANAGER_IMAGE}:${VERSION}"
            docker push "${REGISTRY}/${WAZUH_INDEXER_IMAGE}:${VERSION}"
            docker push "${REGISTRY}/${WAZUH_DASHBOARD_IMAGE}:${VERSION}"
            echo -e "${GREEN}✓ Wazuh 核心服務映像檔推送完成${NC}"
        fi
    else
        echo -e "${YELLOW}跳過映像檔推送${NC}"
    fi
}

# 顯示構建摘要
show_summary() {
    echo ""
    echo -e "${BLUE}=== 構建摘要 ===${NC}"
    echo -e "構建環境: ${GREEN}${BUILD_ENV}${NC}"
    echo -e "版本標籤: ${GREEN}${VERSION}${NC}"
    echo -e "AI Agent 映像檔: ${GREEN}${REGISTRY:+${REGISTRY}/}${AI_AGENT_IMAGE}:${VERSION}${NC}"
    
    if [ "$BUILD_ENV" = "development" ]; then
        echo -e "Wazuh Manager: ${GREEN}${REGISTRY:+${REGISTRY}/}${WAZUH_MANAGER_IMAGE}:${VERSION}${NC}"
        echo -e "Wazuh Indexer: ${GREEN}${REGISTRY:+${REGISTRY}/}${WAZUH_INDEXER_IMAGE}:${VERSION}${NC}"
        echo -e "Wazuh Dashboard: ${GREEN}${REGISTRY:+${REGISTRY}/}${WAZUH_DASHBOARD_IMAGE}:${VERSION}${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}所有映像檔構建完成！${NC}"
}

# 清理函數
cleanup() {
    echo -e "${YELLOW}清理構建快取...${NC}"
    docker builder prune -f
    echo -e "${GREEN}清理完成${NC}"
}

# 主函數
main() {
    # 檢查參數
    if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        show_help
        exit 0
    fi
    
    # 檢查 Docker
    check_docker
    
    # 顯示構建信息
    show_build_info
    
    # 開始構建
    echo -e "${BLUE}開始構建 Wazuh GraphRAG 映像檔...${NC}"
    echo ""
    
    # 構建 AI Agent
    build_ai_agent
    
    # 構建 Wazuh 服務
    build_wazuh_services
    
    # 推送映像檔
    push_images
    
    # 清理
    cleanup
    
    # 顯示摘要
    show_summary
}

# 執行主函數
main "$@" 