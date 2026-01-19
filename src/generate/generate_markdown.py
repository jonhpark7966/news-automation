#!/usr/bin/env python3
"""
generate_markdown.py - 마크다운 생성기
번역된 콘텐츠를 최종 마크다운 파일로 조립합니다.
"""

import sys
import re
import argparse
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _parse_yaml_simple(fm_content: str) -> dict:
    """간단한 YAML 파싱 (복잡한 중첩은 미지원)"""
    frontmatter = {}
    current_key = None
    current_list = None

    for line in fm_content.split("\n"):
        line = line.rstrip()
        if not line:
            continue

        # 리스트 항목
        if line.startswith("  - "):
            if current_list is not None:
                current_list.append(line[4:].strip().strip('"').strip("'"))
            continue

        # 키: 값 형식
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if value == "":
                # 다음 줄에 리스트가 올 수 있음
                current_key = key
                current_list = []
                frontmatter[key] = current_list
            else:
                # boolean 변환
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                frontmatter[key] = value
                current_key = None
                current_list = None

    return frontmatter


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """마크다운에서 frontmatter를 파싱합니다.

    Returns:
        (frontmatter_dict, body) 튜플
    """
    frontmatter = {}
    body = content

    # 코드펜스 안에 frontmatter가 있는 경우 처리 (```yaml\n---\n...\n---\n```)
    codefence_match = re.match(
        r"^```(?:yaml|yml|markdown|md)?\s*\n---\s*\n(.*?)\n---\s*\n```\s*\n(.*)$",
        content,
        re.DOTALL
    )
    if codefence_match:
        fm_content = codefence_match.group(1)
        body = codefence_match.group(2)
        return _parse_yaml_simple(fm_content), body

    # --- 로 시작하고 --- 로 끝나는 frontmatter 추출
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if match:
        fm_content = match.group(1)
        body = match.group(2)
        return _parse_yaml_simple(fm_content), body

    return frontmatter, body


def generate_frontmatter(metadata: dict) -> str:
    """메타데이터에서 frontmatter를 생성합니다."""
    lines = ["---"]

    # title
    title = metadata.get("title", "AI News")
    lines.append(f'title: "{title}"')

    # summary (리스트)
    summary = metadata.get("summary", [])
    if summary:
        lines.append("summary:")
        for item in summary[:5]:  # 최대 5줄
            lines.append(f'  - "{item}"')

    # date
    date = metadata.get("date", datetime.now().strftime("%Y-%m-%d"))
    lines.append(f"date: {date}")

    # originalUrl
    original_url = metadata.get("originalUrl", metadata.get("original_url", ""))
    if original_url:
        lines.append(f'originalUrl: "{original_url}"')

    # hasHeadline
    has_headline = metadata.get("hasHeadline", metadata.get("has_headline", False))
    lines.append(f"hasHeadline: {str(has_headline).lower()}")

    # headline (항상 포함: hasHeadline 여부와 무관)
    headline = metadata.get("headline", "")
    if not headline and summary:
        # 최소한의 폴백: summary 첫 줄을 headline로 사용
        headline = summary[0]
    if headline:
        lines.append(f'headline: "{headline}"')

    # tags (리스트)
    tags = metadata.get("tags", [])
    if tags:
        lines.append("tags:")
        for tag in tags:
            lines.append(f"  - {tag}")

    # isFeatured
    is_featured = metadata.get("isFeatured", metadata.get("is_featured", False))
    lines.append(f"isFeatured: {str(is_featured).lower()}")

    lines.append("---")

    return "\n".join(lines)


def validate_links(original: str, translated: str) -> tuple[bool, list[str]]:
    """원문과 번역본의 링크를 비교합니다.

    Returns:
        (is_valid, missing_urls) 튜플
    """
    # URL 추출 패턴 (http/https 외의 링크도 포함)
    url_pattern = r"\[[^\]]*?\]\(([^)]+)\)"

    original_urls = re.findall(url_pattern, original)
    translated_urls = re.findall(url_pattern, translated)

    from collections import Counter

    original_counts = Counter(original_urls)
    translated_counts = Counter(translated_urls)

    missing = original_counts - translated_counts
    extra = translated_counts - original_counts

    issues = []
    if missing:
        issues.append(f"Missing URLs: {dict(missing)}")
    if extra:
        issues.append(f"Extra URLs: {dict(extra)}")

    return len(missing) == 0 and len(extra) == 0, issues


def assemble_final_markdown(
    translated_content: str,
    metadata: dict = None,
) -> str:
    """최종 마크다운을 조립합니다."""
    # 번역된 콘텐츠에 이미 frontmatter가 있으면 사용
    existing_fm, body = parse_frontmatter(translated_content)

    if existing_fm:
        # 기존 frontmatter 사용, 필요한 필드 보완
        if metadata:
            for key, value in metadata.items():
                if key not in existing_fm:
                    existing_fm[key] = value
        fm_str = generate_frontmatter(existing_fm)
        return f"{fm_str}\n\n{body.strip()}\n"
    elif metadata:
        # 메타데이터로 새 frontmatter 생성
        fm_str = generate_frontmatter(metadata)
        return f"{fm_str}\n\n{translated_content.strip()}\n"
    else:
        return translated_content


def main():
    parser = argparse.ArgumentParser(
        description="번역된 콘텐츠를 최종 마크다운 파일로 조립합니다."
    )
    parser.add_argument(
        "translated_file",
        type=Path,
        help="번역된 마크다운 파일 경로"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="출력 파일 경로"
    )
    parser.add_argument(
        "--original",
        type=Path,
        help="원문 파일 (링크 검증용)"
    )
    parser.add_argument(
        "--date",
        type=str,
        help="날짜 (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--original-url",
        type=str,
        help="원본 URL"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="링크 검증만 수행"
    )

    args = parser.parse_args()

    # 번역본 읽기
    translated_content = args.translated_file.read_text(encoding="utf-8")

    # 링크 검증
    if args.original:
        original_content = args.original.read_text(encoding="utf-8")
        is_valid, issues = validate_links(original_content, translated_content)

        if not is_valid:
            print("FAIL: Link validation failed", file=sys.stderr)
            for issue in issues:
                print(f"  - {issue}", file=sys.stderr)
            if args.validate_only:
                sys.exit(1)
        else:
            print("Link validation passed")

    if args.validate_only:
        sys.exit(0)

    # 메타데이터 구성
    metadata = {}
    if args.date:
        metadata["date"] = args.date
    if args.original_url:
        metadata["originalUrl"] = args.original_url

    # 최종 마크다운 생성
    final_content = assemble_final_markdown(translated_content, metadata)

    # 출력
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(final_content, encoding="utf-8")
        print(f"Saved to: {args.output}")
    else:
        print(final_content)


if __name__ == "__main__":
    main()
