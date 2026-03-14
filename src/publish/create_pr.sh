#!/bin/bash
# create_pr.sh - PR 생성 워크플로우
# smol.ai 한국어 뉴스 자동 발행 시스템
#
# 사용법: ./create_pr.sh <slug> <work_dir>

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/config.sh"
source "$SCRIPT_DIR/../lib/logging.sh"

# 인자 확인
if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <slug> <work_dir>" >&2
    exit 1
fi

SLUG="$1"
WORK_DIR="$2"

# 파일 확인
FINAL_FILE="$WORK_DIR/final.md"
YOUTUBE_FILE="$WORK_DIR/youtube.txt"

if [[ ! -f "$FINAL_FILE" ]]; then
    log_error "Final markdown file not found: $FINAL_FILE"
    exit 1
fi

# Web 레포 확인
if [[ ! -d "$WEB_REPO_PATH" ]]; then
    log_error "Web repository not found: $WEB_REPO_PATH"
    exit 1
fi

# Web 레포로 이동
cd "$WEB_REPO_PATH"

# 현재 브랜치 저장
ORIGINAL_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# main 브랜치로 전환 및 최신화
log_info "Switching to main branch..."
git checkout main
git pull origin main

# 새 브랜치 생성
DATE_PREFIX=$(date +%Y%m%d)
BRANCH_NAME="ainews/${DATE_PREFIX}-${SLUG}"

log_info "Creating branch: $BRANCH_NAME"
git checkout -b "$BRANCH_NAME" 2>/dev/null || {
    # 브랜치가 이미 존재하면 삭제 후 재생성
    git checkout main
    git branch -D "$BRANCH_NAME" 2>/dev/null || true
    git checkout -b "$BRANCH_NAME"
}

# 파일 복사
AINEWS_KO_DIR="$AINEWS_CONTENT_PATH/ko"
AINEWS_YOUTUBE_DIR="$AINEWS_CONTENT_PATH/youtube"

mkdir -p "$AINEWS_KO_DIR"
mkdir -p "$AINEWS_YOUTUBE_DIR"

# 파일명 생성 (날짜-slug.md 형식)
FILENAME="${SLUG}.md"

log_info "Copying files..."
cp "$FINAL_FILE" "$AINEWS_KO_DIR/$FILENAME"

if [[ -f "$YOUTUBE_FILE" ]]; then
    cp "$YOUTUBE_FILE" "$AINEWS_YOUTUBE_DIR/${SLUG}.txt"
fi

# 변경사항 커밋
log_info "Committing changes..."
git add "$AINEWS_CONTENT_PATH/"

# frontmatter에서 제목 추출
TITLE=$(grep "^title:" "$FINAL_FILE" | head -1 | sed 's/title: "//;s/"$//')
if [[ -z "$TITLE" ]]; then
    TITLE="AI News - $SLUG"
fi

git commit -m "$(cat <<EOF
feat(ainews): Add AI news - $SLUG

$TITLE

Co-Authored-By: Codex CLI (gpt-5.2) <noreply@openai.com>
Reviewed-By: Claude Opus <noreply@anthropic.com>
EOF
)"

# 푸시
log_info "Pushing to remote..."
git push -u origin "$BRANCH_NAME"

# PR 생성
log_info "Creating pull request..."

# frontmatter에서 summary 추출
SUMMARY=$(grep -A 5 "^summary:" "$FINAL_FILE" | grep "^  - " | sed 's/^  - "//;s/"$//' | head -3)

# 파이프라인 경고 확인
WARNINGS_FILE="$WORK_DIR/pipeline_warnings.txt"
WARNINGS_SECTION=""
if [[ -f "$WARNINGS_FILE" ]]; then
    WARNINGS_CONTENT=$(cat "$WARNINGS_FILE")
    WARNINGS_SECTION="
## ⚠️ Pipeline Warnings

파이프라인 실행 중 다음 문제가 발생했습니다:

$(echo "$WARNINGS_CONTENT" | while read line; do echo "- $line"; done)

**수동 검토 권장**
"
fi

PR_URL=$(gh pr create \
    --title "feat(ainews): $TITLE" \
    --body "$(cat <<EOF
## Summary

자동 번역된 AI 뉴스입니다.

### 주요 내용
$(echo "$SUMMARY" | while read line; do echo "- $line"; done)
${WARNINGS_SECTION}
## Pipeline Info

- **Translation**: Codex CLI ($CODEX_MODEL, reasoning: $CODEX_REASONING_EFFORT)
- **Review**: Claude Opus
- **Source**: [Original Article](https://github.com/smol-ai/ainews-web-2025/blob/main/src/content/issues/${SLUG}.md)

## Checklist

- [ ] All source links preserved
- [ ] Translation quality acceptable
- [ ] Frontmatter correct
- [ ] No broken markdown

---

🤖 Generated with [news-automation](https://github.com/jonhpark/news-automation) pipeline
EOF
)" \
    --base main \
    --head "$BRANCH_NAME")

# main으로 복귀
log_info "Switching back to main..."
git checkout main

# PR URL 출력
echo "$PR_URL"
