#!/bin/bash
# main.sh - 메인 오케스트레이터
# smol.ai 한국어 뉴스 자동 발행 시스템
#
# 사용법:
#   ./main.sh                    # 새 이슈 자동 감지 및 처리
#   ./main.sh --url <URL>        # 특정 URL 처리
#   ./main.sh --check            # 새 이슈 확인만
#   ./main.sh --dry-run          # PR 생성 없이 실행

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/config.sh"
source "$SCRIPT_DIR/lib/logging.sh"
source "$SCRIPT_DIR/lib/notify.sh"

# 기본값
DRY_RUN=false
CHECK_ONLY=false
TARGET_URL=""
SKIP_REVIEW=false

# 인자 파싱
while [[ $# -gt 0 ]]; do
    case $1 in
        --url)
            TARGET_URL="$2"
            shift 2
            ;;
        --check)
            CHECK_ONLY=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-review)
            SKIP_REVIEW=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --url <URL>      특정 URL 처리"
            echo "  --check          새 이슈 확인만"
            echo "  --dry-run        PR 생성 없이 실행"
            echo "  --skip-review    리뷰 단계 건너뛰기"
            echo "  -h, --help       도움말 표시"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# 의존성 확인
ensure_directories
if ! check_dependencies; then
    log_error "Missing dependencies. Please install required tools."
    exit 1
fi

if ! check_prompts; then
    log_error "Missing prompt files. Please check prompts directory."
    exit 1
fi

# 새 이슈 확인 (URL이 지정되지 않은 경우)
if [[ -z "$TARGET_URL" ]]; then
    log_step "RSS 피드 확인"

    new_issue=$(python3 "$SCRIPT_DIR/rss/check_feed.py" --check --limit 1 --json)

    if [[ -z "$new_issue" ]] || [[ "$new_issue" == "[]" ]]; then
        log_info "No new issues found."
        exit 0
    fi

    TARGET_URL=$(echo "$new_issue" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data[0]['url'] if data else '')")

    if [[ -z "$TARGET_URL" ]]; then
        log_info "No new issues to process."
        exit 0
    fi

    log_info "Found new issue: $TARGET_URL"
fi

if [[ "$CHECK_ONLY" == "true" ]]; then
    log_info "Check only mode. Exiting."
    exit 0
fi

# URL에서 slug 추출
SLUG=$(echo "$TARGET_URL" | sed -n 's|.*/issues/\([^/]*\)/\?$|\1|p')
if [[ -z "$SLUG" ]]; then
    SLUG=$(basename "$TARGET_URL")
fi

# 로그 초기화
init_log_file "$SLUG"

log_info "Processing: $SLUG"
log_info "URL: $TARGET_URL"

# 작업 디렉토리 생성
WORK_DIR="$OUTPUT_DIR/$SLUG"
mkdir -p "$WORK_DIR"

# 상태 업데이트: 진행 중
python3 "$SCRIPT_DIR/state/state_manager.py" mark "$SLUG" --status in_progress

# Step 1: 페이지 크롤링
log_step "Step 1: 페이지 크롤링"
ORIGINAL_FILE="$WORK_DIR/original.md"

crawl_exit_code=0
python3 "$SCRIPT_DIR/crawler/fetch_page.py" "$TARGET_URL" -o "$ORIGINAL_FILE" || crawl_exit_code=$?

if [[ $crawl_exit_code -eq 2 ]]; then
    # Exit code 2 = 검증 실패 (사이트 구조 변경 가능성)
    log_error "Content validation failed - site structure may have changed!"
    notify_validation_failure "$TARGET_URL" "Content validation failed. The smol.ai site structure may have changed."
    python3 "$SCRIPT_DIR/state/state_manager.py" mark "$SLUG" --status failed --error "Validation failed - site structure changed"
    exit 1
elif [[ $crawl_exit_code -ne 0 ]]; then
    log_error "Failed to fetch page"
    notify_crawler_failure "$TARGET_URL" "HTTP or network error during crawling"
    python3 "$SCRIPT_DIR/state/state_manager.py" mark "$SLUG" --status failed --error "Crawling failed"
    exit 1
fi

# 메타데이터 추출
metadata_json=$(python3 "$SCRIPT_DIR/crawler/fetch_page.py" "$TARGET_URL" --json)
HAS_HEADLINE=$(echo "$metadata_json" | python3 -c "import sys, json; print(str(json.load(sys.stdin)['metadata']['has_headline']).lower())")

log_info "Has headline: $HAS_HEADLINE"
log_step_done "페이지 크롤링"

# Step 2: Codex로 번역
log_step "Step 2: Codex CLI 번역"
TRANSLATED_FILE="$WORK_DIR/translated.md"

"$SCRIPT_DIR/translate/translate.sh" "$ORIGINAL_FILE" "$HAS_HEADLINE" "$TRANSLATED_FILE" || {
    log_error "Translation failed"
    notify_translation_failure "$SLUG" "Codex CLI translation failed"
    python3 "$SCRIPT_DIR/state/state_manager.py" mark "$SLUG" --status failed --error "Translation failed"
    exit 1
}

