#!/usr/bin/env python3
"""
check_feed.py - GitHub 소스 파서
smol-ai/ainews-web-2025 GitHub 레포지토리에서 새 이슈를 감지합니다.

기존 RSS 피드(news.smol.ai/rss.xml)가 더 이상 업데이트되지 않아
GitHub 레포지토리의 마크다운 파일을 직접 확인하는 방식으로 변경되었습니다.
"""

import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import re

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

GITHUB_API_URL = "https://api.github.com/repos/smol-ai/ainews-web-2025/contents/src/content/issues"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/smol-ai/ainews-web-2025/main/src/content/issues"
PROCESSED_FILE = PROJECT_ROOT / "data" / "processed.json"


def fetch_github_listing(url: str) -> list[dict]:
    """GitHub API를 사용하여 이슈 파일 목록을 가져옵니다."""
    headers = {
        "User-Agent": "smol-ai-news-automation/1.0",
        "Accept": "application/vnd.github.v3+json",
    }
    request = Request(url, headers=headers)

    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"URL Error: {e.reason}", file=sys.stderr)
        sys.exit(1)


def parse_github_listing(files: list[dict]) -> list[dict]:
    """GitHub 파일 목록을 파싱하여 이슈 목록을 반환합니다."""
    items = []

    for f in files:
        name = f.get("name", "")
        if not name.endswith(".md"):
            continue

        slug = name[:-3]  # .md 제거

        # YY-MM-DD 또는 YYYY-MM-DD 형식만 허용
        if not re.match(r"^(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{2})", slug):
            continue

        raw_url = f"{GITHUB_RAW_BASE}/{name}"

        items.append({
            "title": slug,
            "url": raw_url,
            "slug": slug,
            "pub_date": "",
            "description": "",
            "guid": slug,
        })

    return items


def load_processed_state() -> dict:
    """처리된 이슈 상태를 로드합니다."""
    if not PROCESSED_FILE.exists():
        return {"processed": [], "last_check": None}

    try:
        with open(PROCESSED_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"processed": [], "last_check": None}


def save_processed_state(state: dict):
    """처리된 이슈 상태를 저장합니다."""
    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(PROCESSED_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def mark_as_processed(slug: str, status: str = "success"):
    """이슈를 처리됨으로 표시합니다."""
    state = load_processed_state()

    # 기존 항목 업데이트 또는 추가
    processed_slugs = {item["slug"]: item for item in state["processed"]}
    processed_slugs[slug] = {
        "slug": slug,
        "status": status,
        "processed_at": datetime.now().isoformat()
    }

    state["processed"] = list(processed_slugs.values())
    state["last_check"] = datetime.now().isoformat()

    save_processed_state(state)


def extract_date_from_slug(slug: str) -> str:
    """slug에서 날짜를 추출합니다. YYYY-MM-DD로 정규화하여 반환합니다.

    예: 26-01-16-chatgpt-ads -> 2026-01-16
        2026-02-10-qwenimage -> 2026-02-10
    """
    # YYYY-MM-DD 형식 (새 형식)
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", slug)
    if match:
        return match.group(1)

    # YY-MM-DD 형식 (구 형식) -> YYYY-MM-DD로 변환
    match = re.match(r"^(\d{2})-(\d{2})-(\d{2})", slug)
    if match:
        return f"20{match.group(1)}-{match.group(2)}-{match.group(3)}"

    return ""


def get_latest_processed_date(state: dict) -> str:
    """처리된 이슈 중 가장 최신 날짜를 반환합니다.

    Returns:
        가장 최신 날짜 (예: "2026-01-16"), 없으면 빈 문자열
    """
    if not state.get("processed"):
        return ""

    # success 상태인 항목들의 날짜만 추출
    dates = []
    for item in state["processed"]:
        if item.get("status") == "success":
            date = extract_date_from_slug(item["slug"])
            if date:
                dates.append(date)

    if not dates:
        return ""

    return sorted(dates, reverse=True)[0]


def get_unprocessed_issues(items: list[dict]) -> list[dict]:
    """처리되지 않은 새 이슈 목록을 반환합니다.

    중요: 가장 최근 처리된 글의 날짜 이후에 발행된 글만 반환합니다.
    이전 날짜의 미처리 글은 무시됩니다.

    기준: processed.json의 success 상태인 항목 중 가장 최신 날짜
    """
    state = load_processed_state()
    processed_slugs = {item["slug"] for item in state["processed"]}
    latest_date = get_latest_processed_date(state)

    new_issues = []
    for item in items:
        # 이미 처리된 항목 제외
        if item["slug"] in processed_slugs:
            continue

        # 최신 처리 날짜가 있으면, 그 이후 날짜만 포함
        if latest_date:
            item_date = extract_date_from_slug(item["slug"])
            if item_date and item_date <= latest_date:
                continue  # 이전 날짜는 건너뜀

        new_issues.append(item)

    # 날짜순 정렬 (오래된 것부터)
    new_issues.sort(key=lambda x: extract_date_from_slug(x["slug"]))

    return new_issues


def check_for_new_issues(limit: int = None) -> list[dict]:
    """새 이슈를 확인하고 반환합니다."""
    files = fetch_github_listing(GITHUB_API_URL)
    items = parse_github_listing(files)
    unprocessed = get_unprocessed_issues(items)

    # 상태 업데이트
    state = load_processed_state()
    state["last_check"] = datetime.now().isoformat()
    save_processed_state(state)

    if limit:
        return unprocessed[:limit]
    return unprocessed


def main():
    parser = argparse.ArgumentParser(
        description="GitHub 레포지토리에서 새 이슈를 감지합니다."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="새 이슈 확인"
    )
    parser.add_argument(
        "--list-all",
        action="store_true",
        help="모든 이슈 파일 나열"
    )
    parser.add_argument(
        "--mark-processed",
        type=str,
        metavar="SLUG",
        help="지정된 slug를 처리됨으로 표시"
    )
    parser.add_argument(
        "--status",
        type=str,
        default="success",
        help="mark-processed와 함께 사용할 상태 (default: success)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="반환할 최대 이슈 수 (default: 1)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="JSON 형식으로 출력"
    )

    args = parser.parse_args()

    if args.mark_processed:
        mark_as_processed(args.mark_processed, args.status)
        print(f"Marked '{args.mark_processed}' as processed with status: {args.status}")
        return

    if args.list_all:
        files = fetch_github_listing(GITHUB_API_URL)
        items = parse_github_listing(files)

        if args.json:
            print(json.dumps(items, indent=2, ensure_ascii=False))
        else:
            for item in items:
                print(f"- {item['slug']}: {item['title']}")
        return

    if args.check:
        new_issues = check_for_new_issues(args.limit)

        if args.json:
            print(json.dumps(new_issues, indent=2, ensure_ascii=False))
        else:
            if not new_issues:
                print("No new issues found.")
            else:
                print(f"Found {len(new_issues)} new issue(s):")
                for item in new_issues:
                    print(f"  - {item['slug']}: {item['title']}")
                    print(f"    URL: {item['url']}")
        return

    # 기본 동작: 새 이슈 확인
    new_issues = check_for_new_issues(args.limit)

    if args.json:
        print(json.dumps(new_issues, indent=2, ensure_ascii=False))
    else:
        if new_issues:
            # 첫 번째 이슈의 URL만 출력 (파이프라인에서 사용)
            print(new_issues[0]["url"])
        else:
            sys.exit(1)  # 새 이슈 없음


if __name__ == "__main__":
    main()
