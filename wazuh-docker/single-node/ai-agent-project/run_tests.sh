#!/bin/bash

# Wazuh GraphRAG AI Agent 測試運行腳本
# 提供不同類型的測試執行選項

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# 顯示幫助信息
show_help() {
    echo "使用方法: $0 [選項]"
    echo
    echo "選項："
    echo "  unit             執行單元測試"
    echo "  integration      執行整合測試"
    echo "  all              執行所有測試"
    echo "  coverage         執行覆蓋率測試"
    echo "  performance      執行效能測試"
    echo "  quick            快速測試（僅單元測試）"
    echo "  ci               CI/CD 環境測試"
    echo "  clean            清理測試緩存"
    echo "  report           生成測試報告"
    echo "  -h, --help       顯示此幫助信息"
    echo
    echo "範例："
    echo "  $0 unit                    # 執行單元測試"
    echo "  $0 integration             # 執行整合測試"
    echo "  $0 coverage                # 執行覆蓋率測試"
    echo "  $0 ci                      # CI/CD 測試"
    echo "  $0 clean                   # 清理緩存"
}

# 檢查依賴
check_dependencies() {
    log_info "檢查測試依賴..."
    
    # 檢查 Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 未安裝"
        exit 1
    fi
    
    # 檢查 pytest
    if ! python3 -c "import pytest" &> /dev/null; then
        log_error "pytest 未安裝，請執行: pip install pytest pytest-cov pytest-asyncio"
        exit 1
    fi
    
    # 檢查 pytest-cov
    if ! python3 -c "import pytest_cov" &> /dev/null; then
        log_error "pytest-cov 未安裝，請執行: pip install pytest-cov"
        exit 1
    fi
    
    log_success "所有依賴檢查通過"
}

# 清理測試緩存
clean_test_cache() {
    log_info "清理測試緩存..."
    
    # 清理 pytest 緩存
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type f -name "*.pyo" -delete 2>/dev/null || true
    
    # 清理覆蓋率報告
    rm -rf htmlcov/ 2>/dev/null || true
    rm -rf .coverage 2>/dev/null || true
    rm -rf coverage.xml 2>/dev/null || true
    
    # 清理測試日誌
    rm -rf test_logs/ 2>/dev/null || true
    
    log_success "測試緩存清理完成"
}

# 執行單元測試
run_unit_tests() {
    log_info "執行單元測試..."
    
    python3 -m pytest tests/ -m "unit" \
        --tb=short \
        --strict-markers \
        --disable-warnings \
        --durations=10 \
        -v
    
    if [ $? -eq 0 ]; then
        log_success "單元測試通過"
    else
        log_error "單元測試失敗"
        exit 1
    fi
}

# 執行整合測試
run_integration_tests() {
    log_info "執行整合測試..."
    
    python3 -m pytest tests/ -m "integration" \
        --tb=short \
        --strict-markers \
        --disable-warnings \
        --durations=10 \
        -v
    
    if [ $? -eq 0 ]; then
        log_success "整合測試通過"
    else
        log_error "整合測試失敗"
        exit 1
    fi
}

# 執行覆蓋率測試
run_coverage_tests() {
    log_info "執行覆蓋率測試..."
    
    # 創建測試日誌目錄
    mkdir -p test_logs
    
    python3 -m pytest tests/ \
        --cov=app \
        --cov-report=html:htmlcov \
        --cov-report=term-missing \
        --cov-report=xml \
        --cov-fail-under=80 \
        --cov-branch \
        --tb=short \
        --strict-markers \
        --disable-warnings \
        --durations=10 \
        -v \
        --junitxml=test_logs/junit.xml
    
    if [ $? -eq 0 ]; then
        log_success "覆蓋率測試通過"
        log_info "覆蓋率報告已生成: htmlcov/index.html"
    else
        log_error "覆蓋率測試失敗"
        exit 1
    fi
}

# 執行效能測試
run_performance_tests() {
    log_info "執行效能測試..."
    
    python3 -m pytest tests/ -m "performance" \
        --tb=short \
        --strict-markers \
        --disable-warnings \
        --durations=10 \
        -v
    
    if [ $? -eq 0 ]; then
        log_success "效能測試通過"
    else
        log_error "效能測試失敗"
        exit 1
    fi
}

