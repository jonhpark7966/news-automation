#!/usr/bin/env python3
"""
check_feed.py - RSS 피드 파서
smol.ai 뉴스 RSS 피드를 확인하고 새 이슈를 감지합니다.
"""

import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import xml.etree.ElementTree as ET
import re

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

RSS_FEED_URL = "https://news.smol.ai/rss.xml"
PROCESSED_FILE = PROJECT_ROOT / "data" / "processed.json"


def fetch_rss_feed(url: str) -> str:
    """RSS 피드를 가져옵니다."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; smol-ai-news-automation/1.0)"
    }
    request = Request(url, headers=headers)

    try:
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")
    except HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"URL Error: {e.reason}", file=sys.stderr)
        sys.exit(1)


def parse_rss_feed(xml_content: str) -> list[dict]:
    """RSS 피드를 파싱하여 이슈 목록을 반환합니다."""
    root = ET.fromstring(xml_content)
    items = []

    # RSS 2.0 구조: rss > channel > item
    for item in root.findall(".//item"):
        title = item.find("title")
        link = item.find("link")
        pub_date = item.find("pubDate")
        description = item.find("description")
        guid = item.find("guid")

        if link is None:
            continue

        url = link.text.strip()
        slug = extract_slug_from_url(url)

        items.append({
            "title": title.text.strip() if title is not None else "",
            "url": url,
            "slug": slug,
            "pub_date": pub_date.text.strip() if pub_date is not None else "",
            "description": description.text.strip() if description is not None else "",
            "guid": guid.text.strip() if guid is not None else url,
        })

    return items


def extract_slug_from_url(url: str) -> str:
    """URL에서 slug를 추출합니다.

    예: https://news.smol.ai/issues/26-01-16-chatgpt-ads/ -> 26-01-16-chatgpt-ads
    """
    # URL 끝의 슬래시 제거
    url = url.rstrip("/")

    # /issues/ 이후 부분 추출
    match = re.search(r"/issues/([^/]+)", url)
    if match:
        return match.group(1)

    # 마지막 경로 세그먼트 반환
    return url.split("/")[-1]


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


def get_unprocessed_issues(items: list[dict]) -> list[dict]:
    """아직 처리되지 않은 이슈 목록을 반환합니다."""
    state = load_processed_state()
    processed_slugs = {item["slug"] for item in state["processed"]}

    return [item for item in items if item["slug"] not in processed_slugs]


def check_for_new_issues(limit: int = None) -> list[dict]:
    """새 이슈를 확인하고 반환합니다."""
    xml_content = fetch_rss_feed(RSS_FEED_URL)
    items = parse_rss_feed(xml_content)
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
        description="smol.ai RSS 피드를 확인하고 새 이슈를 감지합니다."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="새 이슈 확인"
    )
    parser.add_argument(
        "--list-all",
        action="store_true",
        help="모든 피드 항목 나열"
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
        xml_content = fetch_rss_feed(RSS_FEED_URL)
        items = parse_rss_feed(xml_content)

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
