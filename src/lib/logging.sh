#!/bin/bash
# logging.sh - 로깅 유틸리티
# smol.ai 한국어 뉴스 자동 발행 시스템

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 레벨
LOG_LEVEL="${LOG_LEVEL:-INFO}"

# 현재 로그 파일
CURRENT_LOG_FILE=""

# 타임스탬프 생성
get_timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

# 로그 파일 초기화
init_log_file() {
    local slug="$1"
    local date_str=$(date '+%Y%m%d_%H%M%S')

    if [[ -n "$LOGS_DIR" ]]; then
        mkdir -p "$LOGS_DIR"
        CURRENT_LOG_FILE="$LOGS_DIR/${date_str}_${slug}.log"
        echo "=== News Automation Log ===" > "$CURRENT_LOG_FILE"
        echo "Started: $(get_timestamp)" >> "$CURRENT_LOG_FILE"
        echo "Slug: $slug" >> "$CURRENT_LOG_FILE"
        echo "===========================" >> "$CURRENT_LOG_FILE"
    fi
}

# 로그 메시지 기록
_log() {
    local level="$1"
    local message="$2"
    local timestamp=$(get_timestamp)
    local log_entry="[$timestamp] [$level] $message"

    # 파일에 기록
    if [[ -n "$CURRENT_LOG_FILE" ]]; then
        echo "$log_entry" >> "$CURRENT_LOG_FILE"
    fi

    # 콘솔에 출력
    echo "$log_entry"
}

# 로그 레벨별 함수
log_debug() {
    if [[ "$LOG_LEVEL" == "DEBUG" ]]; then
        _log "DEBUG" "$1"
    fi
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
    _log "INFO" "$1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    _log "SUCCESS" "$1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    _log "WARN" "$1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    _log "ERROR" "$1"
}

# 단계 시작 로깅
log_step() {
    local step_name="$1"
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}▶ $step_name${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    _log "STEP" "Starting: $step_name"
}

# 단계 완료 로깅
log_step_done() {
    local step_name="$1"
    echo -e "${GREEN}✓ $step_name 완료${NC}"
    _log "STEP" "Completed: $step_name"
}

# 진행 상황 표시
log_progress() {
    local current="$1"
    local total="$2"
    local message="$3"
    echo -e "  [${current}/${total}] $message"
}

# 구분선
log_separator() {
    echo "────────────────────────────────────────"
}

# 로그 파일 경로 반환
get_log_file() {
    echo "$CURRENT_LOG_FILE"
}

# 로그 종료
finalize_log() {
    local status="$1"
    if [[ -n "$CURRENT_LOG_FILE" ]]; then
        echo "===========================" >> "$CURRENT_LOG_FILE"
        echo "Finished: $(get_timestamp)" >> "$CURRENT_LOG_FILE"
        echo "Status: $status" >> "$CURRENT_LOG_FILE"
    fi
}