# 執行所有測試
run_all_tests() {
    log_info "執行所有測試..."
    
    # 創建測試日誌目錄
    mkdir -p test_logs
    
    python3 -m pytest tests/ \
        --cov=app \
        --cov-report=html:htmlcov \
        --cov-report=term-missing \
        --cov-report=xml \
        --cov-fail-under=80 \
        --cov-branch \
        --tb=short \
        --strict-markers \
        --disable-warnings \
        --durations=10 \
        -v \
        --junitxml=test_logs/junit.xml
    
    if [ $? -eq 0 ]; then
        log_success "所有測試通過"
        log_info "覆蓋率報告已生成: htmlcov/index.html"
    else
        log_error "測試失敗"
        exit 1
    fi
}

# 執行快速測試
run_quick_tests() {
    log_info "執行快速測試（僅單元測試）..."
    
    python3 -m pytest tests/ -m "unit and not slow" \
        --tb=short \
        --strict-markers \
        --disable-warnings \
        --durations=5 \
        -v
    
    if [ $? -eq 0 ]; then
        log_success "快速測試通過"
    else
        log_error "快速測試失敗"
        exit 1
    fi
}

# 執行 CI/CD 測試
run_ci_tests() {
    log_info "執行 CI/CD 測試..."
    
    # 創建測試日誌目錄
    mkdir -p test_logs
    
    # 執行測試並生成報告
    python3 -m pytest tests/ \
        --cov=app \
        --cov-report=xml \
        --cov-report=term-missing \
        --cov-fail-under=80 \
        --tb=short \
        --strict-markers \
        --disable-warnings \
        --durations=10 \
        -v \
        --junitxml=test_logs/junit.xml \
        --maxfail=3
    
    if [ $? -eq 0 ]; then
        log_success "CI/CD 測試通過"
        
        # 顯示覆蓋率摘要
        echo
        log_info "覆蓋率摘要："
        python3 -m coverage report --show-missing
    else
        log_error "CI/CD 測試失敗"
        exit 1
    fi
}

# 生成測試報告
generate_test_report() {
    log_info "生成測試報告..."
    
    if [ ! -f "test_logs/junit.xml" ]; then
        log_warning "未找到測試結果文件，請先執行測試"
        return 1
    fi
    
    # 創建報告目錄
    mkdir -p reports
    
    # 生成 HTML 報告
    if command -v junit2html &> /dev/null; then
        junit2html test_logs/junit.xml reports/test_report.html
        log_success "測試報告已生成: reports/test_report.html"
    else
        log_warning "junit2html 未安裝，跳過 HTML 報告生成"
    fi
    
    # 顯示測試摘要
    echo
    log_info "測試摘要："
    python3 -c "
import xml.etree.ElementTree as ET
try:
    tree = ET.parse('test_logs/junit.xml')
    root = tree.getroot()
    testsuites = root.findall('.//testsuite')
    total_tests = sum(int(ts.get('tests', 0)) for ts in testsuites)
    total_failures = sum(int(ts.get('failures', 0)) for ts in testsuites)
    total_errors = sum(int(ts.get('errors', 0)) for ts in testsuites)
    print(f'總測試數: {total_tests}')
    print(f'失敗數: {total_failures}')
    print(f'錯誤數: {total_errors}')
    print(f'成功率: {((total_tests - total_failures - total_errors) / total_tests * 100):.1f}%')
except Exception as e:
    print(f'無法解析測試結果: {e}')
"
}

# 主要函數
main() {
    case "${1:-}" in
        unit)
            check_dependencies
            run_unit_tests
            ;;
        integration)
            check_dependencies
            run_integration_tests
            ;;
        all)
            check_dependencies
            run_all_tests
            ;;
        coverage)
            check_dependencies
            run_coverage_tests
            ;;
        performance)
            check_dependencies
            run_performance_tests
            ;;
        quick)
            check_dependencies
            run_quick_tests
            ;;
        ci)
            check_dependencies
            run_ci_tests
            ;;
        clean)
            clean_test_cache
            ;;
        report)
            generate_test_report
            ;;
        -h|--help)
            show_help
            ;;
        *)
            log_error "未知選項: $1"
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