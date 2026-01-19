#!/usr/bin/env python3
"""
generate_youtube.py - YouTube 템플릿 생성기
번역된 콘텐츠에서 YouTube 영상용 템플릿을 생성합니다.
"""

import sys
import re
import argparse
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """마크다운에서 frontmatter를 파싱합니다."""
    frontmatter = {}
    body = content

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if match:
        fm_content = match.group(1)
        body = match.group(2)

        current_list = None

        for line in fm_content.split("\n"):
            line = line.rstrip()
            if not line:
                continue

            if line.startswith("  - "):
                if current_list is not None:
                    current_list.append(line[4:].strip().strip('"').strip("'"))
                continue

            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip().strip('"').strip("'")

                if value == "":
                    current_list = []
                    frontmatter[key] = current_list
                else:
                    if value.lower() == "true":
                        value = True
                    elif value.lower() == "false":
                        value = False
                    frontmatter[key] = value
                    current_list = None

    return frontmatter, body


def extract_headlines(body: str) -> list[dict]:
    """본문에서 헤드라인(섹션)들을 추출합니다."""
    headlines = []

    # ## 로 시작하는 섹션 추출
    sections = re.split(r"^## ", body, flags=re.MULTILINE)

    for section in sections[1:]:  # 첫 번째는 빈 문자열
        lines = section.strip().split("\n")
        if lines:
            title = lines[0].strip()
            content = "\n".join(lines[1:]).strip()
            headlines.append({
                "title": title,
                "content": content[:500] + "..." if len(content) > 500 else content
            })

    return headlines


def generate_youtube_title(metadata: dict, date_str: str) -> str:
    """YouTube 영상 제목을 생성합니다."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%m/%d")

    title = metadata.get("title", "AI 뉴스")
    headline = metadata.get("headline", "")

    if headline:
        return f"[{formatted_date}] {headline} | AI 뉴스"
    else:
        return f"[{formatted_date}] {title} | AI 뉴스"


def generate_youtube_description(
    metadata: dict,
    body: str,
    original_url: str
) -> str:
    """YouTube 영상 설명을 생성합니다."""
    lines = []

    # 요약
    summary = metadata.get("summary", [])
    if summary:
        lines.append("📌 오늘의 주요 소식:")
        for item in summary:
            lines.append(f"• {item}")
        lines.append("")

    # 본문 요약
    headlines = extract_headlines(body)
    if headlines:
        lines.append("📋 목차:")
        for i, h in enumerate(headlines[:6], 1):  # 최대 6개
            lines.append(f"{i}. {h['title']}")
        lines.append("")

    # 원본 링크
    lines.append("🔗 링크:")
    lines.append(f"• 원문: {original_url}")
    lines.append("")

    # 태그
    tags = metadata.get("tags", [])
    if tags:
        hashtags = " ".join([f"#{tag}" for tag in tags[:5]])
        lines.append(hashtags)
        lines.append("")

    # 푸터
    lines.append("─" * 40)
    lines.append("smol.ai 뉴스 자동 번역 시스템")
    lines.append("Translated by Codex CLI (gpt-5.2)")
    lines.append("Reviewed by Claude Opus")

    return "\n".join(lines)


def generate_youtube_tags(metadata: dict) -> list[str]:
    """YouTube 태그 목록을 생성합니다."""
    base_tags = ["AI", "인공지능", "AI뉴스", "테크뉴스", "머신러닝"]
    custom_tags = metadata.get("tags", [])

    return list(set(base_tags + custom_tags))[:30]  # YouTube 태그 제한


def generate_youtube_template(content: str, original_url: str = "") -> dict:
    """YouTube 템플릿을 생성합니다."""
    metadata, body = parse_frontmatter(content)

    date_str = metadata.get("date", datetime.now().strftime("%Y-%m-%d"))

    return {
        "title": generate_youtube_title(metadata, date_str),
        "description": generate_youtube_description(metadata, body, original_url),
        "tags": generate_youtube_tags(metadata),
        "date": date_str,
    }


def main():
    parser = argparse.ArgumentParser(
        description="번역된 콘텐츠에서 YouTube 영상용 템플릿을 생성합니다."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="번역된 마크다운 파일 경로"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="출력 파일 경로"
    )
    parser.add_argument(
        "--original-url",
        type=str,
        default="",
        help="원본 URL"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="JSON 형식으로 출력"
    )

    args = parser.parse_args()

    content = args.input_file.read_text(encoding="utf-8")
    template = generate_youtube_template(content, args.original_url)

    if args.json:
        import json
        output = json.dumps(template, indent=2, ensure_ascii=False)
    else:
        # 텍스트 형식
        lines = [
            "=" * 50,
            "YouTube Template",
            "=" * 50,
            "",
            f"Title: {template['title']}",
            "",
            "Description:",
            "-" * 30,
            template["description"],
            "-" * 30,
            "",
            f"Tags: {', '.join(template['tags'])}",
            "",
            f"Date: {template['date']}",
            "=" * 50,
        ]
        output = "\n".join(lines)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(f"Saved to: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
