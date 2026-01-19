#!/usr/bin/env python3
"""
state_manager.py - 상태 관리
파이프라인 실행 상태를 관리합니다.
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from enum import Enum
from typing import Optional

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

DATA_DIR = PROJECT_ROOT / "data"
STATE_FILE = DATA_DIR / "processed.json"


class ProcessStatus(Enum):
    """처리 상태"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


def load_state() -> dict:
    """상태 파일을 로드합니다."""
    if not STATE_FILE.exists():
        return {
            "processed": [],
            "last_check": None,
            "stats": {
                "total_processed": 0,
                "success_count": 0,
                "failed_count": 0,
            }
        }

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {
            "processed": [],
            "last_check": None,
            "stats": {
                "total_processed": 0,
                "success_count": 0,
                "failed_count": 0,
            }
        }


def save_state(state: dict):
    """상태 파일을 저장합니다."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def get_processed_slugs() -> set[str]:
    """처리된 slug 목록을 반환합니다."""
    state = load_state()
    return {item["slug"] for item in state["processed"]}


def is_processed(slug: str) -> bool:
    """slug가 이미 처리되었는지 확인합니다."""
    return slug in get_processed_slugs()


def get_status(slug: str) -> Optional[str]:
    """slug의 처리 상태를 반환합니다."""
    state = load_state()
    for item in state["processed"]:
        if item["slug"] == slug:
            return item.get("status", "unknown")
    return None


def update_status(
    slug: str,
    status: ProcessStatus,
    pr_url: str = None,
    error: str = None,
    metadata: dict = None,
):
    """slug의 상태를 업데이트합니다."""
    state = load_state()

    # 기존 항목 찾기
    existing_idx = None
    for i, item in enumerate(state["processed"]):
        if item["slug"] == slug:
            existing_idx = i
            break

    entry = {
        "slug": slug,
        "status": status.value,
        "updated_at": datetime.now().isoformat(),
    }

    if pr_url:
        entry["pr_url"] = pr_url
    if error:
        entry["error"] = error
    if metadata:
        entry["metadata"] = metadata

    if existing_idx is not None:
        # 기존 항목 업데이트
        old_entry = state["processed"][existing_idx]
        entry["created_at"] = old_entry.get("created_at", entry["updated_at"])
        state["processed"][existing_idx] = entry
    else:
        # 새 항목 추가
        entry["created_at"] = entry["updated_at"]
        state["processed"].append(entry)

    # 통계 업데이트
    if status == ProcessStatus.SUCCESS:
        state["stats"]["success_count"] = len([
            p for p in state["processed"] if p["status"] == "success"
        ])
    elif status == ProcessStatus.FAILED:
        state["stats"]["failed_count"] = len([
            p for p in state["processed"] if p["status"] == "failed"
        ])

    state["stats"]["total_processed"] = len(state["processed"])

    save_state(state)


def mark_in_progress(slug: str):
    """slug를 진행 중으로 표시합니다."""
    update_status(slug, ProcessStatus.IN_PROGRESS)


def mark_success(slug: str, pr_url: str = None, metadata: dict = None):
    """slug를 성공으로 표시합니다."""
    update_status(slug, ProcessStatus.SUCCESS, pr_url=pr_url, metadata=metadata)


def mark_failed(slug: str, error: str = None):
    """slug를 실패로 표시합니다."""
    update_status(slug, ProcessStatus.FAILED, error=error)


def mark_skipped(slug: str, reason: str = None):
    """slug를 건너뛰기로 표시합니다."""
    update_status(slug, ProcessStatus.SKIPPED, error=reason)


def get_failed_items() -> list[dict]:
    """실패한 항목 목록을 반환합니다."""
    state = load_state()
    return [item for item in state["processed"] if item["status"] == "failed"]


def get_stats() -> dict:
    """통계를 반환합니다."""
    state = load_state()
    return state.get("stats", {})


def reset_failed(slug: str = None):
    """실패한 항목을 재시도 가능하도록 리셋합니다."""
    state = load_state()

    if slug:
        # 특정 slug만 리셋
        state["processed"] = [
            p for p in state["processed"] if p["slug"] != slug
        ]
    else:
        # 모든 실패 항목 리셋
        state["processed"] = [
            p for p in state["processed"] if p["status"] != "failed"
        ]

    # 통계 재계산
    state["stats"]["total_processed"] = len(state["processed"])
    state["stats"]["success_count"] = len([
        p for p in state["processed"] if p["status"] == "success"
    ])
    state["stats"]["failed_count"] = len([
        p for p in state["processed"] if p["status"] == "failed"
    ])

    save_state(state)


def main():
    parser = argparse.ArgumentParser(
        description="파이프라인 실행 상태를 관리합니다."
    )
    subparsers = parser.add_subparsers(dest="command", help="명령")

    # status 명령
    status_parser = subparsers.add_parser("status", help="상태 확인")
    status_parser.add_argument("slug", nargs="?", help="확인할 slug")

    # mark 명령
    mark_parser = subparsers.add_parser("mark", help="상태 설정")
    mark_parser.add_argument("slug", help="설정할 slug")
    mark_parser.add_argument(
        "--status",
        choices=["pending", "in_progress", "success", "failed", "skipped"],
        required=True,
        help="설정할 상태"
    )
    mark_parser.add_argument("--pr-url", help="PR URL")
    mark_parser.add_argument("--error", help="에러 메시지")

    # list 명령
    list_parser = subparsers.add_parser("list", help="목록 조회")
    list_parser.add_argument(
        "--status",
        choices=["pending", "in_progress", "success", "failed", "skipped"],
        help="필터링할 상태"
    )

    # stats 명령
    subparsers.add_parser("stats", help="통계 조회")

    # reset 명령
    reset_parser = subparsers.add_parser("reset", help="실패 항목 리셋")
    reset_parser.add_argument("slug", nargs="?", help="리셋할 slug (없으면 모두)")

    args = parser.parse_args()

    if args.command == "status":
        if args.slug:
            status = get_status(args.slug)
            if status:
                print(f"{args.slug}: {status}")
            else:
                print(f"{args.slug}: not found")
        else:
            state = load_state()
            print(f"Last check: {state.get('last_check', 'never')}")
            print(f"Total items: {len(state['processed'])}")

    elif args.command == "mark":
        status_enum = ProcessStatus(args.status)
        update_status(args.slug, status_enum, pr_url=args.pr_url, error=args.error)
        print(f"Marked '{args.slug}' as {args.status}")

    elif args.command == "list":
        state = load_state()
        items = state["processed"]
        if args.status:
            items = [i for i in items if i["status"] == args.status]

        for item in items:
            print(f"- {item['slug']}: {item['status']}")

    elif args.command == "stats":
        stats = get_stats()
        print(f"Total processed: {stats.get('total_processed', 0)}")
        print(f"Success: {stats.get('success_count', 0)}")
        print(f"Failed: {stats.get('failed_count', 0)}")

    elif args.command == "reset":
        reset_failed(args.slug)
        if args.slug:
            print(f"Reset '{args.slug}'")
        else:
            print("Reset all failed items")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
