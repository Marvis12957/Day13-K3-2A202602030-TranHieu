"""TICKET C3 — tạo/đổi label prompt `day13-chat` trên Langfuse bằng SDK.

Cần LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY trong .env (xem SETUP.md).

    python scripts/setup_prompts.py --create      # v1 (baseline+production) và v2 (candidate)
    python scripts/setup_prompts.py --list        # xem version + label hiện tại
    python scripts/setup_prompts.py --promote 2   # chuyển label production sang v2
    python scripts/setup_prompts.py --promote 1   # rollback production về v1

Script chỉ gọi API Langfuse; không ghi giả prompt_version vào code hay trace.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from app.cli import configure_utf8_stdio

PROMPT_NAME = os.getenv("LANGFUSE_PROMPT_NAME", "day13-chat")

# v1 = baseline: đúng contract 3 biến trong docs/PROMPT_VERSIONING.md
V1_TEMPLATE = "Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}"
# v2 = candidate: thay đổi nhỏ về độ dài câu trả lời, giữ nguyên 3 biến
V2_TEMPLATE = (
    "Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}\n"
    "Answer concisely under 200 words."
)


def _client():
    load_dotenv()
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        print("Thiếu LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY trong .env — xem SETUP.md.")
        raise SystemExit(1)

    from langfuse import Langfuse

    return Langfuse()


def create(client) -> None:
    v1 = client.create_prompt(
        name=PROMPT_NAME,
        type="text",
        prompt=V1_TEMPLATE,
        labels=["baseline", "production"],
        commit_message="v1 baseline: prompt contract 3 bien (feature/docs/message)",
    )
    print(f"Đã tạo v{v1.version} labels=baseline,production")

    v2 = client.create_prompt(
        name=PROMPT_NAME,
        type="text",
        prompt=V2_TEMPLATE,
        labels=["candidate"],
        commit_message="v2 candidate: them rang buoc do dai cau tra loi",
    )
    print(f"Đã tạo v{v2.version} labels=candidate")
    print(
        "\nTiếp theo: đổi LANGFUSE_PROMPT_LABEL trong .env sang baseline rồi candidate,\n"
        "restart uvicorn và chạy cùng 1 input để có 2 trace với prompt_version khác nhau."
    )


def list_versions(client) -> None:
    versions = client.api.prompts.get(name=PROMPT_NAME)
    for v in versions.versions if hasattr(versions, "versions") else [versions]:
        print(f"v{v.version} labels={list(v.labels)} tags={list(v.tags or [])}")


def promote(client, version: int) -> None:
    """Gắn label `production` vào version chỉ định (dùng cho cả promote và rollback)."""
    updated = client.api.prompt_version.update(
        name=PROMPT_NAME, version=version, new_labels=["production"]
    )
    print(f"Label production -> v{updated.version} (labels hiện tại: {list(updated.labels)})")


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Quản lý prompt version cho Day 13 (TICKET C3)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create", action="store_true", help="Tạo v1 (baseline+production) và v2 (candidate)")
    group.add_argument("--list", action="store_true", help="Liệt kê version và label hiện tại")
    group.add_argument("--promote", type=int, metavar="VERSION", help="Chuyển label production sang version này")
    args = parser.parse_args()

    client = _client()
    if args.create:
        create(client)
    elif args.list:
        list_versions(client)
    else:
        promote(client, args.promote)
    client.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
