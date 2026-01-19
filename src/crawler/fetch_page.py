#!/usr/bin/env python3
"""
fetch_page.py - 웹 크롤러
smol.ai 뉴스 페이지를 크롤링하여 마크다운으로 변환합니다.

smol.ai HTML 구조:
- 콘텐츠: <article class="content-area">...</article>
- 링크: <a href="https://...">text</a>
"""

import sys
import re
import json
import argparse
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from html.parser import HTMLParser
from typing import Optional
from datetime import datetime

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# 검증 기준
MIN_CONTENT_LENGTH = 1000  # 최소 콘텐츠 길이 (문자)
MIN_LINK_COUNT = 5  # 최소 링크 개수


class SmolAIContentParser(HTMLParser):
    """smol.ai content-area를 파싱하는 HTML 파서"""

    # HTML void elements (no end tag). These must not affect depth tracking.
    _VOID_ELEMENTS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self):
        super().__init__()
        self.in_content_area = False
        self.content_depth = 0
        self.content_parts = []
        self.current_link_href = None
        self.current_link_text = []
        self.in_link = False
        self.tag_stack = []
        self.links_found = []
        self.title = ""
        self.in_title_tag = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        # title 태그 감지
        if tag == "title":
            self.in_title_tag = True
            return

        # content-area 시작 감지
        if tag == "article" and "content-area" in attrs_dict.get("class", ""):
            self.in_content_area = True
            self.content_depth = 1
            return

        if not self.in_content_area:
            return

        # depth 추적 (void element는 endtag가 없으므로 제외)
        if tag not in self._VOID_ELEMENTS:
            self.content_depth += 1
            self.tag_stack.append(tag)

        # 마크다운 변환
        if tag == "h1":
            self.content_parts.append("\n\n# ")
        elif tag == "h2":
            self.content_parts.append("\n\n## ")
        elif tag == "h3":
            self.content_parts.append("\n\n### ")
        elif tag == "h4":
            self.content_parts.append("\n\n#### ")
        elif tag == "p":
            self.content_parts.append("\n\n")
        elif tag == "ul":
            self.content_parts.append("\n")
        elif tag == "ol":
            self.content_parts.append("\n")
        elif tag == "li":
            self.content_parts.append("\n- ")
        elif tag == "strong" or tag == "b":
            self.content_parts.append("**")
        elif tag == "em" or tag == "i":
            self.content_parts.append("*")
        elif tag == "code":
            self.content_parts.append("`")
        elif tag == "pre":
            self.content_parts.append("\n```\n")
        elif tag == "hr":
            self.content_parts.append("\n\n---\n\n")
        elif tag == "br":
            self.content_parts.append("\n")
        elif tag == "blockquote":
            self.content_parts.append("\n\n> ")
        elif tag == "a":
            href = attrs_dict.get("href", "")
            if href and not href.startswith("#") and not href.startswith("/"):
                self.in_link = True
                self.current_link_href = href
                self.current_link_text = []
                self.links_found.append(href)
            else:
                # 내부 링크는 텍스트만 추출
                pass
        elif tag == "img":
            alt = attrs_dict.get("alt", "image")
            src = attrs_dict.get("src", "")
            if src:
                self.content_parts.append(f"![{alt}]({src})")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title_tag = False
            return

        if not self.in_content_area:
            return

        # content-area 종료 감지
        if tag == "article":
            self.content_depth -= 1
            if self.content_depth <= 0:
                self.in_content_area = False
            return

        self.content_depth -= 1
        if self.tag_stack:
            self.tag_stack.pop()

        # 마크다운 변환
        if tag == "strong" or tag == "b":
            self.content_parts.append("**")
        elif tag == "em" or tag == "i":
            self.content_parts.append("*")
        elif tag == "code":
            self.content_parts.append("`")
        elif tag == "pre":
            self.content_parts.append("\n```\n")
        elif tag == "a" and self.in_link:
            link_text = "".join(self.current_link_text).strip()
            if link_text and self.current_link_href:
                self.content_parts.append(f"[{link_text}]({self.current_link_href})")
            self.in_link = False
            self.current_link_href = None
            self.current_link_text = []

    def handle_data(self, data):
        if self.in_title_tag:
            self.title += data
            return

        if not self.in_content_area:
            return

        if self.in_link:
            self.current_link_text.append(data)
        else:
            self.content_parts.append(data)

    def handle_startendtag(self, tag, attrs):
        # Self-closing tags like <br/> or <img/> are common; treat as starttag only.
        self.handle_starttag(tag, attrs)


def fetch_page(url: str) -> str:
    """웹 페이지를 가져옵니다."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; smol-ai-news-automation/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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


def html_to_markdown(html_content: str) -> tuple[str, str, list[str]]:
    """HTML을 마크다운으로 변환합니다.

    Returns:
        (content, title, links) 튜플
    """
    parser = SmolAIContentParser()
    parser.feed(html_content)

    content = "".join(parser.content_parts)

    # 정리: 연속된 빈 줄 제거, 앞뒤 공백 제거
    content = re.sub(r"\n{3,}", "\n\n", content)
    content = content.strip()

    # 너무 긴 Discord 상세 섹션(사이트용)을 잘라내고 핵심 뉴스레터만 유지
    # (예: "# Discord: High level Discord summaries" 이하 제거)
    content = re.split(
        r"^# Discord: High level Discord summaries\s*$",
        content,
        maxsplit=1,
        flags=re.MULTILINE,
    )[0].rstrip()
    # 다음 섹션을 위해 붙은 마지막 구분선이 남아있으면 제거
    content = re.sub(r"(\n---\s*)+\Z", "\n", content).strip()

    # title에서 " | AINews" 제거
    title = parser.title.replace(" | AINews", "").strip()

    # 최종 콘텐츠 기준으로 링크 재추출 (trim된 섹션 링크 제외)
    links = re.findall(r"\[[^\]]*?\]\(([^)]+)\)", content)

    return content, title, links


def extract_metadata_from_url(url: str) -> dict:
    """URL에서 메타데이터를 추출합니다."""
    # URL에서 날짜 추출: /issues/26-01-14-not-much/
    date_match = re.search(r"/issues/(\d{2})-(\d{2})-(\d{2})-", url)
    if date_match:
        yy, mm, dd = date_match.groups()
        date = f"20{yy}-{mm}-{dd}"
    else:
        date = datetime.now().strftime("%Y-%m-%d")

    # slug 추출
    slug_match = re.search(r"/issues/([^/]+)/?$", url)
    slug = slug_match.group(1) if slug_match else ""

    return {
        "date": date,
        "slug": slug,
        "original_url": url,
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
    """URL에서 페이지를 가져와 마크다운으로 변환합니다.

    Returns:
        메타데이터와 콘텐츠를 포함한 딕셔너리
    """
    html_content = fetch_page(url)
    content, title, links = html_to_markdown(html_content)
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
        description="smol.ai 뉴스 페이지를 크롤링하여 마크다운으로 변환합니다."
    )
    parser.add_argument(
        "url",
        help="크롤링할 smol.ai 뉴스 URL"
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
        print("WARNING: Content validation failed. Site structure may have changed.", file=sys.stderr)
        sys.exit(2)  # 특별한 exit code로 구조 변경 감지

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