log_step_done "Codex CLI 번역"

# Step 3: Claude로 검토
if [[ "$SKIP_REVIEW" != "true" ]]; then
    log_step "Step 3: Claude Code 검토"

    review_result=$("$SCRIPT_DIR/review/review.sh" "$ORIGINAL_FILE" "$TRANSLATED_FILE" 2>&1) || true

    if echo "$review_result" | grep -q "^PASS"; then
        log_success "Review passed!"
    else
        log_warn "Review failed. Attempting re-translation..."

        # 피드백을 포함하여 재번역 시도
        FEEDBACK_FILE="$WORK_DIR/feedback.txt"
        echo "$review_result" > "$FEEDBACK_FILE"

        # 재번역 (피드백 포함)
        RETRANSLATED_FILE="$WORK_DIR/retranslated.md"

        # 피드백을 원문에 추가
        cat "$ORIGINAL_FILE" > "$WORK_DIR/original_with_feedback.md"
        echo "" >> "$WORK_DIR/original_with_feedback.md"
        echo "## 이전 번역 피드백 (이 문제를 수정해주세요):" >> "$WORK_DIR/original_with_feedback.md"
        echo "$review_result" >> "$WORK_DIR/original_with_feedback.md"

        "$SCRIPT_DIR/translate/translate.sh" "$WORK_DIR/original_with_feedback.md" "$HAS_HEADLINE" "$RETRANSLATED_FILE" || {
            log_error "Re-translation failed"
            python3 "$SCRIPT_DIR/state/state_manager.py" mark "$SLUG" --status failed --error "Re-translation failed"
            exit 1
        }

        # 재검토
        review_result2=$("$SCRIPT_DIR/review/review.sh" "$ORIGINAL_FILE" "$RETRANSLATED_FILE" 2>&1) || true

        if echo "$review_result2" | grep -q "^PASS"; then
            log_success "Re-translation passed review!"
            TRANSLATED_FILE="$RETRANSLATED_FILE"
        else
            log_warn "Re-translation also failed review. Proceeding with best effort."
            # 두 번째 번역이 더 나을 수 있으므로 사용
            TRANSLATED_FILE="$RETRANSLATED_FILE"
        fi
    fi

    log_step_done "Claude Code 검토"
else
    log_info "Skipping review step"
fi

# Step 4: 최종 마크다운 생성
log_step "Step 4: 최종 마크다운 생성"
FINAL_FILE="$WORK_DIR/final.md"

python3 "$SCRIPT_DIR/generate/generate_markdown.py" "$TRANSLATED_FILE" \
    -o "$FINAL_FILE" \
    --original-url "$TARGET_URL" || {
    log_error "Markdown generation failed"
    python3 "$SCRIPT_DIR/state/state_manager.py" mark "$SLUG" --status failed --error "Markdown generation failed"
    exit 1
}

log_step_done "최종 마크다운 생성"

# Step 5: YouTube 템플릿 생성
log_step "Step 5: YouTube 템플릿 생성"
YOUTUBE_FILE="$WORK_DIR/youtube.txt"

python3 "$SCRIPT_DIR/generate/generate_youtube.py" "$FINAL_FILE" \
    -o "$YOUTUBE_FILE" \
    --original-url "$TARGET_URL" || {
    log_warn "YouTube template generation failed (non-critical)"
}

log_step_done "YouTube 템플릿 생성"

# Step 6: PR 생성
if [[ "$DRY_RUN" == "true" ]]; then
    log_info "Dry run mode. Skipping PR creation."
    log_info "Output files:"
    log_info "  - Original: $ORIGINAL_FILE"
    log_info "  - Translated: $TRANSLATED_FILE"
    log_info "  - Final: $FINAL_FILE"
    log_info "  - YouTube: $YOUTUBE_FILE"

    python3 "$SCRIPT_DIR/state/state_manager.py" mark "$SLUG" --status success
else
    log_step "Step 6: PR 생성"

    pr_output=$("$SCRIPT_DIR/publish/create_pr.sh" "$SLUG" "$WORK_DIR" 2>&1) || {
        log_error "PR creation failed"
        python3 "$SCRIPT_DIR/state/state_manager.py" mark "$SLUG" --status failed --error "PR creation failed"
        exit 1
    }

    # PR URL만 추출 (마지막 줄에서 https://로 시작하는 URL)
    pr_url=$(echo "$pr_output" | grep -oE 'https://github\.com/[^ ]+' | tail -1)

    log_success "PR created: $pr_url"
    notify_pr_created "$SLUG" "$pr_url"
    python3 "$SCRIPT_DIR/state/state_manager.py" mark "$SLUG" --status success --pr-url "$pr_url"

    log_step_done "PR 생성"
fi

# 완료
log_separator
log_success "Pipeline completed successfully!"
log_info "Slug: $SLUG"
log_info "Work directory: $WORK_DIR"

finalize_log "success"
