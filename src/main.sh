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

# 파이프라인 경고/실패 추적 (PR 본문에 표시용)
PIPELINE_WARNINGS=()

# final.md 검증 함수
validate_final_markdown() {
    local file="$1"
    local errors=()

    if [[ ! -f "$file" ]]; then
        errors+=("파일이 존재하지 않음")
    else
        local content=$(cat "$file")

        # Frontmatter 확인
        if ! echo "$content" | head -5 | grep -q "^---"; then
            errors+=("Frontmatter 없음")
        fi

        # summary 필드 확인
        if ! echo "$content" | grep -q "^summary:"; then
            errors+=("summary 필드 없음")
        fi

        # 최소 길이 확인
        local line_count=$(echo "$content" | wc -l)
        if [[ $line_count -lt 50 ]]; then
            errors+=("콘텐츠가 너무 짧음 (${line_count}줄)")
        fi

        # 로컬 경로 참조 감지
        if echo "$content" | grep -qE 'workspace/.*\.md|translated\.md|retranslated\.md'; then
            errors+=("로컬 파일 경로 참조 감지")
        fi
    fi

    if [[ ${#errors[@]} -gt 0 ]]; then
        for err in "${errors[@]}"; do
            echo "$err"
        done
        return 1
    fi
    return 0
}

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
    log_step "GitHub 소스 확인"

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

# URL에서 slug 추출 (GitHub raw URL 또는 smol.ai URL 모두 지원)
SLUG=$(basename "$TARGET_URL" .md)
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
        PIPELINE_WARNINGS+=("리뷰 실패: 재번역 시도")

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

        retranslate_exit_code=0
        "$SCRIPT_DIR/translate/translate.sh" "$WORK_DIR/original_with_feedback.md" "$HAS_HEADLINE" "$RETRANSLATED_FILE" || retranslate_exit_code=$?

        if [[ $retranslate_exit_code -ne 0 ]]; then
            log_warn "Re-translation failed (exit code: $retranslate_exit_code). Using original translation."
            PIPELINE_WARNINGS+=("재번역 실패: 원본 번역 사용")
            # 재번역 실패 시 원본 번역 유지 (TRANSLATED_FILE 변경 없음)
        else
            # 재번역 성공 시 검토
            review_result2=$("$SCRIPT_DIR/review/review.sh" "$ORIGINAL_FILE" "$RETRANSLATED_FILE" 2>&1) || true

            if echo "$review_result2" | grep -q "^PASS"; then
                log_success "Re-translation passed review!"
                TRANSLATED_FILE="$RETRANSLATED_FILE"
            else
                log_warn "Re-translation also failed review. Comparing translations..."
                PIPELINE_WARNINGS+=("재번역도 리뷰 실패")

                # 재번역이 유효한지 검증
                retrans_validation=$(validate_final_markdown "$RETRANSLATED_FILE" 2>&1) || true
                orig_validation=$(validate_final_markdown "$TRANSLATED_FILE" 2>&1) || true

                if [[ -z "$retrans_validation" ]]; then
                    log_info "Re-translation is valid, using it."
                    TRANSLATED_FILE="$RETRANSLATED_FILE"
                elif [[ -z "$orig_validation" ]]; then
                    log_info "Original translation is valid, keeping it."
                    PIPELINE_WARNINGS+=("원본 번역 사용 (재번역 검증 실패)")
                else
                    log_warn "Both translations have issues. Using original."
                    PIPELINE_WARNINGS+=("원본 번역 사용 (둘 다 검증 실패)")
                fi
            fi
        fi
    fi

    log_step_done "Claude Code 검토"
else
    log_info "Skipping review step"
fi

# Step 4: 최종 마크다운 생성
log_step "Step 4: 최종 마크다운 생성"
FINAL_FILE="$WORK_DIR/final.md"

# GitHub raw URL을 blob URL로 변환 (원문보기 링크용)
ORIGINAL_URL="$TARGET_URL"
if [[ "$TARGET_URL" == *"raw.githubusercontent.com"* ]]; then
    ORIGINAL_URL=$(echo "$TARGET_URL" | sed 's|raw.githubusercontent.com/\([^/]*/[^/]*\)/\([^/]*\)/|github.com/\1/blob/\2/|')
fi

python3 "$SCRIPT_DIR/generate/generate_markdown.py" "$TRANSLATED_FILE" \
    -o "$FINAL_FILE" \
    --original-url "$ORIGINAL_URL" || {
    log_error "Markdown generation failed"
    python3 "$SCRIPT_DIR/state/state_manager.py" mark "$SLUG" --status failed --error "Markdown generation failed"
    exit 1
}

# final.md 검증
final_validation=$(validate_final_markdown "$FINAL_FILE" 2>&1) || true
if [[ -n "$final_validation" ]]; then
    log_warn "Final markdown validation failed: $final_validation"
    PIPELINE_WARNINGS+=("최종 마크다운 검증 실패: $final_validation")

    # 원본 translated.md가 유효하면 그걸로 대체
    ORIGINAL_TRANSLATED="$WORK_DIR/translated.md"
    orig_validation=$(validate_final_markdown "$ORIGINAL_TRANSLATED" 2>&1) || true

    if [[ -z "$orig_validation" ]]; then
        log_info "Using original translated.md as final.md"
        cp "$ORIGINAL_TRANSLATED" "$FINAL_FILE"
        PIPELINE_WARNINGS+=("원본 번역으로 대체함")
    else
        log_warn "Original translation also invalid. Proceeding with best effort."
        PIPELINE_WARNINGS+=("원본도 검증 실패 - 최선의 결과로 진행")
    fi
fi

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

    # 경고 정보를 환경변수로 전달
    WARNINGS_FILE="$WORK_DIR/pipeline_warnings.txt"
    if [[ ${#PIPELINE_WARNINGS[@]} -gt 0 ]]; then
        printf '%s\n' "${PIPELINE_WARNINGS[@]}" > "$WARNINGS_FILE"
        log_warn "Pipeline had ${#PIPELINE_WARNINGS[@]} warning(s)"
    else
        rm -f "$WARNINGS_FILE"
    fi

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
