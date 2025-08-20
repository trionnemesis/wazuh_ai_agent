#!/bin/bash
# Wazuh Docker 映像簡化構建腳本
# 版本: 2.0
# 描述: 簡化的 Docker 映像構建流程

set -e

# 預設值
WAZUH_VERSION="${WAZUH_VERSION:-4.7.4}"
WAZUH_TAG_REVISION="${WAZUH_TAG_REVISION:-1}"
WAZUH_DEV_STAGE="${WAZUH_DEV_STAGE:-}"
FILEBEAT_MODULE_VERSION="${FILEBEAT_MODULE_VERSION:-0.3}"
BUILD_ENV="${BUILD_ENV:-production}"

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日誌函數
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 幫助函數
help() {
    cat << EOF
使用方式: $0 [選項]

選項:
    -v, --version <ver>     設定 Wazuh 版本 (預設: ${WAZUH_VERSION})
    -r, --revision <rev>    設定修訂版本 (預設: ${WAZUH_TAG_REVISION})
    -e, --env <env>         設定構建環境: production, development (預設: ${BUILD_ENV})
    -c, --clean             清理構建快取
    -h, --help              顯示此幫助訊息

範例:
    $0                      # 使用預設值構建
    $0 -v 4.7.5            # 構建 Wazuh 4.7.5
    $0 -e development      # 構建開發版本
    $0 --clean            # 清理並重新構建

EOF
    exit ${1:-0}
}

# 清理函數
clean_build() {
    log_info "清理 Docker 構建快取..."
    docker builder prune -f
    docker image prune -f
    log_info "清理完成"
}

# 準備構建環境
prepare_build_env() {
    log_info "準備構建環境..."
    
    # 計算必要的變數
    WAZUH_VERSION_NUM=$(echo $WAZUH_VERSION | sed -e 's/\.//g')
    FILEBEAT_TEMPLATE_BRANCH="${WAZUH_VERSION}"
    WAZUH_FILEBEAT_MODULE="wazuh-filebeat-${FILEBEAT_MODULE_VERSION}.tar.gz"
    WAZUH_UI_REVISION="${WAZUH_TAG_REVISION}"
    
    # 檢查分支是否存在
    if [ "${WAZUH_DEV_STAGE}" ]; then
        FILEBEAT_TEMPLATE_BRANCH="v${FILEBEAT_TEMPLATE_BRANCH}-${WAZUH_DEV_STAGE,,}"
    else
        if curl --output /dev/null --silent --head --fail "https://github.com/wazuh/wazuh/tree/v${FILEBEAT_TEMPLATE_BRANCH}"; then
            FILEBEAT_TEMPLATE_BRANCH="v${FILEBEAT_TEMPLATE_BRANCH}"
        elif curl --output /dev/null --silent --head --fail "https://github.com/wazuh/wazuh/tree/${FILEBEAT_TEMPLATE_BRANCH}"; then
            FILEBEAT_TEMPLATE_BRANCH="${FILEBEAT_TEMPLATE_BRANCH}"
        else
            FILEBEAT_TEMPLATE_BRANCH="master"
        fi
    fi
    
    # 創建臨時 .env 檔案
    cat > .build.env << EOF
WAZUH_VERSION=${WAZUH_VERSION}
WAZUH_IMAGE_VERSION=${WAZUH_VERSION}
WAZUH_TAG_REVISION=${WAZUH_TAG_REVISION}
FILEBEAT_TEMPLATE_BRANCH=${FILEBEAT_TEMPLATE_BRANCH}
WAZUH_FILEBEAT_MODULE=${WAZUH_FILEBEAT_MODULE}
WAZUH_UI_REVISION=${WAZUH_UI_REVISION}
BUILD_ENV=${BUILD_ENV}
EOF
    
    log_info "構建配置:"
    cat .build.env | sed 's/^/  /'
}

# 構建映像
build_images() {
    log_info "開始構建 Docker 映像..."
    
    # 使用 --no-cache 選項以確保乾淨構建
    local cache_option=""
    if [ "${CLEAN_BUILD}" = "true" ]; then
        cache_option="--no-cache"
    fi
    
    # 構建映像
    if docker-compose -f build-images.yml --env-file .build.env build ${cache_option}; then
        log_info "✅ Docker 映像構建成功！"
        
        # 列出構建的映像
        log_info "構建的映像:"
        docker images | grep wazuh | head -5
    else
        log_error "❌ Docker 映像構建失敗！"
        return 1
    fi
    
    # 清理臨時檔案
    rm -f .build.env
}

# 主函數
main() {
    local CLEAN_BUILD=false
    
    # 解析命令行參數
    while [[ $# -gt 0 ]]; do
        case $1 in
            -v|--version)
                WAZUH_VERSION="$2"
                shift 2
                ;;
            -r|--revision)
                WAZUH_TAG_REVISION="$2"
                shift 2
                ;;
            -e|--env)
                BUILD_ENV="$2"
                shift 2
                ;;
            -c|--clean)
                CLEAN_BUILD=true
                shift
                ;;
            -h|--help)
                help 0
                ;;
            *)
                log_error "未知選項: $1"
                help 1
                ;;
        esac
    done
    
    echo "========================================"
    echo "🐳 Wazuh Docker 映像構建器 v2.0"
    echo "========================================"
    echo
    
    # 清理構建快取（如果需要）
    if [ "${CLEAN_BUILD}" = "true" ]; then
        clean_build
    fi
    
    # 準備構建環境
    prepare_build_env
    
    # 執行構建
    build_images
}

# 執行主程式
main "$@"