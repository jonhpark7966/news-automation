#!/bin/bash
# review.sh - Claude Code 검토 래퍼
# smol.ai 한국어 뉴스 자동 발행 시스템
#
# 사용법: ./review.sh <original_file> <translated_file>
# 반환: PASS 또는 FAIL: <이유>

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/config.sh"
source "$SCRIPT_DIR/../lib/logging.sh"

# REVIEW_MODE:
# - local (default): 오프라인 정적 검증
# - claude: Claude CLI로 LLM 검토
# - auto: Claude 시도 후 실패 시 local로 폴백
REVIEW_MODE="${REVIEW_MODE:-local}"

# 인자 확인
if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <original_file> <translated_file>" >&2
    echo "  original_file: 원문 파일 경로" >&2
    echo "  translated_file: 번역본 파일 경로" >&2
    exit 1
fi

original_file="$1"
translated_file="$2"

# 파일 존재 확인
if [[ ! -f "$original_file" ]]; then
    log_error "Original file not found: $original_file"
    exit 1
fi

if [[ ! -f "$translated_file" ]]; then
    log_error "Translated file not found: $translated_file"
    exit 1
fi

run_local_review() {
    log_info "Starting local (offline) review"
    python3 "$SCRIPT_DIR/local_review.py" --original "$original_file" --translated "$translated_file"
}

run_claude_review() {
    # 프롬프트 파일 확인
    if [[ ! -f "$REVIEW_LINKS_PROMPT" ]]; then
        log_error "Review prompt not found: $REVIEW_LINKS_PROMPT"
        exit 1
    fi

    # Claude CLI 확인
    if [[ ! -x "$CLAUDE_BIN" ]]; then
        log_error "Claude CLI not found: $CLAUDE_BIN"
        exit 1
    fi

    log_info "Starting review with Claude CLI"
    log_info "Model: $CLAUDE_MODEL"

    # 임시 파일에 결합된 프롬프트 저장 (argv 길이 제한 회피)
    temp_prompt=$(mktemp)
    trap 'rm -f "$temp_prompt"' EXIT

    # 프롬프트 템플릿의 placeholder({original_content}, {translated_content})를 치환해 최종 프롬프트 생성
    python3 - "$REVIEW_LINKS_PROMPT" "$original_file" "$translated_file" > "$temp_prompt" <<'PY'
import sys

prompt_path, original_path, translated_path = sys.argv[1:4]

with open(prompt_path, "r", encoding="utf-8") as f:
    prompt = f.read()
with open(original_path, "r", encoding="utf-8") as f:
    original = f.read()
with open(translated_path, "r", encoding="utf-8") as f:
    translated = f.read()

if "{original_content}" in prompt or "{translated_content}" in prompt:
    prompt = prompt.replace("{original_content}", original).replace("{translated_content}", translated)
else:
    prompt = (
        prompt
        + "\n\n### 원문:\n"
        + original
        + "\n\n### 번역본:\n"
        + translated
    )

sys.stdout.write(prompt)
PY

    # Claude 실행 (stdin으로 프롬프트 전달)
    result=$("$CLAUDE_BIN" --print --model "$CLAUDE_MODEL" < "$temp_prompt" 2>&1) || {
        log_error "Claude review failed"
        echo "$result" >&2
        return 2
    }

    # 결과 파싱
    if echo "$result" | grep -q "^PASS"; then
        log_success "Review passed!"
        echo "PASS"
        return 0
    else
        log_warn "Review failed"
        echo "$result"
        return 1
    fi
}

case "$REVIEW_MODE" in
    local)
        run_local_review
        ;;
    claude)
        run_claude_review
        ;;
    auto)
        # Claude를 먼저 시도하고, 실패/비정상 출력이면 local로 폴백
        if claude_out="$(run_claude_review 2>&1)"; then
            echo "$claude_out"
            exit 0
        else
            # Claude가 FAIL을 준 경우(정상 출력) 그대로 반환, 그 외에는 local로 폴백
            if echo "$claude_out" | grep -qE "^(PASS|FAIL:)"; then
                echo "$claude_out"
                exit 1
            fi

            run_local_review
        fi
        ;;
    *)
        log_error "Unknown REVIEW_MODE: $REVIEW_MODE (expected: local|claude|auto)"
        exit 1
        ;;
esac
