#!/bin/bash
# translate.sh - Codex CLI 번역 래퍼
# smol.ai 한국어 뉴스 자동 발행 시스템
#
# 사용법: ./translate.sh <content_file> <has_headline> [output_file]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/config.sh"
source "$SCRIPT_DIR/../lib/logging.sh"

# 인자 확인
if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <content_file> <has_headline> [output_file]" >&2
    echo "  content_file: 번역할 원문 파일 경로" >&2
    echo "  has_headline: true 또는 false" >&2
    echo "  output_file: 출력 파일 경로 (옵션, 없으면 stdout)" >&2
    exit 1
fi

content_file="$1"
has_headline="$2"
output_file="${3:-}"

# 번역 출력 검증 함수
# 반환값: 0=성공, 1=실패
# 실패 시 stderr에 오류 메시지 출력
validate_translation_output() {
    local content="$1"
    local errors=()

    # 1. Frontmatter 존재 확인
    if ! echo "$content" | head -5 | grep -q "^---"; then
        errors+=("Frontmatter(---) 없음")
    fi

    # 2. summary 필드 확인 (필수)
    if ! echo "$content" | grep -q "^summary:"; then
        errors+=("summary 필드 없음")
    fi

    # 3. 최소 길이 확인 (50줄 미만이면 불완전)
    local line_count=$(echo "$content" | wc -l)
    if [[ $line_count -lt 50 ]]; then
        errors+=("콘텐츠가 너무 짧음 (${line_count}줄, 최소 50줄 필요)")
    fi

    # 4. 로컬 경로 참조 패턴 감지 (이번 버그의 직접 원인)
    if echo "$content" | grep -qE 'workspace/.*\.md|translated\.md|retranslated\.md|final\.md'; then
        errors+=("로컬 파일 경로 참조 감지 - 실제 번역이 아님")
    fi

    # 오류가 있으면 실패
    if [[ ${#errors[@]} -gt 0 ]]; then
        echo "TRANSLATION_VALIDATION_FAILED" >&2
        for err in "${errors[@]}"; do
            echo "  - $err" >&2
        done
        return 1
    fi
    return 0
}

# 파일 존재 확인
if [[ ! -f "$content_file" ]]; then
    log_error "Content file not found: $content_file"
    exit 1
fi

# 프롬프트 선택
if [[ "$has_headline" == "true" ]]; then
    prompt_file="$TRANSLATE_WITH_LINKS_PROMPT"
    log_info "Using prompt: translate-with-links.txt (headline day)"
else
    prompt_file="$TRANSLATE_NO_HEADLINE_PROMPT"
    log_info "Using prompt: translate-no-headline.txt (no headline)"
fi

# 프롬프트 파일 확인
if [[ ! -f "$prompt_file" ]]; then
    log_error "Prompt file not found: $prompt_file"
    exit 1
fi

# Codex CLI 확인
if [[ ! -x "$CODEX_BIN" ]]; then
    log_error "Codex CLI not found: $CODEX_BIN"
    exit 1
fi

log_info "Starting translation with Codex CLI"
log_info "Model: $CODEX_MODEL"
log_info "Reasoning Effort: $CODEX_REASONING_EFFORT"

# 임시 파일에 결합된 프롬프트 저장
temp_prompt=$(mktemp)
temp_last_message=$(mktemp)
temp_logs=$(mktemp)
trap 'rm -f "$temp_prompt" "$temp_last_message" "$temp_logs"' EXIT

cat "$prompt_file" > "$temp_prompt"
echo "" >> "$temp_prompt"
echo "## 원문 (아래 내용을 번역):" >> "$temp_prompt"
echo "" >> "$temp_prompt"
cat "$content_file" >> "$temp_prompt"

# Codex 실행 (마지막 메시지를 파일로 저장)
if ! "$CODEX_BIN" exec --full-auto \
    --skip-git-repo-check \
    --color never \
    -m "$CODEX_MODEL" \
    -c "reasoning_effort=\"$CODEX_REASONING_EFFORT\"" \
    --output-last-message "$temp_last_message" \
    - < "$temp_prompt" > "$temp_logs" 2>&1; then
    log_error "Codex translation failed"
    cat "$temp_logs" >&2
    exit 1
fi

# Codex가 ko.md 파일을 생성했는지 확인 (에이전트 모드 동작)
output_dir=$(dirname "$content_file")
ko_file="$output_dir/ko.md"

if [[ -f "$ko_file" ]]; then
    log_info "Codex created ko.md file, using that instead of last message"
    extracted_content=$(cat "$ko_file")
else
    # Codex 결과 정리: 불필요한 코드펜스(```)로 감싸진 경우 제거
    extracted_content=$(python3 - "$temp_last_message" <<'PY'
import sys

path = sys.argv[1]
text = open(path, "r", encoding="utf-8").read().strip()

lines = text.splitlines()
if lines and lines[0].lstrip().startswith("```") and lines[-1].strip() == "```":
    text = "\n".join(lines[1:-1]).strip()

sys.stdout.write(text + ("\n" if text and not text.endswith("\n") else ""))
PY
)
fi

# 출력 검증
if ! validate_translation_output "$extracted_content"; then
    log_error "번역 출력 검증 실패"
    # exit 2 = 검증 실패 (exit 1 = Codex 실행 실패와 구분)
    exit 2
fi

# 출력
if [[ -n "$output_file" ]]; then
    printf '%s' "$extracted_content" > "$output_file"
    log_success "Translation saved to: $output_file"
else
    printf '%s' "$extracted_content"
fi
