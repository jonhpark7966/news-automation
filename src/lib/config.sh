#!/bin/bash
# config.sh - 환경 설정
# smol.ai 한국어 뉴스 자동 발행 시스템

# 프로젝트 루트 디렉토리
_CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ROOT="$(cd "$_CONFIG_DIR/../.." && pwd)"

# 디렉토리 경로
export PROMPTS_DIR="$PROJECT_ROOT/prompts"
export DATA_DIR="$PROJECT_ROOT/data"
export OUTPUT_DIR="$PROJECT_ROOT/output"
export LOGS_DIR="$DATA_DIR/logs"
export CONFIG_DIR="$PROJECT_ROOT/config"

# 상태 파일
export PROCESSED_FILE="$DATA_DIR/processed.json"

# Web 레포지토리 경로
export WEB_REPO_PATH="${WEB_REPO_PATH:-/home/jonhpark/workspace/web}"
export AINEWS_CONTENT_PATH="$WEB_REPO_PATH/src/content/ainews"

# RSS 피드 URL
export RSS_FEED_URL="https://news.smol.ai/rss.xml"

# 모델 설정
export CODEX_MODEL="gpt-5.2"
export CODEX_REASONING_EFFORT="high"
export CLAUDE_MODEL="opus"

# CLI 경로
export CODEX_BIN="${CODEX_BIN:-/home/jonhpark/.npm-global/bin/codex}"
export CLAUDE_BIN="${CLAUDE_BIN:-/home/jonhpark/.local/bin/claude}"

# 재시도 설정
export MAX_RETRIES=3
export RETRY_DELAY=5

# 번역 검토 재시도
export MAX_REVIEW_RETRIES=1

# 프롬프트 파일
export TRANSLATE_WITH_LINKS_PROMPT="$PROMPTS_DIR/translate-with-links.txt"
export TRANSLATE_NO_HEADLINE_PROMPT="$PROMPTS_DIR/translate-no-headline.txt"
export REVIEW_LINKS_PROMPT="$PROMPTS_DIR/review-links.txt"

# 환경 변수 파일 로드 (존재하는 경우)
if [[ -f "$CONFIG_DIR/config.env" ]]; then
    source "$CONFIG_DIR/config.env"
fi

# 필수 디렉토리 생성
ensure_directories() {
    mkdir -p "$DATA_DIR" "$OUTPUT_DIR" "$LOGS_DIR"
}

# 필수 명령어 확인
check_dependencies() {
    local missing=()
    local review_mode="${REVIEW_MODE:-local}"

    if [[ ! -x "$CODEX_BIN" ]]; then
        missing+=("codex ($CODEX_BIN)")
    fi

    # Claude CLI는 REVIEW_MODE가 claude/auto일 때만 필수
    if [[ "$review_mode" != "local" ]]; then
        if [[ ! -x "$CLAUDE_BIN" ]]; then
            missing+=("claude ($CLAUDE_BIN)")
        fi
    fi

    if ! command -v python3 &> /dev/null; then
        missing+=("python3")
    fi

    if ! command -v gh &> /dev/null; then
        missing+=("gh (GitHub CLI)")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "ERROR: Missing dependencies: ${missing[*]}" >&2
        return 1
    fi

    return 0
}

# 프롬프트 파일 확인
check_prompts() {
    local missing=()

    for prompt in "$TRANSLATE_WITH_LINKS_PROMPT" "$TRANSLATE_NO_HEADLINE_PROMPT" "$REVIEW_LINKS_PROMPT"; do
        if [[ ! -f "$prompt" ]]; then
            missing+=("$prompt")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "ERROR: Missing prompt files: ${missing[*]}" >&2
        return 1
    fi

    return 0
}
