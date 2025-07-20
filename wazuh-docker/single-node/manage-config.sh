#!/bin/bash

# Wazuh GraphRAG 配置管理腳本
# 版本: 1.0
# 描述: 集中管理所有配置文件和環境變數

set -e

# 載入共用函數庫
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common-functions.sh"

# 配置目錄
CONFIG_DIR="$SCRIPT_DIR/config"
ENV_FILE="$SCRIPT_DIR/.env"

# 顯示幫助信息
show_help() {
    echo "使用方法: $0 [命令] [選項]"
    echo
    echo "命令："
    echo "  init         初始化配置環境"
    echo "  validate     驗證配置文件的完整性"
    echo "  backup       備份當前配置"
    echo "  restore      恢復配置備份"
    echo "  update       更新配置到最新版本"
    echo "  show         顯示當前配置狀態"
    echo "  diff         顯示配置差異"
    echo
    echo "選項："
    echo "  -h, --help   顯示此幫助信息"
    echo "  -v, --verbose 詳細輸出"
    echo
    echo "範例："
    echo "  $0 init                    # 初始化配置"
    echo "  $0 validate                # 驗證配置"
    echo "  $0 backup --verbose        # 備份配置（詳細輸出）"
}

# 初始化配置環境
init_config() {
    log_info "初始化 Wazuh GraphRAG 配置環境..."
    
    # 創建必要的目錄
    mkdir -p "$CONFIG_DIR/backup"
    mkdir -p "$CONFIG_DIR/templates"
    
    # 檢查環境變數文件
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "$SCRIPT_DIR/env.example" ]; then
            log_info "創建環境變數文件..."
            cp "$SCRIPT_DIR/env.example" "$ENV_FILE"
            log_success "環境變數文件已創建: $ENV_FILE"
            log_warning "請編輯 $ENV_FILE 設定您的配置參數"
        else
            log_error "找不到 env.example 文件"
            return 1
        fi
    else
        log_info "環境變數文件已存在: $ENV_FILE"
    fi
    
    # 檢查 AI Agent 環境變數文件
    AI_AGENT_ENV="$SCRIPT_DIR/ai-agent-project/.env"
    if [ ! -f "$AI_AGENT_ENV" ]; then
        log_warning "AI Agent 環境變數文件不存在: $AI_AGENT_ENV"
        log_info "請確保已設定必要的 API 金鑰和配置參數"
    fi
    
    log_success "配置環境初始化完成"
}

# 驗證配置文件的完整性
validate_config() {
    log_info "驗證配置文件完整性..."
    
    local errors=0
    local warnings=0
    
    # 檢查必要的配置文件
    local required_files=(
        "docker-compose.main.yml"
        "docker-compose.override.yml"
        "ai-agent-project/requirements.txt"
        "ai-agent-project/requirements.lock.txt"
        "ai-agent-project/Dockerfile"
    )
    
    for file in "${required_files[@]}"; do
        if [ -f "$SCRIPT_DIR/$file" ]; then
            log_success "✓ $file"
        else
            log_error "✗ $file (缺失)"
            ((errors++))
        fi
    done
    
    # 檢查環境變數文件
    if [ -f "$ENV_FILE" ]; then
        log_success "✓ 環境變數文件存在"
        
        # 檢查必要的環境變數
        local required_vars=(
            "WAZUH_ADMIN_PASSWORD"
            "NEO4J_PASSWORD"
            "GRAFANA_ADMIN_PASSWORD"
        )
        
        for var in "${required_vars[@]}"; do
            if grep -q "^${var}=" "$ENV_FILE"; then
                log_success "✓ $var"
            else
                log_warning "⚠ $var (未設定)"
                ((warnings++))
            fi
        done
    else
        log_error "✗ 環境變數文件缺失"
        ((errors++))
    fi
    
    # 檢查 AI Agent 配置
    if [ -f "$SCRIPT_DIR/ai-agent-project/.env" ]; then
        log_success "✓ AI Agent 環境變數文件存在"
        
        # 檢查 AI Agent 必要的環境變數
        local ai_required_vars=(
            "GOOGLE_API_KEY"
            "ANTHROPIC_API_KEY"
            "NEO4J_URI"
            "OPENSEARCH_URL"
        )
        
        for var in "${ai_required_vars[@]}"; do
            if grep -q "^${var}=" "$SCRIPT_DIR/ai-agent-project/.env"; then
                log_success "✓ $var"
            else
                log_warning "⚠ $var (未設定)"
                ((warnings++))
            fi
        done
    else
        log_warning "⚠ AI Agent 環境變數文件缺失"
        ((warnings++))
    fi
    
    # 檢查 SSL 憑證
    if [ -d "$CONFIG_DIR/wazuh_indexer_ssl_certs" ]; then
        log_success "✓ SSL 憑證目錄存在"
    else
        log_warning "⚠ SSL 憑證目錄缺失，可能需要生成憑證"
        ((warnings++))
    fi
    
    # 顯示驗證結果
    echo
    if [ $errors -eq 0 ] && [ $warnings -eq 0 ]; then
        log_success "🎉 所有配置驗證通過！"
        return 0
    elif [ $errors -eq 0 ]; then
        log_warning "⚠ 配置驗證完成，發現 $warnings 個警告"
        return 0
    else
        log_error "❌ 配置驗證失敗，發現 $errors 個錯誤，$warnings 個警告"
        return 1
    fi
}

