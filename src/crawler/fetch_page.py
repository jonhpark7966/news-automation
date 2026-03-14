#!/usr/bin/env python3
"""
fetch_page.py - GitHub 마크다운 페처
GitHub 레포지토리에서 마크다운 파일을 가져와 처리합니다.

기존 smol.ai HTML 크롤링에서 GitHub raw 마크다운 직접 가져오기로 변경되었습니다.
"""

import sys
import re
import json
import argparse
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from typing import Optional
from datetime import datetime

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# 검증 기준
MIN_CONTENT_LENGTH = 1000  # 최소 콘텐츠 길이 (문자)
MIN_LINK_COUNT = 5  # 최소 링크 개수


def fetch_raw_markdown(url: str) -> str:
    """GitHub raw URL에서 마크다운 파일을 가져옵니다."""
    headers = {
        "User-Agent": "smol-ai-news-automation/1.0",
        "Accept": "text/plain",
    }
    request = Request(url, headers=headers)

    try:
        with urlopen(request, timeout=60) as response:
            return response.read().decode("utf-8")
    except HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"URL Error: {e.reason}", file=sys.stderr)
        sys.exit(1)


def strip_frontmatter(raw_content: str) -> tuple[str, dict]:
    """YAML frontmatter를 분리하여 본문과 메타데이터를 반환합니다.

    Returns:
        (body, frontmatter_dict) 튜플
    """
    frontmatter = {}

    if not raw_content.startswith("---"):
        return raw_content, frontmatter

    # frontmatter 끝 찾기
    end_match = re.search(r"\n---\s*\n", raw_content[3:])
    if not end_match:
        return raw_content, frontmatter

    fm_text = raw_content[4:end_match.start() + 3]  # --- 이후부터
    body = raw_content[end_match.end() + 3:]  # --- 이후 본문

    # 간단한 YAML 파싱 (외부 라이브러리 없이)
    for line in fm_text.strip().split("\n"):
        # 리스트 항목 (- value) 건너뛰기
        if line.strip().startswith("- "):
            continue
        match = re.match(r"^(\w+):\s*(.+)$", line)
        if match:
            key = match.group(1)
            value = match.group(2).strip().strip("'\"")
            frontmatter[key] = value

    return body, frontmatter


def process_markdown(raw_content: str) -> tuple[str, str, list[str]]:
    """마크다운 콘텐츠를 처리합니다.

    Returns:
        (content, title, links) 튜플
    """
    body, frontmatter = strip_frontmatter(raw_content)

    # 타이틀 추출 (frontmatter > 첫 번째 # 헤딩)
    title = frontmatter.get("title", "")
    if not title or title == "FILL TITLE IN HERE":
        # 본문에서 첫 번째 헤딩 추출
        heading_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        if heading_match:
            title = heading_match.group(1).strip()

    # 정리: 연속된 빈 줄 제거, 앞뒤 공백 제거
    content = re.sub(r"\n{3,}", "\n\n", body)
    content = content.strip()

    # 너무 긴 Discord 상세 섹션(사이트용)을 잘라내고 핵심 뉴스레터만 유지
    content = re.split(
        r"^# Discord: High level Discord summaries\s*$",
        content,
        maxsplit=1,
        flags=re.MULTILINE,
    )[0].rstrip()
    # 다음 섹션을 위해 붙은 마지막 구분선이 남아있으면 제거
    content = re.sub(r"(\n---\s*)+\Z", "\n", content).strip()

    # 링크 추출
    links = re.findall(r"\[[^\]]*?\]\(([^)]+)\)", content)

    return content, title, links


