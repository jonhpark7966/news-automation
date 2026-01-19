#!/bin/bash
# run.sh - Crontab 래퍼 스크립트
# smol.ai 한국어 뉴스 자동 발행 시스템
#
# Crontab 설정 예시 (매일 오전 9시):
#   0 9 * * * /home/jonhpark/workspace/news-automation/cron/run.sh >> /home/jonhpark/workspace/news-automation/data/logs/cron.log 2>&1
#
# 4시간마다:
#   0 */4 * * * /home/jonhpark/workspace/news-automation/cron/run.sh >> /home/jonhpark/workspace/news-automation/data/logs/cron.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 환경 설정 로드
if [[ -f "$PROJECT_ROOT/config/config.env" ]]; then
    source "$PROJECT_ROOT/config/config.env"
fi

# 타임스탬프
echo "========================================"
echo "News Automation Cron Job"
echo "Started: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

# 메인 스크립트 실행
"$PROJECT_ROOT/src/main.sh" || {
    echo "Pipeline failed with exit code: $?"
    echo "Finished: $(date '+%Y-%m-%d %H:%M:%S')"
    exit 1
}

echo "========================================"
echo "Finished: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
