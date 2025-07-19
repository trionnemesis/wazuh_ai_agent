#!/bin/bash

# Wazuh GraphRAG 整合監控系統 - 共用函數庫
# 版本: 1.0
# 描述: 提供共用的日誌函數和工具函數

# 顏色定義
export RED='\033[0;31m'
export GREEN='\033[0;32m'
export YELLOW='\033[1;33m'
export BLUE='\033[0;34m'
export NC='\033[0m' # No Color

# 日誌函數
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 帶時間戳的日誌函數
log_with_timestamp() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case "$level" in
        "INFO")
            echo -e "${BLUE}[$timestamp INFO]${NC} $message"
            ;;
        "SUCCESS")
            echo -e "${GREEN}[$timestamp SUCCESS]${NC} $message"
            ;;
        "WARNING")
            echo -e "${YELLOW}[$timestamp WARNING]${NC} $message"
            ;;
        "ERROR")
            echo -e "${RED}[$timestamp ERROR]${NC} $message"
            ;;
        *)
            echo "[$timestamp] $message"
            ;;
    esac
}

# 檢查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 檢查 Docker 服務是否正在運行
is_docker_running() {
    if ! command_exists docker; then
        log_error "Docker 未安裝"
        return 1
    fi
    
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker 服務未運行"
        return 1
    fi
    
    return 0
}

# 檢查 Docker Compose 是否可用
is_docker_compose_available() {
    if command_exists docker-compose; then
        return 0
    elif docker compose version >/dev/null 2>&1; then
        return 0
    else
        log_error "Docker Compose 未安裝"
        return 1
    fi
}

# 獲取 Docker Compose 命令
get_docker_compose_cmd() {
    if command_exists docker-compose; then
        echo "docker-compose"
    else
        echo "docker compose"
    fi
}

# 等待服務準備就緒
wait_for_service() {
    local service_name="$1"
    local check_command="$2"
    local max_attempts="${3:-30}"
    local sleep_time="${4:-2}"
    
    local attempt=1
    
    log_info "等待 $service_name 準備就緒..."
    
    while [ $attempt -le $max_attempts ]; do
        if eval "$check_command" >/dev/null 2>&1; then
            log_success "$service_name 已準備就緒"
            return 0
        fi
        
        echo -n "."
        sleep $sleep_time
        ((attempt++))
    done
    
    echo
    log_error "$service_name 啟動超時"
    return 1
}

# 確認操作
confirm_action() {
    local prompt="$1"
    local default="${2:-n}"
    
    if [ "$default" = "y" ]; then
        prompt="$prompt [Y/n]: "
    else
        prompt="$prompt [y/N]: "
    fi
    
    read -p "$prompt" response
    response=${response:-$default}
    
    case "$response" in
        [yY][eE][sS]|[yY])
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# 顯示進度條
show_progress() {
    local duration="$1"
    local message="$2"
    local elapsed=0
    
    while [ $elapsed -lt $duration ]; do
        printf "\r${message} [%-50s] %d%%" $(printf '#%.0s' $(seq 1 $((elapsed * 50 / duration)))) $((elapsed * 100 / duration))
        sleep 1
        ((elapsed++))
    done
    
    printf "\r${message} [%-50s] %d%%\n" $(printf '#%.0s' $(seq 1 50)) 100
}

# 檢查端口是否被佔用
is_port_in_use() {
    local port="$1"
    
    if command_exists netstat; then
        netstat -tuln 2>/dev/null | grep -q ":$port "
    elif command_exists ss; then
        ss -tuln 2>/dev/null | grep -q ":$port "
    elif command_exists lsof; then
        lsof -i ":$port" >/dev/null 2>&1
    else
        # 如果沒有可用的工具，嘗試使用 nc
        nc -z localhost "$port" 2>/dev/null
    fi
}

# 生成隨機密碼
generate_password() {
    local length="${1:-16}"
    
    if command_exists openssl; then
        openssl rand -base64 "$length" | tr -d "=+/" | cut -c1-"$length"
    else
        # 備用方案
        < /dev/urandom tr -dc 'a-zA-Z0-9!@#$%^&*' | head -c"$length"
    fi
}

# 檢查檔案是否存在並可讀
check_file_readable() {
    local file="$1"
    
    if [ ! -f "$file" ]; then
        log_error "檔案不存在: $file"
        return 1
    fi
    
    if [ ! -r "$file" ]; then
        log_error "檔案無法讀取: $file"
        return 1
    fi
    
    return 0
}

# 創建必要的目錄
ensure_directory() {
    local dir="$1"
    
    if [ ! -d "$dir" ]; then
        log_info "創建目錄: $dir"
        mkdir -p "$dir" || {
            log_error "無法創建目錄: $dir"
            return 1
        }
    fi
    
    return 0
}