def extract_metadata_from_url(url: str) -> dict:
    """URL에서 메타데이터를 추출합니다.

    GitHub raw URL 형식: .../src/content/issues/26-03-04-not-much.md
    """
    # 파일명에서 slug 추출
    filename = url.rstrip("/").split("/")[-1]
    slug = filename.replace(".md", "") if filename.endswith(".md") else filename

    # slug에서 날짜 추출
    # YY-MM-DD 형식
    date_match = re.match(r"^(\d{2})-(\d{2})-(\d{2})-", slug)
    if date_match:
        yy, mm, dd = date_match.groups()
        date = f"20{yy}-{mm}-{dd}"
    else:
        # YYYY-MM-DD 형식
        date_match = re.match(r"^(\d{4}-\d{2}-\d{2})-", slug)
        if date_match:
            date = date_match.group(1)
        else:
            date = datetime.now().strftime("%Y-%m-%d")

    # original_url은 GitHub 원문 URL로 구성
    original_url = f"https://github.com/smol-ai/ainews-web-2025/blob/main/src/content/issues/{slug}.md"

    return {
        "date": date,
        "slug": slug,
        "original_url": original_url,
    }


def validate_content(content: str, links: list[str], url: str) -> dict:
    """콘텐츠 품질을 검증합니다.

    Returns:
        {"valid": bool, "errors": list[str], "warnings": list[str]}
    """
    errors = []
    warnings = []

    # 콘텐츠 길이 검증
    if len(content) < MIN_CONTENT_LENGTH:
        errors.append(
            f"Content too short: {len(content)} chars (min: {MIN_CONTENT_LENGTH})"
        )

    # 링크 개수 검증
    if len(links) < MIN_LINK_COUNT:
        errors.append(
            f"Too few links: {len(links)} (min: {MIN_LINK_COUNT})"
        )

    # 필수 섹션 검증
    expected_sections = ["Twitter", "Reddit", "Discord"]
    for section in expected_sections:
        if section not in content:
            warnings.append(f"Missing expected section: {section}")

    # 헤드라인 유무 판단
    has_headline = not any([
        "not much" in content.lower()[:500],
        "quiet day" in content.lower()[:500],
        "relatively quiet" in content.lower()[:500],
        "a quiet day" in content.lower()[:500],
    ])

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "content_length": len(content),
            "link_count": len(links),
            "has_headline": has_headline,
        }
    }


def fetch_and_convert(url: str, output_path: Optional[Path] = None) -> dict:
    """URL에서 마크다운을 가져와 처리합니다.

    Returns:
        메타데이터와 콘텐츠를 포함한 딕셔너리
    """
    raw_content = fetch_raw_markdown(url)
    content, title, links = process_markdown(raw_content)
    url_metadata = extract_metadata_from_url(url)

    # 검증
    validation = validate_content(content, links, url)

    metadata = {
        **url_metadata,
        "title": title,
        "has_headline": validation["stats"]["has_headline"],
    }

    result = {
        "metadata": metadata,
        "content": content,
        "links": links,
        "validation": validation,
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="GitHub 마크다운 파일을 가져와 처리합니다."
    )
    parser.add_argument(
        "url",
        help="GitHub raw 마크다운 URL"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="출력 파일 경로"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="JSON 형식으로 출력"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="검증만 수행"
    )

    args = parser.parse_args()

    result = fetch_and_convert(args.url, args.output if not args.validate_only else None)

    # 검증 결과 출력
    validation = result["validation"]
    if validation["errors"]:
        print("VALIDATION ERRORS:", file=sys.stderr)
        for error in validation["errors"]:
            print(f"  - {error}", file=sys.stderr)

    if validation["warnings"]:
        print("VALIDATION WARNINGS:", file=sys.stderr)
        for warning in validation["warnings"]:
            print(f"  - {warning}", file=sys.stderr)

    if args.validate_only:
        if validation["valid"]:
            print("Validation passed")
            print(f"  Content length: {validation['stats']['content_length']}")
            print(f"  Link count: {validation['stats']['link_count']}")
            print(f"  Has headline: {validation['stats']['has_headline']}")
            sys.exit(0)
        else:
            print("Validation failed")
            sys.exit(1)

    if not validation["valid"]:
        print("WARNING: Content validation failed.", file=sys.stderr)
        sys.exit(2)  # 특별한 exit code로 검증 실패 표시

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if args.output:
            print(f"Saved to: {args.output}")
            print(f"Title: {result['metadata']['title']}")
            print(f"Date: {result['metadata']['date']}")
            print(f"Has Headline: {result['metadata']['has_headline']}")
            print(f"Links found: {len(result['links'])}")
        else:
            print(result["content"])


if __name__ == "__main__":
    main()