# 備份當前配置
backup_config() {
    local backup_dir="$CONFIG_DIR/backup/$(date +%Y%m%d_%H%M%S)"
    log_info "備份配置到: $backup_dir"
    
    mkdir -p "$backup_dir"
    
    # 備份環境變數文件
    if [ -f "$ENV_FILE" ]; then
        cp "$ENV_FILE" "$backup_dir/"
        log_success "✓ 環境變數文件已備份"
    fi
    
    # 備份 AI Agent 環境變數文件
    if [ -f "$SCRIPT_DIR/ai-agent-project/.env" ]; then
        cp "$SCRIPT_DIR/ai-agent-project/.env" "$backup_dir/"
        log_success "✓ AI Agent 環境變數文件已備份"
    fi
    
    # 備份 Docker Compose 文件
    cp "$SCRIPT_DIR/docker-compose.main.yml" "$backup_dir/" 2>/dev/null || true
    cp "$SCRIPT_DIR/docker-compose.override.yml" "$backup_dir/" 2>/dev/null || true
    log_success "✓ Docker Compose 文件已備份"
    
    # 備份依賴文件
    cp "$SCRIPT_DIR/ai-agent-project/requirements.txt" "$backup_dir/" 2>/dev/null || true
    cp "$SCRIPT_DIR/ai-agent-project/requirements.lock.txt" "$backup_dir/" 2>/dev/null || true
    log_success "✓ 依賴文件已備份"
    
    log_success "配置備份完成: $backup_dir"
}

# 恢復配置備份
restore_config() {
    local backup_dir="$1"
    
    if [ -z "$backup_dir" ]; then
        log_error "請指定備份目錄"
        echo "可用的備份："
        ls -1 "$CONFIG_DIR/backup/" 2>/dev/null || echo "沒有找到備份"
        return 1
    fi
    
    if [ ! -d "$CONFIG_DIR/backup/$backup_dir" ]; then
        log_error "備份目錄不存在: $backup_dir"
        return 1
    fi
    
    log_info "從備份恢復配置: $backup_dir"
    
    # 恢復環境變數文件
    if [ -f "$CONFIG_DIR/backup/$backup_dir/.env" ]; then
        cp "$CONFIG_DIR/backup/$backup_dir/.env" "$ENV_FILE"
        log_success "✓ 環境變數文件已恢復"
    fi
    
    # 恢復 AI Agent 環境變數文件
    if [ -f "$CONFIG_DIR/backup/$backup_dir/ai-agent-project/.env" ]; then
        cp "$CONFIG_DIR/backup/$backup_dir/ai-agent-project/.env" "$SCRIPT_DIR/ai-agent-project/.env"
        log_success "✓ AI Agent 環境變數文件已恢復"
    fi
    
    log_success "配置恢復完成"
}

# 顯示當前配置狀態
show_config() {
    log_info "當前配置狀態："
    echo
    
    # 顯示環境變數文件狀態
    if [ -f "$ENV_FILE" ]; then
        echo "📄 環境變數文件: $ENV_FILE"
        echo "   大小: $(du -h "$ENV_FILE" | cut -f1)"
        echo "   修改時間: $(stat -c %y "$ENV_FILE" 2>/dev/null || stat -f %Sm "$ENV_FILE" 2>/dev/null || echo "未知")"
        echo
    else
        echo "❌ 環境變數文件: 缺失"
        echo
    fi
    
    # 顯示 AI Agent 配置狀態
    if [ -f "$SCRIPT_DIR/ai-agent-project/.env" ]; then
        echo "🤖 AI Agent 配置: $SCRIPT_DIR/ai-agent-project/.env"
        echo "   大小: $(du -h "$SCRIPT_DIR/ai-agent-project/.env" | cut -f1)"
        echo
    else
        echo "⚠ AI Agent 配置: 缺失"
        echo
    fi
    
    # 顯示備份狀態
    local backup_count=$(ls -1 "$CONFIG_DIR/backup/" 2>/dev/null | wc -l)
    echo "💾 配置備份: $backup_count 個"
    if [ $backup_count -gt 0 ]; then
        echo "   最新備份: $(ls -1t "$CONFIG_DIR/backup/" 2>/dev/null | head -1)"
    fi
    echo
}

# 主要函數
main() {
    case "${1:-}" in
        init)
            init_config
            ;;
        validate)
            validate_config
            ;;
        backup)
            backup_config
            ;;
        restore)
            restore_config "$2"
            ;;
        show)
            show_config
            ;;
        -h|--help)
            show_help
            ;;
        *)
            log_error "未知命令: $1"
            echo
            show_help
            exit 1
            ;;
    esac
}

# 如果直接執行此腳本
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 