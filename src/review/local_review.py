#!/usr/bin/env python3
"""
local_review.py - 오프라인 번역 품질/링크 보존 검증기

Claude/LLM 없이도 다음 항목을 기계적으로 검증합니다:
- 마크다운 링크(URL) 완전 보존 (가장 중요)
- @username / #hashtag / activity count 보존
- frontmatter 스키마(요약 5줄, 날짜 형식 등)

출력:
- PASS
- FAIL: ... (review-links.txt 형식과 유사)
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass


LINK_RE = re.compile(r"\[[^\]]*?\]\(([^)]+)\)")
MENTION_RE = re.compile(r"@[A-Za-z0-9_]+")
HASHTAG_RE = re.compile(r"#[A-Za-z0-9_]+")
ACTIVITY_RE = re.compile(
    r"\(\s*(?:Activity:\s*)?~?\d+\s+activity(?:\s+comments)?\s*\)",
    re.IGNORECASE,
)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class Issue:
    missing: dict[str, int]
    extra: dict[str, int]
    other: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing and not self.extra and not self.other


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    fm_text = match.group(1)
    body = text[match.end() :]

    frontmatter: dict = {}
    current_list_key: str | None = None

    for raw_line in fm_text.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue

        if line.startswith("  - "):
            if current_list_key is not None:
                frontmatter.setdefault(current_list_key, []).append(
                    line[4:].strip().strip('"').strip("'")
                )
            continue

        if ":" not in line:
            continue

        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()

        if value == "":
            current_list_key = key
            frontmatter[key] = []
            continue

        # scalar
        value = value.strip('"').strip("'")
        if value.lower() == "true":
            frontmatter[key] = True
        elif value.lower() == "false":
            frontmatter[key] = False
        else:
            frontmatter[key] = value

        current_list_key = None

    return frontmatter, body


def _counter_diff(a: list[str], b: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    ca = Counter(a)
    cb = Counter(b)
    missing = ca - cb
    extra = cb - ca
    return dict(missing), dict(extra)


def _fmt_url_list(url_counts: dict[str, int]) -> list[str]:
    def sort_key(item: tuple[str, int]) -> tuple[str, int]:
        url, count = item
        return (url, count)

    lines: list[str] = []
    for url, count in sorted(url_counts.items(), key=sort_key):
        if count > 1:
            lines.append(f"{url} (x{count})")
        else:
            lines.append(url)
    return lines


def review(original: str, translated: str) -> Issue:
    missing: dict[str, int] = {}
    extra: dict[str, int] = {}
    other: list[str] = []

    # 1) 링크 보존
    original_urls = LINK_RE.findall(original)
    translated_urls = LINK_RE.findall(translated)
    missing_urls, extra_urls = _counter_diff(original_urls, translated_urls)
    missing.update(missing_urls)
    extra.update(extra_urls)

    # 2) @username / #hashtag
    original_mentions = set(MENTION_RE.findall(original))
    translated_mentions = set(MENTION_RE.findall(translated))
    missing_mentions = sorted(original_mentions - translated_mentions)
    if missing_mentions:
        other.append(f"누락된 @username: {', '.join(missing_mentions)}")

    original_hashtags = set(HASHTAG_RE.findall(original))
    translated_hashtags = set(HASHTAG_RE.findall(translated))
    missing_hashtags = sorted(original_hashtags - translated_hashtags)
    if missing_hashtags:
        other.append(f"누락된 #hashtag: {', '.join(missing_hashtags)}")

    # 3) activity count
    original_activity = set(ACTIVITY_RE.findall(original))
    translated_activity = set(ACTIVITY_RE.findall(translated))
    missing_activity = sorted(original_activity - translated_activity)
    if missing_activity:
        other.append(f"누락된 activity count: {', '.join(missing_activity)}")

    # 4) Frontmatter 검증
    fm, _ = _parse_frontmatter(translated)
    if not fm:
        other.append("Frontmatter(--- ... ---)를 찾을 수 없습니다.")
        return Issue(missing=missing, extra=extra, other=other)

    title = str(fm.get("title", "")).strip()
    if not title or "번역된" in title or "가장 흥미로운" in title:
        other.append("title이 비어있거나 템플릿 값으로 보입니다.")

    summary = fm.get("summary", [])
    if not isinstance(summary, list) or len(summary) != 5:
        other.append("summary는 정확히 5줄이어야 합니다.")
    else:
        for i, s in enumerate(summary, 1):
            s = str(s).strip()
            if not (20 <= len(s) <= 40):
                other.append(f"summary {i}번째 줄이 20-40자 범위를 벗어났습니다: {len(s)}자")

    date = str(fm.get("date", "")).strip()
    if not DATE_RE.match(date):
        other.append("date 형식이 YYYY-MM-DD가 아닙니다.")

    original_url = str(fm.get("originalUrl", "")).strip()
    if not original_url:
        other.append("originalUrl이 비어있습니다.")

    if "hasHeadline" not in fm:
        other.append("hasHeadline 필드가 없습니다.")

    headline = str(fm.get("headline", "")).strip()
    if not headline:
        other.append("headline 필드가 비어있습니다.")

    return Issue(missing=missing, extra=extra, other=other)


def format_result(issue: Issue) -> str:
    if issue.ok:
        return "PASS\n"

    parts: list[str] = []
    reasons: list[str] = []
    if issue.missing:
        reasons.append("누락된 링크 존재")
    if issue.extra:
        reasons.append("추가된 링크 존재")
    if issue.other:
        reasons.append("기타 검증 실패")

    parts.append("FAIL: " + ", ".join(reasons))

    if issue.missing:
        parts.append("\n## 누락된 링크")
        for i, line in enumerate(_fmt_url_list(issue.missing), 1):
            parts.append(f"{i}. {line}")

    if issue.extra:
        parts.append("\n## 변경된 링크")
        for i, line in enumerate(_fmt_url_list(issue.extra), 1):
            parts.append(f"{i}. 번역본에만 존재: {line}")

    if issue.other:
        parts.append("\n## 기타 문제")
        for item in issue.other:
            parts.append(f"- {item}")

    parts.append("\n## 수정 제안")
    if issue.missing:
        parts.append("- 누락된 URL을 번역본에 동일하게 추가하세요.")
    if issue.extra:
        parts.append("- 원문에 없는 링크를 번역본에서 제거하세요.")
    if issue.other:
        parts.append("- Frontmatter/메타데이터 규칙을 프롬프트대로 맞추세요.")

    return "\n".join(parts).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="오프라인 번역 검토기")
    parser.add_argument("--original", required=True, help="원문 파일 경로")
    parser.add_argument("--translated", required=True, help="번역본 파일 경로")
    args = parser.parse_args()

    original = open(args.original, "r", encoding="utf-8").read()
    translated = open(args.translated, "r", encoding="utf-8").read()

    result = format_result(review(original, translated))
    sys.stdout.write(result)
    return 0 if result.startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())

